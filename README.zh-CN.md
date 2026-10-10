# UGC 带货视频

## 概述

本 Skill 根据产品图片和核实过的产品事实制作本地带货短视频项目：规划创意、准备提示词和参考图，经用户确认后用随包提供的 LuluLab Node.js CLI 提交图片与视频任务，并检查、拼接结果。适合能够审核产品卖点和付费生成步骤的商家与创作者。

Agent Skills 根目录是本仓库的 `ugc-product-video/` 文件夹，其中包含 `SKILL.md`。安装时须保留整个文件夹。

## 主要能力

- 产品资料、创意规划、分段提示词及质量检查。
- 使用 LuluLab `ImageGenV2` 和 `VideoGenV2`，保存任务 ID 以便恢复。
- 交互语言与成片语言独立选择，现有规则支持中英文及其他 BCP-47 语言。
- 有已批准的本地知识库时，可选用知识驱动的创意规划。

## 环境要求

- 能读取 Agent Skills 文件夹并操作本地文件的智能体。Codex、Claude Code 的 Skill 目录不同，应以各自当前文档为准；其他智能体需要等效的文件型 Skill 能力。
- Node.js 20+、Python 3、FFmpeg、FFprobe，以及选用工作流所需的 Python 依赖。
- 生成任务需要连接 LuluLab 服务，并在付费提交前配置 LuluLab API Key。Node.js CLI 已包含在 `scripts/lululab_cli.mjs`，无需 npm 或 `npx` 安装。
- 默认 LuluLab 通道面向 macOS 和 Windows；可选渠道各有自身要求。

## 安装

可向具备文件操作能力的智能体发送：

> 请将这个 LuluLab Skill 安装到我当前使用的 AI 智能体环境：https://github.com/LuluLab-AI/ugc-product-video 。请遵循项目的官方安装说明。

智能体应先检查仓库，再把完整的 `ugc-product-video/` 文件夹复制到当前智能体的用户 Skill 目录，目录名保持 `ugc-product-video`，并确认 `SKILL.md`、`scripts/`、`core/`、`local/`、`references/` 均在同一根目录。不能只复制 `SKILL.md`。已有同名目录时先比较版本，并在替换前征求用户确认；不要覆盖其他 Skill。安装后重新加载 Skill 列表，确认能够识别 `ugc-product-video`。此 Skill 未提供独立安装脚本。

## 快速开始

- “用这些产品图，通过 $ugc-product-video 为美国市场规划一条 15 秒 TikTok 演示视频；生成前先给我确认产品事实和方案。”
- “用这些照片制作面向美国消费者的西班牙语产品视频，和我用中文交流。”

用户需审核产品宣称，并在第一次付费生成前确认。

## 配置

用 `node scripts/lululab_cli.mjs --help` 离线检查 CLI。首次付费提交前，Skill 使用 `node scripts/lululab_cli.mjs user --credits`，随后使用 `task submit` 与 `task fetch`。在本机设置 `LULULAB_API_KEY`，或在已有私有文件 `~/.ugc-product-video/config.json` 中设置 `apiKey`。不要把 Key 提交到仓库、提示词或命令参数。Node 不在 `PATH` 时可用 `LULULAB_NODE` 指向 Node.js；`LULULAB_API_BASE_URL` 仅供高级测试服务配置。详见 [Node API 契约](references/lululab-node-api.md)。

## 支持语言

交互遵循用户指定语言，包括中文和英文，并按现有 BCP-47 规则处理其他语言。口播和画面文字语言与交互语言独立，可由用户明确指定。

## 常见问题

| 问题 | 检查方法 |
| --- | --- |
| 无法识别 Skill | 检查目录名称、根目录中的 `SKILL.md` 及智能体当前的 Skill 目录，然后重新加载。 |
| 找不到 CLI | 检查 Node.js 20+ 和 `scripts/lululab_cli.mjs`，运行 `--help`。 |
| 缺少 API Key | 在付费任务前于本机配置 `LULULAB_API_KEY`。 |
| 网络请求失败 | 检查网络、服务状态及覆盖的服务地址；重新提交前先恢复已保存的任务 ID。 |
| 模型调用失败 | 查看保存的任务状态和模型错误，不静默切换模型或重复付费提交。 |
| 缺少依赖 | 安装报告中指出的 Python、FFmpeg 或 FFprobe 依赖，再执行本地预检。 |

## 支持

网站：https://lululab.ai  
邮箱：contact@lululab.ai
