# Execution Spec（本地 v3）

每个 beat 还必须包含 `initialState`、`endState` 非空状态对象；相邻节拍状态变化时填 `transitionExplanation`，说明可见动作或合理剪辑，不能让产品或道具瞬移。

Creative Blueprint 先定创意，Execution Spec 再定可拍的第一帧、连续动作、镜头和声音。`local/orchestrator.py validate-spec` 检查与来源 Pattern、时长和必要关系是否一致。不要把原片的绝对秒数照搬；可参考来源 Execution Pattern 的比例时间、镜头不变量、生成风险和 fallback。

最小结构：`{blueprintId,format,duration,hookChannel,buyReason,endingIntent,voiceDescription,productContinuity,creatorContinuity,noOnScreenText,beats[]}`。用户明确指定语言时，另写 `mediaLanguage`（优先 BCP-47）；未指定时按目标市场确定并写入。每个 beat：`{beatRef,start,end,visual,action,camera,audio,speech?,screenText?}`。首块从 0 秒开始，无缝覆盖全片；每块不超过 4 秒。`speech={role,text}` 必须是真正要说的成片语言台词，不是声音设定；允许新增的 `screenText` 同样使用成片语言。明确无口播仅在用户选择时允许。文字型 Hook 与无屏幕文字冲突时转为可理解的口播或重选 Hook；语义型 Hook 不能退化为泛泛表情。

每个 `requiredRelationship` 指到真实的 beatRef；Hook 前 3 秒落实，所有 Blueprint 动作和选中的 Proof/CTA 落实。产品/人物起止状态与相邻镜头必须可连续解释。`buyReason` 和 `endingIntent` 要在最终 Prompt 中可核对；不编造优惠、价格或功效。不能实现时返回 Planner 重选，不由 Prompt Generator 即兴补剧情。

`voiceDescription` 与 `promptLanguage` 对齐：中文采用中文声音句；其他语言采用可解析的 `Fixed voice(Role): language=...; accent=...; adult gender=...; age impression=...; core timbre=...; pitch=...; base speaking rate=...; delivery style=....`，字段值和描述使用对应交互语言。非中文 Spec 不携带中文声音标签供后续原样复制；`mediaLanguage` 及 `speech.text` 独立表示成片语言。
