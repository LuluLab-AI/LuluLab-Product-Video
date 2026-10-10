# 生成前后质量合同 v5.5

默认 UGC 有口播；明确选择无口播时才使用内部 `qualityRequirements={"speechMode":"none","explicitNoSpeechRequest":true}`。默认 `speechMode=required`。`targetLanguage` 首先取用户明确指定的成片语言（尽量标准化为 BCP-47，如 `es-US`）；未指定时才由目标市场确定，默认美国可用 `en-US`。交互语言不得覆盖 `targetLanguage`。除英语的初步脚本检查外，其他语言及画面文字仍需语义和成片审查，不冒充自动语言识别。用户要求保留在原四段输入的 creativeRequirement，内部配置不能冒充用户选择。

## Prompt 与执行接口

每个时间块使用可解析的稳定标签：中文可用 `口播（角色名）：“实际目标语言台词”` 或 `旁白（角色名）：“实际目标语言台词”`；其他交互语言使用 `Dialogue(Role): "actual media-language line"` 或 `Voiceover(Role): "actual media-language line"`。非中文声音句使用 `Fixed voice(Role): language=...; accent=...; adult gender=...; age impression=...; core timbre=...; pitch=...; base speaking rate=...; delivery style=....`，标签和字段名保持稳定，字段值及其余描述使用 `promptLanguage` 对应语言。非中文无口播使用 `No character speech in this segment.`。`qualityRequirements.promptLanguage` 是规范化 BCP-47 叙述语言，独立于 `targetLanguage`；历史任务未声明此项时仍可兼容读取。角色必须匹配独立的固定声音句。英语每秒≤3.5词、中文每秒≤5字只是上限，安排呼吸与停顿；涂唇时用旁白或静音。画面无字幕不意味着无口播。

输出仍为 videoPrompts/creatorPrompts。执行任务额外携带 `qualityRequirements`、`qualityReview`、`promptMode`，知识库模式还携带 build-context 解析后的 `creativeBlueprint`；不得写进产品输入四段结构。

执行 job 中 v3 使用 `strategyRequested`、`strategyUsed`（DIRECT 或 KNOWLEDGE）、`fallbackReason`；AUTO 回退 DIRECT 必须写明原因。KNOWLEDGE 还携带 `creativeBlueprint`、`executionSpec` 及可选 `knowledgeDb` 绝对路径；提交时重新读取已审核 v3 Pattern，不信任旧候选文件。旧 `promptMode` 仅为历史任务兼容。

`qualityReview` 由实际阅读最终提示词的智能体填写，不由脚本自动宣告语义通过：

- `promptDigest`：`quality_gate.digest(segments)`；任一镜头修改后重新审核。
- `reviewer / reviewedAt / semanticPassed`：真实审核来源、ISO时间、结论。
- `states`：按时间顺序逐时间块 `{beatRef, initial, visibleAction, end, transitionExplanation}`。beatRef 为 `segmentId:该段从1开始的时间块编号`。initial/end 是非空状态对象，例如 `{applicator:"瓶内",bottle:"打开"}`；visibleAction 必须引用镜头中的实际文字。相邻状态不同需解释可见操作或合理剪辑，不能用解释掩盖瞬移。
- `hook / buyReason / ending`：各含 `{beatRef, quote, rationale}`，quote 是该块实际文字。Hook 在全片前3秒；购买理由必须基于产品事实。ending 另有 `origin=original/source/no-cta`；source 要有真实 CTA assetKey，原创软引导不得伪装来源事实，禁止虚构促销。

## 知识库落实

HOOK 资产保存 `expressionChannels=[speech/text/action]`；STRUCTURE 保存 `requiredStages`。
Blueprint 新增 `hookRealization={channels,message,beatRef,adaptationReason}` 和 `structureRealization=[{stage,beatRef,quote,rationale}]`。这些字段经 build-context 保留到执行任务。语义型 Hook 不可用泛泛转脸替代，文字禁用时转为口播；结构必要阶段不适合当前产品时重新选择结构，不能删掉核心机制仍算采用。
文字型Hook必须以 `On-screen text: "actual media-language text"`（英文提示词）或 `屏幕文字：“实际文字”`（中文提示词）进入时间块；策划说明里的同一句话不算落实。

`generationReadiness=limited` 的每项限制须在所选资产的 `limitationChecks=[{limitation,handling}]` 逐条对应并说明处理。needs_review 禁止使用。这些检查只证实合同齐全，智能体仍须核对台词、动作、可读性和真实卖点。
主Bundle为limited时同样填写Blueprint.primaryLimitationChecks，不能仅检查资产而忽略整片约束。
当retrievalDiagnostics.allZeroMatch=true，先重做产品画像；确有跨品类迁移依据时写zeroMatchReview={decision:"cross-category-transfer",reason,productGrounding}，仍需语义重排与物理依据，不把候选分包装成高语义相关性。

## 执行

先运行 `python3 scripts/local_prompt.py validate --display-language en --input result.json --model seedance-2-fast --target-duration 20 --requirements requirements.json`。
编写执行 job 后运行 `python3 scripts/quality_gate.py --jobs job_01.json job_02.json`。所有正式渠道入口也会校验；用户明确改用其他渠道时，仍先运行该独立门禁，不绕过质量检查。
批量比对实际 Hook、台词、场景、动作和结尾；共享达人和产品不算重复，但不能只换资产编号。Planner 还需对比创意假设与 requiredRelationships 的实现，程序文本相似度只是辅助。生成前检查 `executionSpec` 是否完整进入最终 Prompt；不能由 Prompt Generator 即兴更换结构。

## 成片验收

运行 `review_render.py --job job.json --video final_video.mp4 --transcript asr.json --visual-review render_review.json`。
ASR 需含 `mediaSha256` 和带 start/end/text 的 segments；推荐保留 no_speech_prob/avg_logprob，歌曲识别不得当产品台词。ASR必须来自对应成片，可用已有本地模型，不自动上传或下载新模型。
render_review 含 `mediaSha256 / promptDigest / reviewer / reviewedAt / checks`；checks 为 hook、actions、product、continuity、speechAudible、dialogueComplete，逐项实际核查。明确无口播作品最后两项表示“符合明确无口播要求”，备注说明。
另需inspectionMode=direct-video-and-audio、evidenceWindows=[{start,end,observation}]记录实际听看范围；仅有布尔勾选不得通过。不能进行实际动态/声音检查时保持needs_review。
时间窗需按顺序覆盖全片，无超过0.15秒的缺口；每项有有效起止时间和具体观察，不接受空对象。
无转写或未实际审看时返回 needs_review，不可用抽帧或音轨存在冒充通过；口播缺失、动作/产品错误为失败。发现失败保留记录，不自动付费重试。使用现有失败样本做离线测试不触发生成。
