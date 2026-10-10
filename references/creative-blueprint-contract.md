# Creative Blueprint（本地 v3）

Blueprint 的 `assetKeys[]` 必须完整保留来源 Pattern 关联的原子资产。每个 `actions[]` 对应一项 `actionGrounding={action,factRefs,initialState,endState,physicalCheck}`，事实引用须来自当前 Product Profile 的 `confirmedFacts`；选 Proof 时还需 `proofGrounding={factRefs,physicalCheck}`。有限可用的 Bundle 或资产逐项填写 `limitationChecks={limitation,handling}`，待复核内容禁止进入规划。

由当前智能体在看过 Product Profile、已审核 v3 Pattern 候选和原片限制后撰写；`local/creative_planner.py` 只做可机械验证的关系、来源和批次差异检查，不能代替语义判断。运行 `local/orchestrator.py validate-plan`。

每条 Blueprint 至少包含：`blueprintId`、`patternKey`、`format`、`creativeHypothesis`、`hook`、`scene`、`conflict`、`actions[]`、`proof` 或 `proofOmissionReason`、`cta`、`ctaOrigin`、`relationshipMappings[]`。`format` 取 demonstration、micro_drama、review、comparison、tutorial、reaction、transformation、challenge、hybrid。`relationshipMappings` 与来源 `requiredRelationships` 一一对应，每项为 `{sourceRelationship,realization,beatRefs}`，不得删掉原机制再继续标记为采用它。所有产品卖点/Proof 用 `claimFactRefs` 引用当前产品 `confirmedFacts`。

CTA 可以省略。`ctaOrigin=original` 是原创软引导；`source` 必须提供真实 CTA 资产；`no-cta` 不得暗添购买引导。不能迁移来源价格、优惠、功效或销量。`CREATIVE_REFERENCE` 不能为当前产品提供 Proof 或来源 CTA。跨品类迁移以产品真实用法、可见状态和物理可执行性优先。

批量必须是不同创意假设及不同的 Hook/场景/冲突/动作/Proof 组合；换话术或资产 ID 不算差异化。智能体还要比较实际台词和叙事，程序相似度检查只是辅助。没有已审核 v3 Pattern 时，不能伪造 KNOWLEDGE Blueprint。
