# 历史 v2 证据约束 Blueprint（仅供旧任务追溯）

本页不用于 v3 生产路径；请用 [Creative Blueprint 合同](creative-blueprint-contract.md) 和 [Execution Spec 合同](execution-spec-contract.md)。

仅适用于 viralKnowledge；direct 模式、四段用户输入结构、模型和生成接口不变。

读取 candidate_pack 时保留 `knowledgeClass / productRole / viralityDrivers / creatorDependency / observedProducts / transferConditions / incompatibleUses`。所有 `requiresReview=true` 候选禁止直接选择。找不到可用资产时告诉用户需要重审，不得静默切换 direct。

ProductProfile 增加独立的 `confirmedFacts`，每项 `{id, fact, source}`。source 指用户明确提供的描述、可见产品图事实、说明书或可核查报告。图片不能证明不可见性能，愿望卖点不能成为已确认事实。不要更改原 request 四段结构。

每条 Blueprint 必须有 Primary Bundle、Structure、Hook、1～4 Action。Structure 或 Hook 至少一个来自 Primary。Proof 可省略并给出原因；CTA 可省略。跨 Bundle 资产也必须保留来源限制。

最小形状（示例键仅占位，实际必须从候选包选择）：

```json
{
  "blueprintId": "CB-001",
  "primaryBundleKey": "VB-...",
  "structure": {"assetKey": "STRUCTURE-..."},
  "hook": {"assetKey": "HOOK-..."},
  "actions": [{
    "assetKey": "ACTION-...",
    "adaptation": {
      "initialState": "当前产品操作开始前的具体状态",
      "action": "依据已确认用法编写的具体动作",
      "endState": "可见的操作结束状态，不新增功效",
      "productFactRefs": ["P1"],
      "conditionChecks": [{"condition": "逐字对应所选资产的一个 physicalPrerequisites 条目", "productFactRefs": ["P1"], "rationale": "该产品资料如何满足条件"}],
      "riskMitigation": "具体镜头拆分或降低动作复杂度的方案"
    }
  }],
  "proof": null,
  "proofOmissionReason": "缺少可支持效果对比的当前产品资料，仅展示真实用法",
  "avoid": [],
  "transferNotes": "保留机制，替换产品和操作，不迁移原片的未证实结果"
}
```

每个 ACTION/PROOF 都必须填 adaptation；每个 physicalPrerequisites 条目都有 conditionChecks 和有效 productFactRefs。低机制匹配只能在有当前产品事实支撑的等效适配后使用，不能只写“AI 已验证”。

选择 PROOF 时还需 `adaptation.presentation="illustration"`。允许演示/外观比较/有独立验证来源的机制，但生成画面仍只是示意；creator-claim 不得当 PROOF。当前产品事实和原片事实严格分开。没有证据时删去功效，不通过降低置信度保留假功效。

```bash
python3 scripts/viral_knowledge.py build-context \
  --input creative_blueprint_001.json \
  --candidate-pack candidate_pack.json \
  --output prompt_library_context_001.json
```

不要修改候选包来绕过检查。build-context 从候选包恢复规范资产，拒绝伪造键、错误类型、修改原模式/限制、缺失来源和缺少当前产品依据。它校验数据合同，不会自动判断报告真伪或视频语义；智能体与用户仍要审核。

`PromptLibraryContext.prompt` 将包含每个资产的证据、完整状态/动作/构图/节奏、条件和 fallback，以及所有来源约束。母提示词生成后，逐条对照这些合同做语义检查，不允许只写抽象“痛点→产品→效果”。验证机制、动作、产品一致性、可生成性和创意差异化；真实 CTR/CVR 必须来自真实投放反馈，不能从观看量估计。
