#!/usr/bin/env node
/** Customer/Dispatcher commerce adapter. Node >=20, no dependencies. */
import { readFile, writeFile, mkdir, rename, rm } from 'node:fs/promises';
import { resolve, dirname, basename } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { LuluLabClient, resolveApiKey, imageMimeType } from './lululab_cli.mjs';
const SCHEMA = 'lululab.dispatcher.commerce.v1';
const terminal = task => ['Succeeded', 'Failed', 'Cancelled'].includes(task?.status);
const guid = value => typeof value === 'string' && /^[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}$/i.test(value);
function url(value) {
  const parsed = new URL(value);
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password) throw Error('Media must use HTTPS without credentials.');
  return parsed.href;
}
function refs(files = [], mediaType = 'image') {
  if (!Array.isArray(files)) throw Error('References must be arrays.');
  return files.map(file => {
    if (!file?.mimeType?.startsWith(`${mediaType}/`)) throw Error(`Expected uploaded ${mediaType} references.`);
    const expiredAt = file.expiredAt || file.expiresAt;
    if (expiredAt && (!Number.isFinite(Date.parse(expiredAt)) || Date.parse(expiredAt) <= Date.now())) throw Error('Reference image expired.');
    return { url: url(file.location ?? file.url), mimeType: file.mimeType, ...(expiredAt ? { expiredAt } : {}) };
  });
}
function integer(value, min, max, label) {
  if (!Number.isInteger(value) || value < min || value > max) throw Error(`Invalid ${label}: ${min}–${max}.`);
  return value;
}
function videoCreativeBrief(c) {
  const labels = { productPitch: '口播带货', storyDrivenAd: '剧情带货', lifestyleSeeding: '场景种草' };
  const text = value => String(value ?? '').trim();
  if (c.materialDescriptions !== undefined && !Array.isArray(c.materialDescriptions)) throw Error('materialDescriptions must be an array.');
  return [
    c.creativeType === 'auto' ? '创意类型：智能推荐；根据商品与素材从口播带货、剧情带货、场景种草中选择。' : `创意类型：${labels[c.creativeType]}`,
    `口播语言：${c.targetLanguage}；使用该语言的自然口语。`,
    `画面比例：${c.aspectRatio}`, `视频分辨率：${c.resolution}`,
    text(c.category) ? `商品类目：${text(c.category)}` : '',
    text(c.features) ? `产品特性：${text(c.features)}` : '',
    text(c.usageScenarios) ? `使用场景：${text(c.usageScenarios)}` : '',
    ...(c.materialDescriptions ?? []).map((value, index) => text(value) ? `素材${index + 1}：${text(value)}` : ''),
    text(c.creativeRequirement),
  ].filter(Boolean).join('\n');
}
function videoPromptWithVoiceReference(prompt, c) {
  if (!c.referenceAudios?.length) return prompt;
  prompt = prompt.replace(/\n\n【系统音色参考规则】[\s\S]*?【系统音色参考规则结束】$/, '');
  if (c.generateAudio === false) return prompt;
  const rule = "人物说话音色仅参考独立添加的音频素材；默认使用@音频1，多声音时按创作文案明确指定的音频与人物对应关系使用。独立音频的音色优先于任何参考视频中的人声，忽略参考视频原声的音色，不得混合两者。参考视频仍用于人物形象与表现参考。";
  return `${prompt}\n\n【系统音色参考规则】${rule}仅参考人声身份、音色和自然发声特点，不照搬参考素材中的台词、背景音乐或环境声。台词、语言与是否口播遵循本次创作文案，不得因存在声音参考而新增口播。同一人物在所有分段中保持相同音色；每个含该人物口播的分段都必须保留对应的音色参考来源及优先级。以上音色来源优先级覆盖创作文案中与其冲突的音色来源要求。【系统音色参考规则结束】`;
}

export function buildPlan(config) {
  if (config?.kind !== 'video') throw Error('This skill requires kind=video.');
  const c = { aspectRatio: '9:16', targetCountry: '美国', targetLanguage: 'en-US', creativeRequirement: '', ...config };
  if (!['video', 'image'].includes(c.kind)) throw Error('kind must be video or image.');
  c.productImages = refs(c.productImages); c.creatorImages = refs(c.creatorImages);
  if (c.kind === 'video') {
    c.referenceAudios = refs(c.referenceAudios, 'audio');
    if (c.productImages.length + c.creatorImages.length > 10 || c.referenceAudios.length > 10) throw Error('Too many reference files.');
  }
  if (!c.productImages.length) throw Error('Product images are required.');
  if (c.creatorImages.length > 1 && c.kind === 'image') throw Error('Frontend image mode supports one creator image.');
  if (typeof c.creativeRequirement !== 'string') throw Error('creativeRequirement must be text.');
  if (c.kind === 'video') {
    c.model ??= 'seedance-2-fast'; c.duration ??= 15; c.count ??= 1; c.resolution ??= '720p'; c.generateAudio ??= true; c.creativeType ??= 'auto';
    integer(c.duration, 4, 60, 'duration'); integer(c.count, 1, 20, 'video count');
    if (!['auto', 'productPitch', 'storyDrivenAd', 'lifestyleSeeding'].includes(c.creativeType)) throw Error('Invalid creativeType.');
    if (!['seedance-2-mini', 'seedance-2-fast', 'seedance-2', 'seedance-2-5', 'wan-3', 'minimax-h3', 'google-omni', 'grok-imagine-1-5-preview'].includes(c.model)) throw Error('Unsupported commerce model.');
    if (typeof c.generateAudio !== 'boolean') throw Error('generateAudio must be boolean.');
    const standard = ['21:9', '16:9', '4:3', '1:1', '3:4', '9:16'];
    const ratios = c.model === 'google-omni' ? ['9:16', '16:9'] : c.model === 'wan-3' ? ['9:16', '16:9', '1:1', '3:4', '4:3'] : c.model.startsWith('grok-') ? ['16:9', '4:3', '3:2', '9:16', '3:4', '1:1', '2:3'] : standard;
    const sizes = c.model === 'google-omni' ? ['720p', '1080p', '2160p'] : c.model === 'minimax-h3' ? ['720p', '1440p'] : c.model === 'wan-3' ? ['720p', '1080p'] : c.model === 'seedance-2-5' ? ['480p', '720p', '1080p'] : ['480p', '720p'];
    if (!ratios.includes(c.aspectRatio) || !sizes.includes(c.resolution)) throw Error('Unsupported model settings.');
    if (c.model === 'google-omni' && ![4, 6, 8, 10].includes(c.duration)) throw Error('Omni duration must be 4, 6, 8 or 10 seconds.');
    if ((c.model === 'minimax-h3' || c.model.startsWith('grok-')) && c.duration > 15) throw Error('Selected model supports at most 15 seconds.');
    // Seedance/Wan long videos are split and merged by VideoCreationV1.
    const assetItems = (originals, normalized) => normalized.map((file, index) => {
      const asset = { ...originals[index], ...file }, name = asset.fileName || `Reference ${index + 1}`;
      return { id: asset.id || file.url, asset, name, url: file.url };
    });
    const markets = [['US', '美国', 'United States'], ['CN', '中国', 'China'], ['GB', '英国', 'United Kingdom'],
      ['EU', '欧洲', 'Europe'], ['LATAM', '拉丁美洲', 'Latin America'], ['SEA', '东南亚', 'Southeast Asia'],
      ['AS', '亚洲', 'Asia'], ['AU', '澳大利亚', 'Australia'], ['ME', '中东', 'Middle East']];
    const region = markets.find(market => market.includes(c.targetCountry))?.[0] ?? c.targetCountry;
    const editorSnapshot = { productName: c.productName ?? '', creativeNotes: [c.sellingPoints ? `卖点：${c.sellingPoints}` : '', c.targetAudience ? `目标受众：${c.targetAudience}` : '', videoCreativeBrief(c).split('\n').slice(4).join('\n')].filter(Boolean).join('\n'),
      productAssets: assetItems(config.productImages, c.productImages), characterAssets: assetItems(config.creatorImages ?? [], c.creatorImages),
      voiceAssets: assetItems(config.referenceAudios ?? [], c.referenceAudios), region, language: c.targetLanguage,
      videoType: { auto: '智能匹配', productPitch: '口播带货', storyDrivenAd: '剧情带货', lifestyleSeeding: '场景种草' }[c.creativeType],
      videoCount: c.count, model: c.model, aspectRatio: c.aspectRatio, resolution: c.resolution,
      duration: c.duration, generateAudio: c.generateAudio, mentionBindings: [] };
    return { config: c, task: { workflowId: 'SalesVideoPromptV3', editorSnapshot, input: {
      model: c.model, duration: c.duration, videoCount: c.count, aspectRatio: c.aspectRatio,
      resolution: c.resolution, generateAudio: c.generateAudio,
      referenceImages: [...c.productImages, ...c.creatorImages], creativeType: c.creativeType,
      salesRegion: c.targetCountry, speechLanguage: c.targetLanguage,
      productInfo: { name: (c.productName ?? '').trim(), category: (c.category ?? '').trim(), features: (c.features ?? '').trim(),
        sellingPoints: (c.sellingPoints ?? '').trim(), targetAudience: (c.targetAudience ?? '').trim(), usageScenarios: (c.usageScenarios ?? '').trim() },
      creativeBrief: videoCreativeBrief(c),
    } } };
  }
  c.model ??= 'gpt-image-2-5-sunburst'; c.resolution ??= '1K'; c.count ??= 9;
  integer(c.count, 1, 10, 'image count');
  if (!['gpt-image-2-5-sunburst', 'gpt-image-2-5-flare'].includes(c.model) || !['1K', '2K', '4K'].includes(c.resolution)
    || !['9:16', '3:4', '4:5', '1:1', '16:9'].includes(c.aspectRatio)) throw Error('Unsupported frontend image settings.');
  if (c.creativeMode && c.creativeMode !== 'original') throw Error('Benchmark adaptation uses the legacy workflow; the frontend supports original images.');
  return { config: c, task: { workflowId: 'ProductImagePromptV1', input: {
    productBrief: { productName: c.productName ?? '', sellingPoints: Array.isArray(c.sellingPoints) ? c.sellingPoints : (c.sellingPoints ?? '').split('\n').filter(Boolean),
      targetCountry: c.targetCountry, targetAudience: c.targetAudience ?? '', productImages: c.productImages },
    creativeRequirement: c.creativeRequirement,
    userConfig: { creativeMode: 'original', cardsPerSet: c.count, aspectRatio: c.aspectRatio,
      targetLanguage: c.targetLanguage, storyStyle: 'storyDrivenCarousel', imageStyle: 'storyDrivenCarousel' },
    creatorBrief: { creatorMode: c.creatorImages.length ? 'provided' : 'none', creatorImages: c.creatorImages },
  } } };
}
function record(value) { return typeof value === 'string' ? JSON.parse(value) : value; }
export function generationTasks(plan, planning) {
  if (planning.status !== 'Succeeded' || !guid(planning.id)) throw Error('Planning has not succeeded.');
  const root = record(planning.output), payload = record(root?.output) ?? root;
  if (!payload || root.success === false || payload.success === false) throw Error('Planning output indicates failure.');
  const c = plan.config, images = [...c.productImages, ...c.creatorImages];
  if (c.kind === 'video') {
    const entries = Array.isArray(payload.videos) ? payload.videos : c.count === 1 ? [payload] : [];
    if (entries.length !== c.count) throw Error('Video plan count mismatch.');
    const seen = new Set();
    return entries.map((entry, index) => {
      const v = record(entry), p = record(v?.videoPrompt);
      if ((Array.isArray(payload.videos) && v.videoId !== index + 1) || p?.duration !== c.duration || !p?.prompt?.trim() || !p?.summary?.trim()) throw Error('Invalid full video plan.');
      const signature = p.prompt.replace(/\s+/g, '');
      if (seen.has(signature)) throw Error('Duplicate video plans.'); seen.add(signature);
      return { workflowId: 'VideoCreationV1', editorSnapshot: { ...plan.task.editorSnapshot, planningTaskId: planning.id }, input: { taskType: 'reference', model: c.model, aspectRatio: c.aspectRatio,
        resolution: c.resolution, duration: c.duration, generateAudio: c.generateAudio, prompt: videoPromptWithVoiceReference(p.prompt, c), referenceImages: images,
        ...(c.referenceAudios?.length ? { referenceAudios: c.referenceAudios } : {}) },
        attributes: { saveGeneratedAssets: true, creationSource: 'commerce' } };
    });
  }
  const cards = record(payload.imagePrompts)?.cards;
  if (!Array.isArray(cards) || cards.length !== c.count) throw Error('Image plan count mismatch.');
  return cards.map((card, index) => {
    card = record(card);
    if (!card?.prompt?.trim()) throw Error('Empty card prompt.');
    return { workflowId: 'ImageGenV2', input: { model: c.model, prompt: card.prompt, aspectRatio: c.aspectRatio,
      resolution: c.resolution, referenceImages: images }, attributes: { saveGeneratedAssets: true,
      creationSource: 'shoppable-images', parentTaskId: planning.id, cardIndex: index } };
  });
}

export class CommerceClient extends LuluLabClient {
  async upload(file, requestedMimeType) {
    const bytes = await readFile(file), mimeType = requestedMimeType ?? imageMimeType(bytes);
    if (!bytes.length || !mimeType || (!mimeType.startsWith('image/') && !/^audio\/[\w.+-]+$/.test(mimeType))) throw Error('Upload requires an image or an explicit audio MIME type.');
    if (mimeType.startsWith('image/') && imageMimeType(bytes) !== mimeType) throw Error('Image MIME type does not match its content.');
    const ticket = await this.request('/uploads', { method: 'POST' });
    if (!guid(ticket.id)) throw Error('Upload ticket ID missing.');
    const form = new FormData();
    form.append('file', new Blob([bytes], { type: mimeType }), basename(file));
    const response = await this.fetch(url(ticket.presignedUrl), { method: 'POST', body: form,
      redirect: 'error', signal: AbortSignal.timeout(this.timeoutMs) });
    if (!response.ok) throw Error(`Upload HTTP ${response.status}.`);
    // Like the browser client, confirm the uploaded file through the owned asset
    // library. The transfer response is not a TemporaryFile contract.
    for (let attempt = 0; attempt < 20; attempt++) {
      for (let page = 1; page <= 10; page++) {
        const result = await this.request(`/files?page=${page}&pageSize=100`);
        if (!Array.isArray(result.items)) throw Error('Asset library returned invalid file data.');
        const file = result.items.find(item => item.id === ticket.id);
        if ((file?.location || file?.url) && Number(file.size) === bytes.length) return { id: file.id, ...refs([file], mimeType.startsWith('audio/') ? 'audio' : 'image')[0] };
        if (file || page * 100 >= result.total) break;
      }
      await new Promise(done => setTimeout(done, 500));
    }
    throw Error('Uploaded file was not confirmed by the asset library.');
  }
}

async function save(file, state) {
  await mkdir(dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  await writeFile(tmp, JSON.stringify(state, null, 2) + '\n', { mode: 0o600 }); await rename(tmp, file);
}
async function load(file) { try { return JSON.parse(await readFile(file, 'utf8')); } catch (e) { if (e.code === 'ENOENT') return null; throw e; } }
async function locked(file, action) {
  await mkdir(dirname(file), { recursive: true }); const lock = `${file}.lock`;
  try { await mkdir(lock); } catch (e) { if (e.code === 'EEXIST') throw Error('State locked; verify the old process stopped before removing its lock.'); throw e; }
  try { return await action(); } finally { await rm(lock, { recursive: true }); }
}
async function createTask(state, slot, request, file, client) {
  if (slot.task?.id) return;
  if (slot.submissionUnknown) throw Error('Submission may already exist. Inspect owned task history; do not resubmit.');
  for (const files of [request.input?.referenceImages, request.input?.referenceAudios]) {
    for (const media of files ?? []) {
      const expiry = media.expiredAt || media.expiresAt;
      if (expiry && (!Number.isFinite(Date.parse(expiry)) || Date.parse(expiry) <= Date.now())) throw Error('Reference expired; no new task was submitted. Preserve the state and existing task IDs.');
    }
  }
  const quote = await client.request('/billing/quotes', { method: 'POST', body: request });
  if (!guid(quote?.id)) throw Error('Quote ID missing.');
  slot.request = request; slot.quoteId = quote.id; slot.submissionUnknown = true;
  await save(file, state);
  const task = await client.request('/tasks', { method: 'POST', body: { ...request, quoteId: quote.id } });
  if (!guid(task?.id)) throw Error('Task ID missing; inspect history before recovery.');
  slot.task = task; slot.submissionUnknown = false; await save(file, state);
}
export async function submit(config, file, client) {
  const plan = buildPlan(config), signature = createHash('sha256').update(JSON.stringify(plan)).digest('hex');
  return locked(file, async () => {
    let state = await load(file);
    if (state && (state.schema !== SCHEMA || state.signature !== signature)) throw Error('State belongs to another request or legacy task.');
    state ??= { schema: SCHEMA, signature, plan, planning: {}, generations: [] };
    await createTask(state, state.planning, plan.task, file, client); return state;
  });
}
export async function advance(file, client, approved = false) {
  return locked(file, async () => {
    const state = await load(file);
    if (state?.schema !== SCHEMA) throw Error('No saved commerce state.');
    for (const slot of [state.planning, ...state.generations]) {
      if (slot.submissionUnknown && !slot.task?.id) throw Error('Uncertain submission; inspect history before recovery.');
      if (slot.task?.id && !terminal(slot.task)) { slot.task = await client.task(slot.task.id); await save(file, state); }
    }
    if (approved && state.planning.task?.status === 'Succeeded') {
      const requests = generationTasks(state.plan, state.planning.task);
      for (const [index, request] of requests.entries()) {
        state.generations[index] ??= {};
        await createTask(state, state.generations[index], request, file, client);
      }
    }
    return state;
  });
}
export function estimateItems(plan) {
  const { kind, model, resolution, duration, count } = plan.config;
  if (kind === 'image') return [{ workflowId: 'ProductImagePromptV1' }, { workflowId: 'ImageGenV2', input: { model, resolution, imageCount: count } }];
  // Match salesVideoCreditEstimateItems: at most ten videos per estimate item.
  return [{ workflowId: 'SalesVideoPromptV3' }, ...Array.from({ length: Math.ceil(count / 10) }, (_, index) => ({
    workflowId: 'VideoCreationV1', input: { model, resolution, duration, videoCount: Math.min(10, count - index * 10) },
  }))];
}

export async function estimate(config, client) {
  const result = await client.request('/billing/estimates', { method: 'POST', body: { items: estimateItems(buildPlan(config)) } });
  if (!Number.isSafeInteger(result?.credits) || result.credits < 0) throw Error('Billing estimate has no valid credit total. Do not submit.');
  return result;
}

export async function main(args = process.argv.slice(2)) {
  if (!args.length || args.includes('--help')) {
    process.stdout.write('Dispatcher commerce: upload --file PATH --output asset.json [--mime-type audio/mpeg]; plan --config request.json; estimate --config request.json; submit --config request.json --state state.json --generation-approved; advance --state state.json --generation-approved; poll --state state.json; download --state state.json --output DIR\nplan is offline; poll only reads tasks; advance submits missing generation tasks under the original approval.\n'); return;
  }
  const command = args[0], allowed = { upload: ['--file', '--output', '--mime-type'], plan: ['--config'], estimate: ['--config'], submit: ['--config', '--state', '--generation-approved'], advance: ['--state', '--generation-approved'], poll: ['--state'], download: ['--state', '--output'] };
  if (!allowed[command]) throw Error('Unknown command.');
  const flags = {};
  for (let i = 1; i < args.length; i++) {
    const flag = args[i];
    if (!allowed[command].includes(flag) || Object.hasOwn(flags, flag)) throw Error('Unknown or repeated flag.');
    if (flag === '--generation-approved') flags[flag] = true;
    else { if (!args[i + 1] || args[i + 1].startsWith('--')) throw Error('Missing flag value.'); flags[flag] = args[++i]; }
  }
  const path = name => { if (!flags[name]) throw Error(`Missing ${name}.`); return resolve(flags[name]); };
  if (['submit', 'advance'].includes(command) && !flags['--generation-approved']) throw Error('Existing user authorization is required.');
  const config = ['plan', 'estimate', 'submit'].includes(command) ? JSON.parse(await readFile(path('--config'), 'utf8')) : null;
  if (command === 'plan') { process.stdout.write(JSON.stringify(buildPlan(config), null, 2) + '\n'); return; }
  const stateFile = ['submit', 'advance', 'poll', 'download'].includes(command) ? path('--state') : null;
  const output = ['upload', 'download'].includes(command) ? path('--output') : null;
  const source = command === 'upload' ? path('--file') : null;
  const client = new CommerceClient({ apiKey: await resolveApiKey(), baseUrl: process.env.LULULAB_API_BASE_URL || 'https://customer.lululab.ai' });
  let state;
  if (command === 'estimate') state = await estimate(config, client);
  else if (command === 'upload') { const asset = await client.upload(source, flags['--mime-type']); await save(output, asset); state = asset; }
  else if (command === 'submit') state = await submit(config, stateFile, client);
  else if (command === 'advance' || command === 'poll') state = await advance(stateFile, client, command === 'advance');
  else {
    state = await locked(stateFile, async () => {
      const s = await load(stateFile);
      if (s?.schema !== SCHEMA) throw Error('No saved commerce state.');
      await mkdir(output, { recursive: true });
      for (const [index, slot] of s.generations.entries()) {
        if (slot.task?.status !== 'Succeeded') continue;
        const payload = record(slot.task.output), video = s.plan.config.kind === 'video';
        const result = video ? payload?.video : payload?.image ?? payload?.images?.[0];
        const address = url(typeof result === 'string' ? result : result?.url);
        const response = await client.fetch(address, { redirect: 'error', signal: AbortSignal.timeout(180000) });
        if (!response.ok) throw Error(`Download HTTP ${response.status}.`);
        const bytes = Buffer.from(await response.arrayBuffer());
        if (!bytes.length) throw Error('Empty output.');
        const mime = response.headers.get('content-type')?.split(';')[0];
        const extension = video ? 'mp4' : ({ 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp' }[mime]);
        if (!extension) throw Error('Unsupported output media type.');
        slot.file = resolve(output, `${video ? 'video' : 'card'}_${String(index + 1).padStart(2, '0')}.${extension}`);
        await writeFile(slot.file, bytes); await save(stateFile, s);
      }
      return s;
    });
  }
  process.stdout.write(JSON.stringify(state, null, 2) + '\n');
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) main().catch(error => { process.stderr.write(error.message + '\n'); process.exitCode = 1; });
