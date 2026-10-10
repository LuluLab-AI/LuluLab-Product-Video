---
name: ugc-product-video
description: Create local product videos from product images using LuluLab CLI and Seedance. Follow the user interaction language across agents; select the video language independently.
license: GPL-3.0-only
metadata:
  version: "v6.2.2"
---

# Local Product Video / 本地带货视频 v6.2.2

## Response language / 交互语言

At the start of every task, resolve `interactionLanguage` in this order across Codex, Claude Code, WorkBuddy and other agents:

1. The user's explicit response-language instruction. A video-language request changes only `mediaLanguage`.
2. The primary language of the user's current task message. Ignore quoted material, code, JSON, video dialogue and packaging text when identifying it. Use the agent's existing language understanding; no detection API is needed.
3. The established task response language, including retries and recovery, when no new language switch was requested.
4. The agent's default response language, only if available from trusted configuration.
5. English (`en-US`).

Do not infer the agent default from operating-system locale. Product images, attachment names, paths, tool output, target market and Skill text are not evidence of user language. A numeric choice, file or link without task prose preserves the current context. An explicit user switch applies to subsequent responses and prompts; historical results need no automatic translation.

Maintain a context such as `{"interactionLanguage":"en-US","languageSource":"user_message","promptLanguage":"en-US"}`. Normalize language tags with `core.language.normalize_language` and use BCP-47 without a language whitelist. `promptLanguage` equals `interactionLanguage`. Carry the context through planning, prompt building, confirmation, quality review, retries and task recovery. Tool output never changes it.

Write all user-visible prose, including welcome, collection, complete confirmation card, questions, progress, creative plan, storyboard, creator and camera descriptions, quality report, errors, retry explanations and final delivery, naturally in `interactionLanguage`. CLI `errorCode` values are language-neutral; render them in `interactionLanguage` and keep `diagnostic` internal for debugging. Never paste raw Python or Node.js diagnostics into the user-facing answer. Keep JSON keys, API parameters, filenames, paths, commands, model names, parser labels, brand names and proper nouns stable.

## Media language / 成片语言
- 另行确定**成片语言**：用户明确指定的视频口播、旁白、屏幕文字或允许新增的图片文字语言优先；未指定才按目标市场选择自然的当地语言。交互语言、提示词叙述语言、产品图原有包装文字都不能覆盖用户指定的成片语言。市场与语言不是一一对应；例如美国市场也可按用户要求生成西班牙语内容。
- 将成片语言明确写入规划、Execution Spec、视频和达人图片 Prompt、质量要求 `targetLanguage` 与人工成片验收。台词必须直接用成片语言写出，不用交互语言占位再让模型翻译；允许文字时也直接写目标语言原文。默认不新增字幕或图片标签；若用户要求文字，按其指定语言制作，并核对可读性与拼写。参考产品图上已有的商标/包装文字按产品真实性保留，不擅自翻译。
- `scripts/local_prompt.py build` 必须显式传 `--display-language <interactionLanguage>`，例如 `pt-BR`、`zh-CN` 或 `en-US`；用户明确指定成片语言时另传 `--media-language <mediaLanguage>`。CLI 无显式显示语言时安全默认英文。JSON Key 和 `[0s-3s]` 时间轴保持不变。中文沿用中文结构标签；其他语言使用固定英文结构标签 `Fixed voice`、`Dialogue`、`Voiceover`、`On-screen text`、`No character speech in this segment.`，这些属于代码解析字段。结构标签之外的声音字段值、场景、镜头、人物和达人描述均按交互语言自然书写；实际台词及新增文字按成片语言。

只处理本地工作流，不引用云端 Prompt、Webhook、数据库实现或生成编排。继续使用现有视频渠道、达人参考图、Segment 限制、下载和拼接能力；本次重构不提交计费任务。开始规划或提交前读 [质量合同](references/quality-contract.md)，知识库模式还须读 [v3 知识接口](references/viral-knowledge-interface.md)、[Creative Blueprint 合同](references/creative-blueprint-contract.md) 和 [Execution Spec 合同](references/execution-spec-contract.md)。

## 核心链路

`用户确认的产品事实 → Product Profile → v3 Hybrid Retrieval → AI Creative Planner → Creative Blueprint → Execution Spec → 模型 Prompt → Prompt Quality Gate → 视频生成 → Render Review → Generation Feedback`。

- 本地用户不再选择「UGC／剧情」类型。Planner 按真实产品与知识机制选择 demonstration、micro_drama、review、comparison、tutorial、reaction、transformation、challenge 或 hybrid；它们只是内部创意标签，不是用户配置。
- 普通请求默认策略为 `AUTO`：优先使用经过 v3 审核且适配的知识；若无可用知识，记录 `strategyUsed=DIRECT` 与 `fallbackReason` 后创作原创基线。用户明确要求知识库时采用 `KNOWLEDGE`，无可用知识则停止并说明，不静默回退。用户明确要求对照实验或调试时可指定 `DIRECT`，不得查询数据库。
- Builder 与生成 Skill 只共享产品事实、Creative Pattern、Execution Pattern、Blueprint、Execution Spec 和质量合同；本 Skill 不修改知识库的历史审核结论。
- `Creative Pattern.requiredRelationships` 是整体因果约束，不能把 Hook、Action、Proof 任意拼贴；`Execution Pattern` 是节奏、镜头、声音与风险的来源，不是原片绝对秒数模板。
- Prompt Generator 只翻译已审核的 Execution Spec，不能重新决定形式、Hook、场景、冲突、Proof、CTA 或叙事。Direct 不使用知识库，仍需先在内部形成原创创意假设和执行节拍。
- 原创带货默认有成片语言的实际口播/旁白台词；仅用户明确选择整条无口播才允许无口播。无字幕不等于无声音。视频生成后按 [成片验收](references/quality-contract.md) 动态看听，文件下载成功不是质量通过。

## 用户确认与输入

未收到产品图时按交互语言请求产品图。产品名称、卖点、用途只取自用户说明和图片可见事实；不得编造成分、功效、认证、参数、销量、价格或优惠。目标市场默认美国，不得由对话语言推断。收到产品图后按交互语言展示以下**对应的一整张确认卡**，已指定项标注当前选择；用户确认后执行，不重复确认。以下中英文卡是格式示例；其他语言按该语言的自然表达生成同样完整的字段、四个模型选项和两个操作选项，不从图片、文件名或 Skill 原文选择语言。

Resolved interaction language: Chinese / 中文交互：

```text
已识别产品（可修改）
名称：{已确认}
可见/已知卖点：{最多3项}
市场：美国（默认，可修改）
成片语言：{用户指定语言；未指定时按目标市场默认，可修改}
受众：{已确认或待确认}

模型：
1. Seedance 2 Fast（默认）
2. Seedance 2 Mini
3. Seedance 2
4. Seedance 2.5
时长：4–60秒（默认15秒）
数量：1–10条（默认1条）
达人：AI生成（默认）／用户提供
创意策略：AUTO（默认）；用户明确指定时可选 KNOWLEDGE 或 DIRECT
特殊要求：{用户原话或无}
[1] 按当前配置继续
[2] 修改配置
```

Resolved interaction language: English / 英文交互：

```text
Identified product (editable)
Name: {confirmed name}
Visible/confirmed selling points: {up to 3}
Target market: United States (default; editable)
Video language: {user-selected language, or natural local language for the target market; editable}
Audience: {confirmed or awaiting confirmation}

Video model:
1. Seedance 2 Fast (default)
2. Seedance 2 Mini
3. Seedance 2
4. Seedance 2.5
Duration: 4–60 seconds (default: 15 seconds)
Number of videos: 1–10 (default: 1)
Creator: AI-generated (default) / User-provided
Creative strategy: AUTO (default); KNOWLEDGE or DIRECT only if explicitly requested
Special requirements: {user's request or None}
[1] Continue with these settings
[2] Change settings
```

Use the selected language for any product-image request before this card and for every later configuration-change prompt. Preserve the current selections and the video-language row. Changing only the interaction language does not change video language; changing only video language does not change the interaction language.

原本四个顶层输入名称保留：`productBrief`、`userConfig`、`creativeRequirement`、`creatorBrief`。其中 `userConfig` 只需 `videoModel` 和 `duration`；旧 `videoStyle` 若出现在历史请求中仅兼容读取，不能驱动本地创意分支。生成数量只在本地循环，不得加入 `userConfig`。内部的 Product Profile、Candidate Pack、Blueprint、Execution Spec 和质量审核不得写入最终 `videoPrompts/creatorPrompts` 输出。

## 本地规划与检索

1. 用户事实生成内部 Product Profile，字段见 [v3 知识接口](references/viral-knowledge-interface.md)。机制标签必须由带来源的 `confirmedFacts` 支撑。缺依据的机制或卖点保持未知，不为命中数据库而补造。
2. 运行 `python3 local/orchestrator.py prepare --request request.json --profile profile.json --strategy AUTO --output candidate_pack.json`。正式库默认 `~/.lululab/viral_knowledge/viral.db`，可用 `LULULAB_VIRAL_DB` 覆盖。只从已批准的 v3 Creative/Execution Pattern 检索；旧 Bundle 可保留历史但不是 v3 生成依据。
3. Hybrid Recall 先比较结构化机制和 BM25；只有本地已有同模型向量时才加语义向量分，不自动下载模型或调用云端服务。原始候选最多80，交给智能体语义重排的短名单最多20。全部零匹配必须给出诊断并重新画像或证明跨品类迁移，不宣称高相关。使用次数不降权，原视频热度不在生成端重复排序；有效成片反馈至少5条才可入排序。
4. Planner 对每条提出不同的 `creativeHypothesis`，按产品适配、Pattern 必要关系、Proof 物理可执行性及源限制选 Pattern/资产，生成 Blueprint。批量不允许只换台词或 ID；先运行 `python3 local/orchestrator.py validate-plan --candidate-pack candidate_pack.json --blueprints blueprints.json --count N`。
5. 再依据 [Execution Spec 合同](references/execution-spec-contract.md) 为每条写明第一帧、全局节拍、人物/产品起止状态、镜头、实际台词、Hook 渠道、购买理由和结尾意图。运行 `python3 local/orchestrator.py validate-spec --request request.json --candidate-pack candidate_pack.json --blueprint blueprint_01.json --authored-spec authored_spec_01.json --output execution_spec_01.json`。
6. 只把产品事实、达人事实、Render Spec、已核验的 Execution Spec 和硬约束交给 Prompt Generator：`python3 scripts/local_prompt.py build --input request.json --execution-spec execution_spec_01.json --display-language <interactionLanguage>`。用户明确指定成片语言时另加 `--media-language <mediaLanguage>`。不得塞入整包候选、全部 Evidence、来源 JSON 或原始 Bundle。Direct 模式不用 `--execution-spec`，由本地模型先原创规划。
7. 生成 JSON 后运行 `local_prompt.py validate --display-language <promptLanguage>`（与 build 相同）与 `quality_gate.py --jobs ...`。执行 job 声明 `strategyRequested/strategyUsed/fallbackReason`；KNOWLEDGE 还绑定 `creativeBlueprint`、`executionSpec`、`knowledgeDb` 和审核记录。正式提交入口必须通过同一门禁。修改任何最终 Prompt 都要重审。重试和恢复沿用已保存的语言上下文。
8. 成片之后运行 `review_render.py`，实际听看口播、动作连续、Hook、产品和购买理由。按 [反馈合同](references/feedback-contract.md) 保存有证据的生成反馈；失败不自动付费重试。提示词校验通过与成片质量通过分开报告。


## 输出契约保持不变

```json
{
  "videoPrompts": {
    "summary": "",
    "segments": [{"segmentId": 1, "title": "", "duration": 10, "prompt": ""}]
  },
  "creatorPrompts": {
    "summary": "",
    "creators": [{"creatorId": 1, "role": "", "appearsInSegments": [1], "consistencyReason": "", "prompt": ""}]
  }
}
```

## 视频提示词展示规范

生成并校验 `videoPrompts` 后，必须把完整视频提示词以适合人阅读的 Markdown 展示给用户；展示层不得直接倾倒原始 JSON，也不得把整段 Prompt 挤在一个长段落中。JSON 文件和执行 job 继续保留原输出契约，展示排版不修改提交语义。

- 单条或批量任务都按“视频 → Segment”分组。每条视频先显示视频编号和 `videoPrompts.summary`；每个 Segment 单独显示 `title` 与 `duration`。
- 每个 Segment 的完整 `prompt` 放进独立的 `text` 代码块，不截断、不省略为摘要。代码块内使用真实换行，不显示字面量 `\n`。
- Prompt 内按语义换行：参考图职责一段；人物、产品、场景、光线、机位和初始状态一段；固定声音或无口播声明独占一行；每个 `[0s-3s]` 时间块各占一行；结尾限制独占一行。相邻部分之间可留一个空行。
- 不为美化而改写台词、时间点、产品事实、动作或限制；展示文本必须与通过校验并实际提交的 `segments[].prompt` 一致，只允许调整空白和换行。
- 达人图 Prompt 与视频 Prompt 分开显示；除非用户明确要求，不展示母提示词、内部 Creative Blueprint、质量审核 JSON 或执行 job JSON。

展示格式（中文交互）：

````markdown
### 视频 1

{videoPrompts.summary}

#### Segment 1｜{title}｜{duration} 秒

```text
{参考图职责}

{人物、产品、场景、光线、机位和初始状态}

{人物固定声音句或“本段无人物口播。”}

[0s-3s] {画面、动作、声音与台词}
[3s-6s] {画面、动作、声音与台词}

{结尾限制}
```
````

English interaction uses the same validated `summary`, `title`, and `prompt` values without translating or rewriting them in the display layer. Other interaction languages follow the same rule: localize headings, labels and duration units naturally, while keeping the validated prompt unchanged. Only headings, labels, and duration units change:

````markdown
### Video 1

{videoPrompts.summary}

#### Segment 1 | {title} | {duration} seconds

```text
{complete validated segments[0].prompt, preserving real line breaks}
```
````

Display creator-image captions, reference-image roles, quality findings, failures, recovery steps, and delivery summaries in the same interaction language. Preserve JSON keys and timeline notation. English prompts must use English voice/speech labels and field descriptions. Do not introduce Chinese validation markers. Dialogue and existing packaging text can remain in their independently selected/original language.

## 模型与时长映射

本地不再向用户提供 UGC／剧情类型开关；旧 `videoStyle` 只兼容历史请求。内部创意形式由 Blueprint 决定，不映射到旧固定母提示词分支。

逻辑模型与 provider 映射保持原 Skill：

- Seedance 2 Fast → `seedance-2-fast` → `seedance2.0fast_vip`
- Seedance 2 Mini → `seedance-2-mini` → `seedance2.0mini_vip`
- Seedance 2 → `seedance-2` → `seedance2.0_vip`
- Seedance 2.5 → `seedance-2-5` → `seedance2.5`

LuluLab CLI 使用上述逻辑模型 ID（`seedance-2-fast`、`seedance-2-mini`、`seedance-2`、`seedance-2-5`）提交。用户明确改用小云雀或即梦时，前三个模型不得静默改用非 VIP 变体；所选 CLI 必须在提交前通过该命令的 `--help` 明确声明对应 provider ID，未声明则该渠道不可用。

前三个单段 4～15 秒；Seedance 2.5 单段 4～30 秒。总时长 4～60 秒，拆成尽量少的合法 Segment。

## 登录与积分

- 默认视频渠道为 LuluLab CLI（`lululab_cli`）。首次计费提交前运行只读 `node scripts/lululab_cli.mjs user --credits` 检查余额；任务全部终态后再次查询并报告余额。
- LuluLab 凭证优先从 `LULULAB_API_KEY` 读取；兼容旧 `LINGZHI_API_KEY`、`LZSTUDIO_API_KEY` 或现有 `~/.ugc-product-video/config.json` 读取。不得把 API Key 写入任务 JSON、日志或回复；缺失时停止并提示用户在本机配置，不在普通对话中回显凭证。
- 用户明确改用即梦时使用官方 OAuth 登录；需要登录时提示用户运行 `dreamina login`，不索取或保存凭证，并在首次计费操作前运行 `dreamina user_credit`。
- 达人参考图默认使用 LuluLab Node.js CLI `task submit/fetch`（`ImageGenV2`，模型 `gpt-image-2-5-sunburst`）；视频使用同一 CLI 的 `VideoGenV2`。LuluLab 生图失败时保留原 task ID，只恢复查询，不自动改用其他生图平台。
- LibTV、小云雀和即梦仅在用户明确指定时使用各自已有的本地登录状态与检查逻辑。

### 视频提示词质量硬规则

- Segment 只是受模型单段时长限制的生成任务容器，不是 Hook、Problem、Solution、Proof 或 CTA 等内容阶段。先确定最少 Segment 数，再把完整故事节拍按时间分配进去。
- 选择微剧情时，按其 Blueprint 的必要关系建立具体节拍；其他形式可采用结果前置、实测、教程等不同结构，不套固定“痛点→产品→满意”。每个时间块推进叙事、产品信息或有效转化，禁止用走路、空镜、重复惊讶或无信息慢镜头凑时长。
- 每个 `segments[].prompt` 必须使用 `[0s-3s]` 这类连续时间轴：从 0 秒开始，无空档、重叠或倒序，结束时间等于 Segment 时长，单个时间块不超过 4 秒。每块只安排一个核心镜头或连续动作链。
- 每个 Segment 都是独立提交给模型的任务。每段都要完整写明本次任务中产品图和达人图的职责、人物、产品、场景、光线、机位及本段初始状态。使用绝对描述，禁止“上一段”“下一段”“承接”“继续前段”“同一个达人”“同一人物”“相同人物”“同上一人物”或“声音同上段”等跨段引用。
- 声音与台词格式跟随提示词叙述语言，台词内容独立跟随成片语言。英文声音句：`Fixed voice(Role): language=...; accent=...; adult gender=...; age impression=...; core timbre=...; pitch=...; base speaking rate=...; delivery style=....`；台词：`Dialogue(Role): "actual media-language line"` 或 `Voiceover(Role): "actual media-language line"`；无口播：`No character speech in this segment.`；允许新增文字：`On-screen text: "actual media-language text"`。英文声音字段及描述全部用英文。
- 中文声音句：`人物固定声音（角色名）：语言=...；口音=...；成年性别=...；年龄感=...；核心音色=...；音高=...；基础语速=...；表达风格=...。`；台词使用 `口播（角色名）：“实际台词”` 或 `旁白（角色名）：“实际台词”`；无口播使用 `本段无人物口播。`；允许文字使用 `屏幕文字：“实际文字”`。
- 有台词的每个 Segment 都独立写完整声音句；同一角色跨 Segment 的声音句，这一整句必须逐字相同，当段情绪只写入时间轴。校验器兼容中英文两套语法和历史中文提示词；新非中文任务使用上述稳定英文结构标签，叙述与字段值按交互语言。`qualityRequirements.promptLanguage` 写入规范化 BCP-47 值，与 `--display-language` 一致，供提交门禁检查；`targetLanguage` 仍单独表示成片语言。
- `validate_result()` 除结构和时长外，必须校验连续时间轴、跨段引用禁词、声音特征完整性及同角色跨 Segment 的逐字一致性。校验失败不得进入计费生成。

输出契约保持：

```json
{
  "videoPrompts": {
    "summary": "",
    "segments": [{"segmentId": 1, "title": "", "duration": 10, "prompt": ""}]
  },
  "creatorPrompts": {
    "summary": "",
    "creators": [{"creatorId": 1, "role": "", "appearsInSegments": [1], "consistencyReason": "", "prompt": ""}]
  }
}
```

## 生成流程

### AI 达人图

- 未提供达人图即使用 `creatorMode: "auto"`；生成 Seedance 视频前，必须先生成一张 9:16 的真人多视角达人产品参考图。单条任务保存到该视频目录；批量任务默认保存到批次根目录并供所有视频共享。该前置步骤不可跳过。
- 自动设计达人时，必须综合使用用户已确认的目标市场、目标受众、产品名称、可见卖点、产品风格和自定义创作要求。达人的年龄感、整体气质、妆发、体型与穿搭应适合当地内容消费习惯、产品使用场景和受众定位；用户明确提供的达人要求优先级最高。
- 目标市场只用于判断内容语境和本地化风格，不得仅凭国家或地区套用种族、肤色、五官或文化刻板印象，也不得虚构用户未提供的职业、身份或生活方式。
- 达人必须具有真实自然的普通 UGC 创作者质感：自然表情与站姿、真实人体比例和皮肤纹理、生活化妆发与合身日常服装。避免过度磨皮、夸张身材、僵硬姿势、塑料皮肤、奢华影棚模特感和明显 AI 面孔。
- 生成达人产品参考图时，必须把 `productBrief.productImages` 中所有有效产品图作为实际生图参考输入；不得只在文字 Prompt 中描述产品。运行图片任务前逐张上传产品图，并按原顺序作为 `referenceImages` 传入 `ImageGenV2`。
- 多视角达人产品参考图必须是单张四视图参考板，只呈现同一个达人。四个清晰分区固定为：`人物脸部特写`、`人物全身正面`、`人物全身侧面`、`人物全身背面`；不得用三分之四侧面替代标准侧面，也不得缺少背面。脸部特写需完整显示五官、发际线、双耳附近和自然皮肤纹理，不裁切关键脸部特征；三个全身视图均从头顶完整显示到鞋底。四个视图的身份、脸部特征、肤色、发型、体型、服装、鞋履和固定配饰必须完全一致。使用自然表情与站姿、浅色干净背景、均匀光线、统一比例，不添加文字、Logo、边框、分隔标签或额外人物。
- 产品必须融入三个全身视图，并严格保留产品图中可见的颜色、版型、结构、图案、材质观感与部件。穿戴类产品默认由达人正确穿戴，成套服装必须完整穿着；手持或使用型产品由达人自然持有或使用；不适合穿戴或手持的大型产品与达人同场展示并保持可信比例。脸部特写以锁定人物身份为首要目标，不强行塞入与脸部无关的产品；只有产品本来用于脸部、头部或能自然出现在近景中时才展示，并与全身视图保持一致。不得把产品替换成普通占位服装或凭空补造看不见的细节。
- 单条任务使用该条视频的 `creatorPrompts.creators[0].prompt`；批量任务默认让各条 `creatorPrompts` 描述同一达人和同一产品穿戴/使用方式，并用首条有效的 `creatorPrompts.creators[0].prompt` 生成共享参考图。将 Prompt 保存到 UTF-8 文本文件，通过 `scripts/local_creator_image_generate.py` 生成；不调用内置生图工具、Dreamina 或远程 PromptGen。
- 图片任务使用随 Skill 分发的 LuluLab Node.js CLI，工作流 `ImageGenV2`、默认模型 `gpt-image-2-5-sunburst`、分辨率 `1K`、画幅 `9:16`。明确指定已支持的 `gpt-image-2-5-flare` 时可用 `--image-model` 覆盖，并保持提交参数与任务记录一致；失败不得自动切换模型。首次计费图片提交前运行只读 `node scripts/lululab_cli.mjs user --credits` 检查积分；本地凭证只由 CLI 按现有优先级读取，不写入 Prompt、任务文件、日志或聊天。
- 生图命令：`python3 scripts/local_creator_image_generate.py --prompt-file <达人图Prompt.txt> --reference-image <产品图1> [--reference-image <产品图2>] --output <creator.png> --report <creator-image-task.json>`。产品图上传成功后、任务提交前持久化不确定状态，取得 task ID 后原子保存；查询或下载失败时恢复原 task ID，不重复计费提交。提交结果不确定且没有 task ID 时停止，告知用户；已知任务用 `--resume-task-id <id>` 恢复。图片任务失败时停止该条流程，不自动切换模型或渠道。
- `creatorMode: "referCreator"`：直接使用用户提供的本地达人图，不生成额外达人图。
- 自动生成的多视角达人图在批量任务中默认只生成一张并跨视频复用。只有用户明确要求每条视频使用不同达人时，才逐条生成独立参考图。
- 多视角达人图生成并保存成功后，必须在进入 Seedance 视频生成前立即向用户显示。使用绝对本地路径以内联图片形式展示：中文交互用 `![多视角达人图](/absolute/path.png)`，英文交互用 `![Multi-view creator reference](/absolute/path.png)`；不得只发送文件路径。批量共享时按交互语言标明“全部视频共用”或 “Shared by all videos”；逐条生成时标明对应的视频编号。

### Seedance 视频

#### LuluLab 默认渠道

- 默认使用随 Skill 分发的 Node.js CLI：`scripts/lululab_cli.mjs`，无需 npm 安装或原生二进制。macOS、Windows 使用同一入口，需要 Node.js ≥20；优先使用 `LULULAB_NODE` 指定的 Node 路径，否则使用 PATH 中的 `node`。`LULULAB_CLI` 仅可覆盖为 `.mjs` 入口；旧二进制路径需取消或更新。检测阶段只检查本地入口和命令帮助，不读取凭证或联网。旧 `lingzhi_cli`、`lululab_cli` 状态沿用原 taskId 查询，不重新提交；provider 标识继续使用 `lululab_cli`。
- API 契约见 [Node.js API 适配](references/lululab-node-api.md)，默认服务地址 `https://customer.lululab.ai`；`LULULAB_API_BASE_URL` 可显式选择测试服务。API Key 原值放入 `Authorization` 请求头，不加 Bearer，不传入命令参数。完整请求映射与上传约定见 [Node.js API 适配](references/lululab-node-api.md)。
- 品牌由灵智工坊改为 LuluLab；workflow ID、接口和输入/输出协议保持不变，继续使用既有 `VideoGenV2` 协议：参考图按产品图、达人图的既定顺序去重后逐个 `upload`，转换 `location` 为参考媒体 `url` 并保留 `mimeType`；不把上传链接的 `expiresAt` 当作媒体的 `expiredAt`。通过 `node scripts/lululab_cli.mjs task submit --workflow-id VideoGenV2 --input <JSON>` 提交，输入字段为 `model`（逻辑模型 ID）、`prompt`、`duration`、`aspectRatio`、`resolution`、`referenceImages`（媒体对象数组）。工作流 ID 内置，`LULULAB_VIDEO_WORKFLOW_ID` 仅为可选高级覆盖项，无需用户配置；客户端不导入、部署或编排服务端工作流。

- 在任何视频计费提交前运行 `python3 scripts/video_cli.py preflight --model <逻辑模型>`；默认只检测并使用 `lululab_cli`，不可因 LuluLab CLI 不可用而自动切换其他渠道。只有用户明确指定 LibTV、小云雀或即梦时才加 `--provider libtv_cli`、`--provider xiaoyunque_cli` 或 `--provider dreamina_cli`。
- LuluLab 必须通过 `node scripts/lululab_cli.mjs task submit --help` 确认 `--workflow-id`、`--input`，通过 `node scripts/lululab_cli.mjs task fetch --help` 确认 `--id`。不要求 CLI 提供专门的 `video submit` 命令。用户指定即梦或小云雀时，仍须从 `multimodal2video --help` 与 `query_result --help` 核对精确 provider 模型 ID 和参数；明确指定 LibTV 时以其实时 CLI 帮助和模型 schema 为准。
- 检测与提交是两个阶段。检测不得安装、更新、登录或提交任务；用户确认配置即授权本轮首次视频生成，不再要求用户手动选渠道。
- 一旦任一 Segment 返回 LibTV 画布/节点或小云雀/即梦 taskId，整条视频锁定该 provider。失败、超时、网络错误、登录或余额异常均不得自动切到下一渠道重新提交；仅恢复和查询原 provider 的原任务。
- 当前选定渠道不可用、缺少本地凭证或积分不足时，不安装、不调用其他平台，也不提交付费任务。向用户说明 LuluLab CLI、本地凭证或积分的具体缺项，或请用户明确改用其他工具；手动交付逐段 Prompt 时列出参考图角色和可点击绝对路径。

#### 参考图与执行任务

- 每个 Segment 的 `referenceFiles` 至少包含产品图；`creatorMode: "auto"` 时同时包含自动生成的多视角达人图，批量任务默认向每条视频传入同一张共享图；`creatorMode: "referCreator"` 时包含用户提供的达人图。保持确定顺序并去重，不得静默丢弃参考图。
- 为执行层写入独立任务 JSON；这只是本地产物，不得加入本地提示词生成的四个顶层输入。格式为：

```json
{
  "projectName": "ugc-product-video",
  "videoModel": "seedance-2-fast",
  "aspectRatio": "9:16",
  "resolution": "720p",
  "segments": [
    {
      "segmentId": 1,
      "duration": 15,
      "prompt": "...",
      "referenceFiles": ["/absolute/product.png", "/absolute/creator.png"]
    }
  ]
}
```

上面仅示意视频执行字段；正式 job 还必须按 [质量合同](references/quality-contract.md) 加入 `strategyRequested`、`strategyUsed`、必要时的 `fallbackReason`、`qualityRequirements` 和绑定最终 Prompt 摘要的 `qualityReview`。KNOWLEDGE 还附当前已审核的 `creativeBlueprint`、`executionSpec` 与数据库路径。缺失或校验失败时不能提交。

#### LibTV

- 选中 LibTV 时必须完整读取已安装的 `libtv-cli` Skill，并以 `libtv --help`、相关子命令 `--help` 和实时模型 schema 为权威接口，不猜测参数或私有 HTTP 地址。
- 运行 `python3 scripts/libtv_batch_generate.py --job <任务JSON> --generation-approved`；需要指定工作区时可加 `--workspace-id <id>`，复用已有画布时可加 `--project-uuid <uuid>`。只检查计划时使用 `--plan-only`，该模式不创建画布、不上传、不提交计费任务。
- 编排器去重上传参考图，使用 CLI 返回的真实 `nodeKey` 建边并写入 `{{Node <nodeKey>}}` 占位符；先原子保存画布、节点和 provider 状态，再触发生成。
- `libtv node ... --run` 自行提交、轮询并等待终态；调用方直接等待命令退出，不额外轮询，不因 stderr 出现 taskId 而提前结束。
- 状态不确定时保留画布、节点和 `libtv-generation.json`，禁止自动重新运行节点。成功后下载各段，并向用户提供 `https://www.liblib.tv/canvas?projectId=<projectUuid>` 画布链接。

#### LuluLab、小云雀与即梦

- 默认 LuluLab CLI 运行 `python3 scripts/local_video_generate.py --job <任务JSON> --provider lululab_cli --generation-approved`。
- 选中小云雀时运行 `python3 scripts/local_video_generate.py --job <任务JSON> --provider xiaoyunque_cli --generation-approved`。
- 选中即梦时运行 `python3 scripts/local_video_generate.py --job <任务JSON> --provider dreamina_cli --generation-approved`。
- 三者都直接上传本地参考图。LuluLab CLI 使用逻辑模型 ID；小云雀与即梦使用“输入与模型映射”中的精确 provider 模型 ID。任务提交后原子记录 taskId，只轮询该 taskId；成功后下载结果。
- 提交调用状态不确定但未返回 taskId 时，写入 `submit_started_uncertain` 并停止，禁止自动重提；已有 taskId 时只恢复查询原任务。

#### 并发与输出

- 所有受支持模型的批量任务均允许并发生成，包括 `seedance-2-mini`、`seedance-2-fast`、`seedance-2` 和 `seedance-2-5`；最多同时运行 3 条完整视频工作流。批量数量不足 3 条时，按实际数量并发。
- 同一条视频内的多个 Segment 仍按编号顺序生成和拼接，不在单条视频内部并发 Segment。
- submitted、queued、querying、processing、running 等非终态任务都计入并发数；不得为了加速而超过 3 条。
- 某条并发任务返回 `ExceedConcurrencyLimit` 或其他终态失败时，保留其他任务继续运行并报告失败；不自动重复提交计费任务。

单条视频保存为 `segment_01.mp4` 等和 `final_video.mp4`。批量保存到 `video_01/`、`video_02/` 等子目录；同一条视频的多段按编号拼接，不得跨视频拼接。所有模型最多同时运行 3 条完整视频工作流。

## 结果与边界

- 部分失败时保留并展示所有成功结果，同时按编号说明失败阶段与已脱敏错误。
- 某条的必要阶段失败后，停止该条后续阶段，继续其他视频；不自动换模型、换 provider 或重复提交计费任务。
- 全部工作流进入终态后，按所选 provider 的能力查询结束积分并与结果、实际渠道一起展示。
- 不在用户确认前修改产品信息、类型、模型、时长、数量、达人方式或视频提示词配置。
- LuluLab API Key 只通过本机环境变量或既有私有配置读取；不得显示、记录到任务文件或经由 Prompt 传递。
