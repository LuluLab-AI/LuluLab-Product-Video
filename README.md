# LuluLab Product Video

Create 1–20 product videos through the same Customer/Dispatcher pipeline as the website:

`SalesVideoPromptV3 → one VideoCreationV1 per video → server-side segmentation, VideoGenV2, duration inspection and assembly`

The local adapter uploads product/creator images, persists task IDs, polls and downloads. Creator images are optional; no additional AI reference board is generated. Defaults: US market, English speech, automatic creative type, Seedance 2.0 Fast, 15 seconds, one video, 9:16, 720p, audio enabled.

Copy the complete skill directory into your agent's Skills directory. New tasks require Node.js ≥20 and a locally configured LuluLab API key (`LULULAB_API_KEY` or existing private configuration). Python, FFmpeg and third-party video CLIs are not required. Never put credentials in chat, prompts or task files.

Review the configuration and billing scope before submission and reuse explicit approval for that unchanged run. Resume the original state after interruption; never automatically retry paid or uncertain submissions.

See [SKILL.md](SKILL.md) for commands and contracts. Old scripts are for [legacy task recovery](references/LEGACY_WORKFLOW.md) only. License: GPL-3.0-only.

Supports multilingual interaction for configuration, estimated credits, confirmation, progress, errors and delivery. Reply language follows the user’s choice; output text/speech language is configured separately. See [SKILL.md](SKILL.md).
