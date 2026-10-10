# 历史 v2 原子资产 Planner（仅供旧任务追溯）

本页不用于 v3 生产路径。新路径以 [Creative Blueprint 合同](creative-blueprint-contract.md) 和 [Execution Spec 合同](execution-spec-contract.md) 为准；不能拼接七类资产后跳过 Creative Pattern.requiredRelationships。

输入：`candidate_pack.json`、用户已确认的产品事实、生成数量 N。

目标：不是复刻某一条爆款，而是先选择高相关 Primary Gene Bundle，再从 STRUCTURE / HOOK / SCENE / CONFLICT / ACTION / PROOF / CTA 中重组 N 个差异化 Creative Blueprint。品类不是硬隔离条件；跨品类迁移必须按资产类型控制强度。

## 1. ProductProfile 优先级

优先使用：

1. 用户明确产品事实与图片可见事实；
2. `sellingPointMechanisms`（仅由已确认卖点抽象）；
3. painPoints / useScenarios / desiredProofTypes；
4. category / industry；
5. targetCountry / videoStyle。

禁止为了匹配知识库创造新卖点、参数、功效、认证或用法。

## 2. Bundle Rerank

按以下顺序判断：

1. 产品真实痛点、卖点机制是否匹配；
2. Structure 能否迁移到当前产品；
3. Proof 是否存在可信的可视化路径；
4. 场景和人物关系是否自然；
5. 视频类型和目标市场是否适配；
6. 知识质量 / 可复用性；
7. 趋势信号。

`trend.label / viewsPerHour / hotScore` 只能作为小权重或同等适配时的优先项。不得因为 `RISING_FAST` 就选择产品机制明显不匹配的 Bundle。

## 3. 七类资产迁移规则

### STRUCTURE

默认可跨品类。迁移抽象因果结构，不复制原产品、原动作和原场景。

### HOOK

默认可跨品类。保留“注意力机制”，例如任务失败、异常结果、结果前置、质疑、挑战；具体动作必须重新适配当前产品。

### CTA

通常可跨品类，但目标市场和自然流/广告强度必须匹配。剧情自然流优先软 CTA。

### SCENE / CONFLICT

中等约束。允许跨品类，但必须符合当前产品的真实使用场景、人物关系和生活语境。

### ACTION

强物理约束。必须确认当前产品真实可以完成该动作。若 `compatibility.requiresPhysicalValidation=true`，必须显式检查。

### PROOF

最严格。必须与用户已确认卖点机制一致，并能通过当前产品真实、可视化地证明。若 `lowMechanismMatchWarning=true`，默认不选，除非存在不新增产品能力的等效最小适配。

必须遵守 [prompt-ready-blueprint.md](prompt-ready-blueprint.md)：来源合同、当前产品事实引用、逐条件校验和可执行 adaptation 都不能省略。\n\n## 4. 规划顺序

1. Rerank Bundle；每条选择 1 个 Primary Bundle。
2. STRUCTURE 优先继承 Primary Bundle。
3. 选择 HOOK。
4. 选择自然的 SCENE + CONFLICT。
5. 选择 1～4 个物理成立 ACTION。
6. 选择 0～1 个有依据的示意 PROOF；没有则写 proofOmissionReason，不发明功效。
7. 根据内容语境选择 0～1 CTA。
8. 对全批次做多样性检查。

每条 Blueprint 增加：

- `sellingPointMapping`：用户真实卖点如何映射到 Proof；
- `transferNotes`：哪些资产来自跨品类迁移，以及具体做了什么等效适配；
- `rationale`：为什么这套组合适合当前产品。

## 5. 多样性硬规则

候选充足时：

- 不重复相同的 STRUCTURE+HOOK+PROOF 三元组。
- 相邻两条至少改变 Hook + Scene/Conflict/Proof 中的两个维度。
- 同一 Scene 连续最多使用两次。
- 同一 Hook 在一批 10 条里最多使用两次。
- 同一 Proof 在物理允许时最多使用三次；若产品只有一种可信 Proof，可重复 Proof，但必须改变 Structure/Hook/Scene。

## 6. 质量优先级

产品真实性/物理成立 > Proof 清晰 > 卖点机制匹配 > Hook 强度 > 剧情真实感 > 差异化 > 趋势新鲜度 > CTA。
