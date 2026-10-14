# Changelog

## v8.4.0 — 2026-10-14

- Always generate video prompts through SalesVideoPromptV2; remove prompt-source choice.
- Add optional custom creative requirements and pass them into the workflow metaprompt.
- Show product name, selling points, market, and audience separately from configurable generation settings.
- Update skill and UI descriptions and bilingual guides.


## v8.3.0 — 2026-10-14

- List every configurable option in the confirmation table and mark defaults and current selections.
- Support AI-generated or user-provided creator references; keep cost disclosure outside the table.
- Refresh skill, UI, repository, and bilingual guide descriptions.


## v8.0.0 — 2026-10-14

- Publish the LuluLab-first UGC and story video workflow, with SalesVideoPromptV2 prompts, ImageGenV2 creator references, and VideoGenV2 as the default video path.
- Validate capability before video submission; preserve provider and task ID after submission.
- Support one to ten videos, sequential segments per video, three concurrent workflows, and final assembly.
- Replace local creative generation and knowledge retrieval with server-side creative prompts and local output validation.
- Refresh Skill metadata and English and Chinese installation guides.

## v6.2.2 — 2026-10-10 (release candidate)

- Add synchronized English and Chinese GitHub installation guides and GPL-3.0-only licensing.
- Keep the existing Node.js CLI, language handling, models and paid-task recovery behavior.

## v6.2.1 — 2026-10-10

- Preserve the established task language ahead of the agent default during retries and recovery.
- Emit language-neutral CLI error codes with separate diagnostics for agent-localized explanations.
- Emit language-neutral render review findings and retain accented speech tokens during transcript comparison.
- Keep `ImageGenV2`, Sunburst and `1K` as image defaults; allow an explicit supported Flare override and bind the selected model to the persisted image task.
- Keep the LuluLab Node.js CLI and existing paid-task submission and recovery flow.
