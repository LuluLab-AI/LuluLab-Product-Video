# 本地 v3 爆款知识接口

默认数据库：`~/.lululab/viral_knowledge/viral.db`；`LULULAB_VIRAL_DB` 可覆盖。生成 Skill 仅读已审核的 `creative_patterns`、`execution_patterns`、相关 Bundle 与有证据的反馈。历史 v2 Bundle 和原子资产保留，但未复核到 v3 的记录不能直接成为 KNOWLEDGE 创意依据。当前正式库若 `creative_patterns=0`，AUTO 明确回退 DIRECT；显式 KNOWLEDGE 停止并报告。

## Product Profile

根据产品图可见事实和用户说明生成内部文件，字段：

```json
{
  "industry": "beauty",
  "category": "lip-gloss",
  "productType": "唇彩",
  "painPoints": [],
  "sellingPoints": ["可见粉色珠光"],
  "useScenarios": [],
  "problemMechanisms": [],
  "solutionMechanisms": [],
  "interactionMechanisms": [],
  "proofMechanisms": [],
  "possibleProofTypes": [],
  "targetAudience": "",
  "targetCountry": "美国",
  "creativeRequirement": "",
  "confirmedFacts": [
    {"id":"F1","fact":"产品图可见粉色珠光","source":"product-image","mechanisms":[]}
  ]
}
```

机制标签须列在对应 `confirmedFacts[].mechanisms` 内，不能因想召回某 Pattern 而凭空补充。目标市场及受众以用户确认信息为准。产品画像中不再包含 `videoStyle`。

## 检索与策略

`python3 local/orchestrator.py prepare --request request.json --profile profile.json --strategy AUTO --output candidate_pack.json`

内部召回结合结构化机制、BM25 词面分和本地同模型 embedding（若已有）；没有向量时不谎称语义检索已启用。召回最多 80，输出供智能体重排的短名单最多 20；排序以产品适配、Pattern 关系、物理可执行性、AI 可生成性为主，不扣使用次数，不重复叠加原片热度。趋势留在 Builder 的发现阶段。所有粗召回分数不能取代 AI 语义重排。

返回 `strategyRequested`、`strategyUsed`、`fallbackReason`、`status`、`diagnostics` 和 `candidates`。每个候选包含 Creative Pattern、Execution Pattern、独立来源数、知识评分及反馈样本数。全部零匹配是诊断而非高相关候选；需要重新画像，或由 Planner 明确说明真实跨品类迁移理由。样本少于 5 的成片反馈不参与排序。

## Planner → Execution Spec → Prompt

先读 [Creative Blueprint 合同](creative-blueprint-contract.md)，形成每条不同的创意假设并逐项映射 Pattern 的必要关系。读 [Execution Spec 合同](execution-spec-contract.md) 写可执行时间轴。正式 Prompt 输入仅为产品事实、达人事实、Render Spec、Execution Spec 和硬约束，不再包含原始候选包或全部证据。可执行命令见 [SKILL.md](../SKILL.md)。

旧 `scripts/viral_knowledge.py search` 对含 v3 表的正式库会走 v3 检索；旧 `build-context` 仅用于历史测试，不得作为 v3 生产路径。
