# LuluLab 带货视频

从商品图生成 1～20 条带货视频，与网站共用 Customer/Dispatcher 执行链路：

`SalesVideoPromptV3 → 每条 VideoCreationV1 → 服务端分段、VideoGenV2、时长检查与拼接`

本地负责整理素材、提交请求、保存任务 ID、查询和下载。达人图可选；不额外生成多视角达人板。默认美国市场、英语口播、智能匹配创意、Seedance 2.0 Fast、15 秒、1 条、9:16、720p、有声音。模型与时长组合由适配器校验。

安装时完整复制本技能目录到智能体 Skills 目录。新流程仅需 Node.js ≥20 和本机 LuluLab API Key，不需要 Python、FFmpeg 或第三方视频 CLI。Key 使用 `LULULAB_API_KEY`（兼容已有私有配置），不要发到聊天或写入任务文件。

提交前展示配置与计费范围，沿用用户对当前配置的明确确认。策划和视频生成使用同一轮授权；失败不自动付费重试。中断后复用原 state 查询，提交结果不确定时不重提。

实际命令、输入示例和恢复规则见 [SKILL.md](SKILL.md)。旧脚本仅用于恢复历史任务，见 [历史流程](references/LEGACY_WORKFLOW.md)。许可证：GPL-3.0-only。

支持多语言交互：配置、预计积分、确认、进度、错误与交付说明跟随用户选择的交流语言；口播语言独立设置，详见 [SKILL.md](SKILL.md)。
