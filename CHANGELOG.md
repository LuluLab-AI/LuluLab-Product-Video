# Changelog

## v6.2.2 — 2026-10-10 (release candidate)

- Add synchronized English and Chinese GitHub installation guides and GPL-3.0-only licensing.
- Keep the existing Node.js CLI, language handling, models and paid-task recovery behavior.

## v6.2.1 — 2026-10-10

- Preserve the established task language ahead of the agent default during retries and recovery.
- Emit language-neutral CLI error codes with separate diagnostics for agent-localized explanations.
- Emit language-neutral render review findings and retain accented speech tokens during transcript comparison.
- Keep `ImageGenV2`, Sunburst and `1K` as image defaults; allow an explicit supported Flare override and bind the selected model to the persisted image task.
- Keep the LuluLab Node.js CLI and existing paid-task submission and recovery flow.
