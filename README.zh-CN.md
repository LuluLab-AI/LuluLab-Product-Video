# LuluLab 带货视频

根据商品图生成 1～10 条原创 UGC 或剧情带货视频。可配置视频类型、提示词来源、目标市场、口播语言、Seedance 模型、时长、数量和达人参考图（默认 AI 生成，也可由用户提供）。本 Agent Skill 默认使用随包提供的 LuluLab Node.js CLI 生成提示词、达人参考图和视频，支持顺序生成片段、拼接成片、保存任务 ID 和最多 3 条独立视频工作流并发。

## 工作流程

1. 智能体识别图片可见的商品事实，并用表格列出全部可选项：视频类型、提示词方式、目标市场、口播语言、模型、时长、数量和达人方式。积分或费用说明放在表格外，并在首次计费提交前进行一次确认。
2. 每条视频通过随包 CLI 向私有 SalesVideoPromptV2 工作流提交四字段请求，并在本地校验返回的提示词。
3. 若用户未提供达人图，LuluLab ImageGenV2 使用全部商品原图制作多视角达人与商品参考图。
4. 视频默认使用 LuluLab VideoGenV2。仅在视频提交前确认 LuluLab 不可用或不支持配置时，才依次检查已验证可用的 LibTV、小云雀、即梦 CLI。任务提交后保持原渠道和任务 ID，不自动跨渠道重提。
5. 同一条视频的片段按顺序生成并拼接，各条视频分别保存成片。

原创视频核心元提示词仅存于私有工作流，不随公开仓库发布。提示词生成前，LuluLab 任务服务须已部署并正确映射工作流 ID SalesVideoPromptV2。

## 安装

将本仓库完整复制到智能体的 Skills 目录，文件夹命名为 LuluLab-Product-Video；保持 SKILL.md、scripts、core、references 和 agents 在同一目录。重新加载智能体 Skill 列表。Codex 等不同智能体的安装目录可能不同。

需要 Node.js 20+、Python 3.10+；多段拼接需要 FFmpeg。付费任务须在本机配置 LuluLab API Key。Skill 仅在首次 LuluLab 计费提交前读取已配置凭证并查询积分；不要将密钥写进提示词、任务文件、日志或仓库。可选视频渠道另需对应 CLI 和登录状态。

## 使用

示例：“使用 $LuluLab-Product-Video，根据这些商品图做一条面向美国市场的 15 秒 UGC 带货视频。”

默认原创 UGC、工作流生成提示词、美国市场、英语口播、Seedance 2.0 Fast、15 秒、1 条和 AI 达人参考图。用户可改为剧情带货、自带提示词或创作要求、其他市场或语言、其他支持模型、不同数量和时长，也可提供达人参考图。提示词、图片和视频任务可能消耗积分；新增付费重试或变更付费模型、渠道须重新授权。

执行与任务恢复详见 [SKILL.md](SKILL.md) 和 [Node API 说明](references/lululab-node-api.md)。英文说明：[README.md](README.md)。许可证：GPL-3.0-only。
