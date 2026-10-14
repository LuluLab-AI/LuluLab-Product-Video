# LuluLab-Product-Video

Create 1–10 original UGC or story-driven product videos from product images. This Agent Skill uses the bundled LuluLab Node.js CLI for creative prompts, optional creator reference images, and video generation. It supports sequential segments, final assembly, saved task IDs, and up to three independent video workflows at once.

## How it works

1. The agent identifies visible product facts and asks the user to confirm the market, spoken language, duration, quantity, model, and paid generation.
2. The bundled CLI submits each video's four-field request to the private SalesVideoPromptV2 workflow. The returned prompts are validated locally.
3. If the user has not supplied a creator image, LuluLab ImageGenV2 makes a multi-view creator and product reference from all product images.
4. LuluLab VideoGenV2 is the default video path. Before any video submission, an unavailable or unsupported LuluLab configuration may fall back to a verified LibTV, Xiaoyunque, then Dreamina CLI. A submitted task stays with its original provider and task ID.
5. Segments are generated in order and joined into a separate final video for each request.

The private creative workflow and its core metaprompts are not included in this public repository. SalesVideoPromptV2 must be deployed and mapped in the LuluLab task dispatcher before prompt generation can work.

## Install

Copy this entire repository into your agent's Skills directory as LuluLab-Product-Video, keeping SKILL.md, scripts, core, references, and agents together. Reload the agent's skill list. Codex and other agents may use different Skills directories.

Requirements: Node.js 20+, Python 3.10+, and FFmpeg for joining segments. Configure a LuluLab API key locally for paid tasks. The skill reads existing credentials and checks credits only before its first LuluLab paid submission; never put credentials in prompts, task files, logs, or this repository. Optional video providers need their own installed and authenticated CLIs.

## Use

Ask the agent: “Use $LuluLab-Product-Video with these product photos to make one 15-second UGC video for the US market.”

Defaults are US market, English speech, Seedance 2.0 Fast, 15 seconds, one video, and an AI creator reference. The user can change these before generation. Prompt, image, and video tasks may consume credits. Paid retries or a change of paid model or provider require fresh authorization.

For implementation and task recovery, see [SKILL.md](SKILL.md) and the [Node API reference](references/lululab-node-api.md). Chinese guide: [README.zh-CN.md](README.zh-CN.md). License: GPL-3.0-only.
