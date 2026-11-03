---
name: LuluLab-Product-Video
description: 根据商品图生成带货视频，通过与前端一致的 SalesVideoPromptV3 和 VideoCreationV1 调度器任务完成策划、分段生成与拼接。
metadata:
  version: "v9.2.1"
license: GPL-3.0-only
---

# LuluLab 带货视频

新任务与前端带货视频保持一致：`SalesVideoPromptV3 → VideoCreationV1`。本地只上传素材、提交策划、读取完整脚本、提交每条视频的父任务及查询下载。调度器负责分段、视频生成和拼接，不再由 skill 逐段调用 VideoGenV2 或本地 FFmpeg。CLI 是 Customer/Dispatcher API 的传输工具，不能直连 n8n 或绕过调度器。

默认 Seedance 2.0 Fast、15 秒、1 条、9:16、720p、生成声音；数量支持前端的 1～20 条，时长 4～60 秒（受模型能力限制）。创意类型 `auto`（智能匹配）、`productPitch`（口播带货）、`storyDrivenAd`（剧情带货）、`lifestyleSeeding`（场景种草）。模型和尺寸支持范围由适配器校验，不能静默替换用户选择。前端长视频由 VideoCreationV1 拆分。

达人与前端一致：可提供达人参考图，未提供则由脚本策划处理，不再额外生成本地多视角达人板。需要特定人物或风格时原样放入 creativeRequirement。产品图在前，达人图在后，策划和视频使用相同顺序。

请求示例（替换为实际上传结果）：

```json
{
  "kind": "video",
  "productName": "用户确认的产品名称",
  "sellingPoints": "用户确认的卖点",
  "targetAudience": "用户确认的受众",
  "productImages": [{"url":"https://asset.example/product.png","mimeType":"image/png"}],
  "creatorImages": [],
  "targetCountry": "美国",
  "targetLanguage": "en-US",
  "creativeType": "auto",
  "creativeRequirement": "",
  "model": "seedance-2-fast",
  "duration": 15,
  "count": 1,
  "aspectRatio": "9:16",
  "resolution": "720p",
  "generateAudio": true
}
```

策划输出须包含每条完整 videoPrompt 的 summary、prompt、匹配的 duration；多条须编号连续且内容不同。适配器验证后原样提交完整 prompt。失败或结构不符时停止，不自动重做付费策划。最终展示每条父任务 ID、实际状态、下载文件和失败原因。未观看成片不宣称视觉与口播已通过审查。

## 通用执行合同

网站与 Skill 共用 Customer/Dispatcher 后端：一次 `SalesVideoPromptV3` 批量策划，每条完整脚本对应一个 `VideoCreationV1` 父任务。服务端运行 `VideoSegmentPlanV1 → VideoGenV2 → 时长检查／必要裁剪 → 多段拼接`；分段并发与 provider 路由由服务端管理。Skill 不运行本地知识检索、ChatGenV2 母提示词、额外 AI 达人图、外部 CLI 渠道预检或本地分段生成与拼接。旧脚本只服务已有旧任务的恢复。

以 `scripts/dispatcher_commerce.mjs` 的 `buildPlan()` 和 `generationTasks()` 为本地唯一请求适配入口，不在对话中另造请求协议。前端对照源是 `workshop/src/domain/salesVideoPrompt.ts` 的 `salesVideoPromptV3BatchForm()`、`workshop/src/domain/videoTask.ts` 的 `createVideoTask()` 及 `workshop/src/config/workflows.ts`；后端是 `VideoCreationWorker`。更新模型能力与协议时一并核对这些入口；服务端未支持的配置须报错，不能靠换模型或绕过父任务补齐。

策划请求使用前端批量协议：`model/duration/videoCount/aspectRatio/resolution/generateAudio/referenceImages/creativeType/salesRegion/speechLanguage/productInfo/creativeBrief`，不再发送旧的四字段 PromptGen 请求。`creativeBrief` 由适配器按前端规则加入创意类型、口播语言、尺寸、已知商品信息和用户创作需求。生成请求传完整 `prompt` 与一致的素材顺序，`attributes.creationSource=commerce`、`saveGeneratedAssets=true`；不把服务端分段或内部 Prompt 当成新的用户输入。

可选 `referenceAudios` 接受已上传的音频媒体对象，生成任务保留这些引用，并按前端规则添加固定音色参考后缀；实际台词仍来自策划。`upload` 支持图片；使用 `--mime-type audio/mpeg` 等明确音频类型可上传本地声音素材。所有引用必须是实际上传结果，不能把本地路径伪装成媒体 URL。

交互语言跟随用户；口播语言独立由 `targetLanguage` 指定，未指定按目标市场确定。中文交流不自动把美国市场的英语视频改成中文。用户确认后沿用这份配置，错误和恢复说明使用交互语言。策划完成后按视频编号展示 summary 与完整 prompt（独立 text 代码块），随后按已确认配置提交，无需再次确认同一轮生成。

## 多语言交互与成品语言

- 三个概念独立处理：交互语言、目标市场、成品语言。交互语言依次采用用户明确指定的回复语言、宿主可用的语言设置、当前会话主要语言；无法判断时沿用上一轮，首次无上下文时使用用户本次消息的语言。支持按用户选择使用中文、英语、日语、韩语、西班牙语、葡萄牙语、法语、德语、越南语等语言，不限于中英文；不因本文或示例为中文就固定中文回复。
- 所有用户可见说明使用交互语言：素材收集、配置表的字段和选项、默认值说明、预计积分及计费明细、确认问题、进度、错误、恢复和交付说明。翻译服务端状态与计费项目的人类可读标签，保留原始积分数值、模型 ID、工作流 ID、命令、任务 ID、路径和 JSON 字段名。CLI 的原始英文输出由智能体用交互语言解释，不直接作为最终回复。
- 配置表单独列出成品语言；用户指定优先，否则沿用本 skill 的目标市场与默认规则，并作为待确认值展示。不得从交互语言推断市场或自动覆盖成品语言。图片内文字、发布文案、视频口播及字幕（仅实际支持的步骤）遵循目标语言；方言、地区用语和多语言混用要求完整保留。模型或工作流不支持时，在提交前说明限制并让用户选择，不静默改成中文或英语，也不承诺未经验证的语言效果。
- 确认文案均为可翻译示例。按交互语言表达“预计消耗 {credits} 积分；回复 1 开始，回复 2 修改”，接受数字或任意语言中明确等效的确认；拒绝、提问和修改配置不算确认。仅切换交流语言不改变生成配置或新增确认；修改成品语言属于配置变更，须更新请求、重新预估并确认。
- 服务端返回的生成 prompt 原文保留并原样提交；需要便于用户理解时，另附交互语言的摘要或译文并标为说明，不能用译文替换原 prompt。用户创作要求保留原文，不因翻译遗漏事实或修改语言选择。本节也适用于历史任务和旧参考文档；旧文档的“中文／非中文统一英文”展示规则不得覆盖本节。

视频请求通过 `targetLanguage` 传入口播语言（如 `ja-JP`、`es-ES`、`vi-VN`），适配器映射到策划的 `speechLanguage`，并保留用户创作要求。

## 调度器执行

需要 Node.js ≥20。从当前 SKILL.md 所在目录解析脚本，支持 Windows/macOS/Linux，无需 npm。凭证继续使用本 skill 已有的环境变量与私有配置；不在命令参数、提示词或日志中放 Key。默认 Customer API 为 `https://customer.lululab.ai`，可用 `LULULAB_API_BASE_URL` 指定开发环境。

收到产品图后识别可见商品事实；缺图时请求产品图。价格、优惠、功效、认证等只使用用户提供或素材有依据的信息。目标市场默认美国、发布语言默认 en-US；默认值只用于准备待确认配置。

### 提交前配置确认（必需）

每轮新任务用简短配置摘要一次确认，不逐字段提问。默认使用“项目／本轮配置”两列、以下五行合并展示；这里的“完整配置”指这些合并项覆盖实际提交参数，不要求把每个字段拆成单独确认项：

| 项目 | 展示内容 |
|---|---|
| 商品信息 | 产品名称及一句话可见卖点 |
| 素材 | 产品图数量及用途；仅有达人图或声音参考时补充其数量及用途；无达人图时简写“人物由策划安排” |
| 市场与受众 | 目标市场、成品／口播语言及受众；推测的受众标为“建议” |
| 创意 | 当前视频类型；有自定义创作需求时原样附上，无则不单列“无” |
| 生成规格 | 模型、时长 × 数量、画幅、分辨率、有声／无声合并为一行 |

省略单独的“来源”列。用一句话说明未指定参数采用默认值，仅在推测或建议的信息旁标注来源，避免将推测写成用户事实。所有值以本轮实际 request.json 为准。表格外简写本轮计费范围为“脚本策划 1 次＋视频生成 N 条”，积分预估仍按下述规则展示。

“创意”行必须展示当前视频类型；未指定时标为默认。在表格旁用一句话列出全部选项及简短说明，例如“类型可选：智能匹配（自动选择）／口播带货（人物讲解）／剧情带货（情节演绎）／场景种草（日常体验）”。不要另加一张类型表或向用户展示内部请求值。以下映射仅供构造请求，展示标签按交互语言翻译：

| 视频类型 | 简短说明 | 请求值 |
|---|---|---|
| 智能匹配（默认） | 根据商品与素材，从下列三种类型中选择 | `auto` |
| 口播带货 | 以人物讲解商品和卖点为主 | `productPitch` |
| 剧情带货 | 通过人物情节和使用场景介绍商品 | `storyDrivenAd` |
| 场景种草 | 以日常生活中的商品使用和体验为主 | `lifestyleSeeding` |

用户可直接用类型名称修改选择，将其映射为对应 creativeType 后，更新完整配置并重新预估积分，沿用本节的确认流程。

配置表后必须用交互语言展示**预计消耗：{credits} 积分**（翻译标签，保留真实数值），再让用户确认开始。先对同一份 request.json 运行 `estimate --config request.json`，读取 `/billing/estimates` 返回的 `credits`、`breakdown` 和 `version`；展示总额及服务端提供的计费明细，不写死单价、不用余额差推算，也不把预估说成最终扣费。多套请求须分别估算并汇总，列明套数、每套数量和本轮总积分。

预估查询不创建生成任务，可在确认前上传素材、校验配置并查询。预估失败、缺少有效积分总额或计费范围不完整时，说明原因并暂停提交，不把未知写成 0 或仅提示“可能收费”后继续。用户修改配置时重新估算并展示；用户须明确确认最终配置与预计积分后，才能传入 `--generation-approved`。同一配置与已展示计费范围的后续正常阶段沿用确认，不增加重复确认。提交时仍按服务端实时报价结算；若报价规则变化导致预计总额上涨，先展示更新预估并重新确认。旧入口的新计费提交也须先提供实际范围的预估，无法可靠估算时暂停。

确认文案示例（须翻译为交互语言，占位符必须替换为真实返回值）：“以上为本次配置，预计消耗 {credits} 积分，包含{计费步骤与数量}，实际按提交时服务端报价结算。回复 1 按当前配置和预计积分开始，回复 2 修改配置。”

面向用户的确认说明保持简洁：展示完整配置、真实积分预估与计费明细后，直接询问是否开始，并以开始／修改选项收尾。不要追加“依据技能要求”“技能规定必须确认”等内部规则说明，不引用 SKILL.md 原文或附上技能文件链接来解释确认流程；用户主动询问原因时再说明。此项只精简展示文案，仍须取得当前配置与预计积分的明确确认。

展示后必须明确询问用户是否按这份配置开始，并等待用户回复。只有用户明确确认当前已展示的完整配置，才可提交策划任务并传入 `--generation-approved`。“生成带货视频”“使用这个 skill”、上传素材、沉默或智能体自行宣布配置均不算配置确认。即使用户在最初请求中写明部分或全部参数，也要先展示最终配置并取得确认。用户已确认同一份配置时，后续策划、生成、查询与下载沿用该确认，不重复询问。

确认前可识别与整理素材、准备本地请求、执行离线 `plan` 校验及非生成式积分预估；不得创建策划、图片或视频任务。用户修改配置后须展示更新后的完整配置并重新确认，再用新 state 提交。付费重试或新增计费范围同样须明确确认；已有任务的只读查询与下载无需重新确认。

所有新任务使用 `scripts/dispatcher_commerce.mjs`：

```bash
node <技能根目录>/scripts/dispatcher_commerce.mjs upload --file <产品图路径> --output asset_01.json
node <技能根目录>/scripts/dispatcher_commerce.mjs plan --config request.json
node <技能根目录>/scripts/dispatcher_commerce.mjs estimate --config request.json
node <技能根目录>/scripts/dispatcher_commerce.mjs submit --config request.json --state state.json --generation-approved
node <技能根目录>/scripts/dispatcher_commerce.mjs poll --state state.json
node <技能根目录>/scripts/dispatcher_commerce.mjs advance --state state.json --generation-approved
node <技能根目录>/scripts/dispatcher_commerce.mjs download --state state.json --output <交付目录>
```

上传所有产品图和用户提供的达人图，把上传返回的 `{url,mimeType,expiredAt?}` 对象写入请求。`plan` 离线校验和展示实际请求，不读取 Key 或创建任务。`estimate` 查询 1 次策划及全部视频的总预估积分（超过 10 条时按每项最多 10 条拆分估算），不创建任务。`submit` 只创建策划任务；保存 state 后按需 `poll`，策划成功后 `advance` 逐个提交生成任务。等待生成期间继续 `poll`；它只查询，不会提交。每次 `advance` 只提交缺失的任务，已有 ID（含失败任务）不会重提。完成后下载成功结果，保留部分成功与所有失败信息。

产品图与人物图合计最多 10 张，声音参考最多 10 个，与网页一致。策划和视频任务均提交顶层 editorSnapshot，使用网站的 productAssets、characterAssets、voiceAssets、region、language 等字段；每条视频快照保留 planningTaskId。

每次任务创建都先调用 `/billing/quotes`，再携带 quoteId 调用 `/tasks`，与前端 SDK 一致。视频、图片保存 `saveGeneratedAssets` 及前端来源字段，使用同一账户可关联任务与资产。

不要自动付费重试、切换 provider、重做整批或在本地改写服务端返回的提示词。state 在 POST 之前落盘，并用文件锁避免并发重复提交。提交结果未知时停止，核对同账户任务历史及精确 input 后人工恢复，不能删除 state 后重提。中断后继续使用原 state；遗留锁须先确认原进程已停止。API Key 无效、积分不足或网络故障分别报告，不回显服务端原始错误中的私人数据。

`--generation-approved` 仅表示用户已明确确认本轮展示的完整配置与计费范围；不能根据泛化的生成请求自行设置此标志，也不代表脚本自行取得授权。修改配置后需新 state，并重新确认完整配置与计费范围。适配器本身不部署服务端或修改工作流。

当前目录名包含 backup 也按本文执行新任务，不能因目录名回到旧流程。

历史任务：仅恢复旧任务时读取 [references/LEGACY_WORKFLOW.md](references/LEGACY_WORKFLOW.md)，沿用原任务 ID 与旧脚本，不挂接到新的调度器任务。
