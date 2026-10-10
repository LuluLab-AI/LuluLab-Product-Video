# UGC Product Video

## Overview

This Skill turns product images and verified product facts into short, local commerce video projects. It plans a creative concept, prepares prompts and reference images, submits approved image and video tasks through the bundled LuluLab Node.js CLI, then checks and assembles the result. The intended users are merchants and creators who can review the product claims and approve paid generation.

The Agent Skills root is this repository's `ugc-product-video/` folder, which contains `SKILL.md`. Keep the entire folder together.

## Key Features

- Product profile, creative plan, segment prompts and quality checks.
- LuluLab `ImageGenV2` reference images and `VideoGenV2` videos, with saved task IDs for recovery.
- Separate interaction and video languages. English, Chinese and other BCP-47 interaction languages are supported by the existing language rules.
- Optional knowledge-based creative planning when an approved local knowledge database exists.

## Requirements

- An AI agent that can read an Agent Skills folder and run local files. Codex and Claude Code use different skill locations; confirm the location in the agent's current documentation. Other agents need an equivalent file-based skill mechanism.
- Node.js 20+, Python 3, FFmpeg and FFprobe, plus the Python dependencies required by the chosen workflow.
- Network access to the LuluLab service for generation and a LuluLab API Key for paid tasks. The Node.js CLI is already included at `scripts/lululab_cli.mjs`; there is no npm or `npx` install step.
- macOS or Windows for the default LuluLab path. Optional providers have their own requirements.

## Installation

Ask your file-capable agent:

> Please install this LuluLab Skill into my current AI agent environment: https://github.com/LuluLab-AI/ugc-product-video . Follow the project's official installation instructions.

The agent should inspect the repository, copy the **whole** `ugc-product-video/` folder to the current agent's user Skill directory under the name `ugc-product-video`, and verify that `SKILL.md`, `scripts/`, `core/`, `local/`, and `references/` remain together. Do not copy only `SKILL.md`. If a folder of that name already exists, compare versions and ask before replacing it; leave unrelated Skills alone. Reopen or reload the agent's Skill list and confirm that `ugc-product-video` is discoverable. No installer script is supplied for this Skill.

## Quick Start

- “Use $ugc-product-video with these product photos to plan a 15-second TikTok demonstration for the US market. Show me the facts and plan before generation.”
- “Create a Spanish-language product video from these photos for US shoppers, and reply to me in English.”

The user reviews product claims and confirms the first paid generation before submission.

## Configuration

Check the bundled CLI without sending a request: `node scripts/lululab_cli.mjs --help`. At the first paid submission, the Skill uses `node scripts/lululab_cli.mjs user --credits`, then `task submit` and `task fetch`. Set `LULULAB_API_KEY` in the local environment or use the existing private `~/.ugc-product-video/config.json` with an `apiKey` field. Never commit the Key or put it in a prompt or command argument. `LULULAB_NODE` may point to Node.js when it is not on `PATH`; `LULULAB_API_BASE_URL` is an advanced test-service override. See [the Node API contract](references/lululab-node-api.md).

## Supported Languages

Interaction follows the user's requested language, including English and Chinese, with BCP-47 locale handling. Spoken and on-screen video language is selected separately from the interaction language and can be explicitly requested.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Skill is not recognized | Verify the folder name, `SKILL.md` at its root, and the agent's current Skill directory; reload discovery. |
| CLI is missing | Verify Node.js 20+ and `scripts/lululab_cli.mjs`; run its `--help`. |
| API Key is missing | Configure `LULULAB_API_KEY` locally before a paid task. |
| Network request fails | Check connectivity, service availability and any configured base URL; recover a saved task ID before resubmitting. |
| Model call fails | Inspect the saved task status and model-specific error; do not silently switch models or repeat a paid task. |
| Dependency is missing | Install the reported Python, FFmpeg or FFprobe dependency and rerun the local preflight. |

## Support

Website: https://lululab.ai  
Email: contact@lululab.ai
