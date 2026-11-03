import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildPlan, generationTasks, CommerceClient } from '../scripts/dispatcher_commerce.mjs';
const id = '11111111-1111-4111-8111-111111111111';
const product = { id, url: 'https://assets.example/product.png', mimeType: 'image/png' };
const voice = { id, url: 'https://assets.example/voice.mp3', mimeType: 'audio/mpeg' };
const config = { kind: 'video', productImages: [product] };
test('website history preserves media roles and links generated videos to planning', () => {
  const p = buildPlan({ ...config, creatorImages: [product], referenceAudios: [voice], targetCountry: '日本', targetLanguage: 'ja-JP', creativeRequirement: '保持包装', sellingPoints: '便携' });
  assert.equal(p.task.editorSnapshot.language, 'ja-JP');
  assert.equal(p.task.editorSnapshot.productAssets[0].asset.id, id);
  assert.equal(p.task.editorSnapshot.characterAssets.length, 1);
  assert.equal(p.task.editorSnapshot.voiceAssets[0].asset.url, voice.url);
  assert.ok(p.task.editorSnapshot.creativeNotes.includes('便携'));
  const t = generationTasks(p, { id, status: 'Succeeded', output: { videoPrompt: { summary: 'one', prompt: 'full prompt', duration: 15 } } })[0];
  assert.equal(t.editorSnapshot.planningTaskId, id);
  assert.deepEqual(t.input.referenceAudios, [{ url: voice.url, mimeType: voice.mimeType }]);
  assert.ok(t.input.prompt.includes('【系统音色参考规则】'));
  assert.equal(t.attributes.creationSource, 'commerce');
});
test('website ten-image limit is enforced before billing', () => {
  assert.equal(buildPlan({ ...config, productImages: Array(10).fill(product) }).config.productImages.length, 10);
  assert.throws(() => buildPlan({ ...config, productImages: Array(10).fill(product), creatorImages: [product] }));
});
test('audio uploads confirm owned file and never forward API key to signed host', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'commerce-audio-')), file = join(dir, 'voice.mp3');
  try {
    await writeFile(file, Buffer.from('audio-content'));
    const client = new CommerceClient({ apiKey: 'test-local-key', fetchImpl: async (address, options) => {
      const url = new URL(address);
      if (url.pathname === '/uploads') return Response.json({ id, presignedUrl: 'https://upload.example/signed' });
      if (url.hostname === 'upload.example') { assert.equal(options.headers, undefined); return new Response(''); }
      if (url.pathname === '/files') return Response.json({ total: 1, items: [{ ...voice, size: 13 }] });
      throw Error('Unexpected request');
    } });
    assert.equal((await client.upload(file, 'audio/mpeg')).mimeType, 'audio/mpeg');
  } finally { await rm(dir, { recursive: true, force: true }); }
});
