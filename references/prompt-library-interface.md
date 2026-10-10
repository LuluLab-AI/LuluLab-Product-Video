# 历史 PromptLibraryContext 接口（v5.4，仅供旧任务追溯）

v3 生产链路不再把 Blueprint 包成 PromptLibraryContext；改用 [Execution Spec 合同](execution-spec-contract.md) 与 `local_prompt.py --execution-spec`。本页保留是为了兼容旧任务和回归测试。

该接口现在只承担一件事：把**已经由 Creative Planner 选定的单条 Creative Blueprint**注入原有 `local_prompt.py`，从而保持原 Prompt Generator 的调用方式不变。

它不负责检索数据库，也不负责 AI Rerank。

## 接入边界

- `viral_knowledge.py search`：负责从 SQLite 粗召回 Gene Bundle 与七类资产候选。
- 当前智能体：负责 AI Rerank、批次多样性规划和生成 Creative Blueprint。
- `viral_knowledge.py build-context --candidate-pack candidate_pack.json`：校验来源资产、当前产品事实及适配条件后，把 Creative Blueprint 转成 `PromptLibraryContext v1.0`；具体见 [prompt-ready-blueprint.md](prompt-ready-blueprint.md)。
- `local_prompt.py`：只验证和渲染该 Context，不访问数据库或网络。

适配器不得修改 `productBrief`、`userConfig`、`creativeRequirement` 或 `creatorBrief`，不得提交图片或视频任务。所有知识库处理必须发生在任何计费任务之前。

## PromptLibraryContext v1.0

```json
{
  "schemaVersion": "1.0",
  "status": "ready",
  "source": "local-viral-creative-blueprint",
  "version": "2.3",
  "matches": [
    {
      "templateId": "CB-001",
      "title": "出门前任务失败→产品介入→重复动作Proof",
      "score": 1.0,
      "hook": "正常动作因痛点突然失败",
      "structure": "任务失败→冲突→产品介入→重复动作→成功→反应",
      "shotRhythm": "前3秒快速建立冲突，中段产品介入，后段Proof与反应",
      "conversionPattern": "Proof：重复原失败动作并成功；CTA：人物反应型软转化",
      "sellingPoints": "用户真实卖点与Proof的映射说明",
      "avoid": "不得迁移未提供的功效/参数",
      "prompt": "Primary Bundle、Scene、Conflict、Action、Proof、CTA 的组合说明"
    }
  ],
  "warning": ""
}
```

### 状态

- `disabled`：Direct 模式或未传上下文，`matches=[]`。
- `ready`：知识库模式，必须且只能包含 1 条已选定 Creative Blueprint。
- `cached`：保留兼容状态，也必须且只能包含 1 条。
- `unavailable`：知识库不可用，`matches=[]`。

`MAX_MATCHES = 1`。知识库模式不再把多个原始爆款直接交给 Prompt Generator 自由挑选。

`prompt` 必须完整包含资产证据、promptSpec、constraints、claimLimit、当前产品事实和适配动作，不只是组合摘要。渲染上限 48,000 字符；超限报错，禁止静默截断。没有 Proof/CTA 的蓝图不能被生成器补出虚构功效/转化动作。示例仅说明外部字段，真实内容必须由 build-context 产生。

## 主流程调用

```python
build_prompt(
    product_brief,
    user_config,
    creator_brief,
    creative_requirement,
    prompt_library_context=context,
)
```

命令行：

```bash
python3 scripts/local_prompt.py build \
  --input request.json \
  --prompt-library-context prompt_library_context.json
```

验证：

```bash
python3 scripts/prompt_library.py validate --input prompt_library_context.json
python3 scripts/prompt_library.py render --input prompt_library_context.json
```
