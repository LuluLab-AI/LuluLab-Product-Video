"""Language context supplied by the agent; never infer it from files or locale."""
from __future__ import annotations

import re
from typing import NamedTuple


class LanguageContext(NamedTuple):
    interactionLanguage: str
    languageSource: str
    promptLanguage: str

    def as_dict(self) -> dict[str, str]:
        return self._asdict()


def normalize_language(value: str | None) -> str | None:
    """Normalize a BCP-47 tag without restricting the supported languages."""
    if not value or not value.strip():
        return None
    parts = value.strip().replace('_', '-').split('-')
    if not re.fullmatch(r'[A-Za-z]{2,8}', parts[0]) or not all(
        re.fullmatch(r'[A-Za-z0-9]{1,8}', part) for part in parts[1:]
    ):
        raise ValueError(f'Invalid BCP-47 language tag: {value!r}')
    normalized = [parts[0].lower()]
    for part in parts[1:]:
        normalized.append(part.upper() if len(part) == 2 and part.isalpha()
                          else part.title() if len(part) == 4 and part.isalpha()
                          else part.lower())
    return '-'.join(normalized)


def resolve_language_context(*, explicit_language: str | None = None,
                             task_message_language: str | None = None,
                             agent_default_language: str | None = None,
                             session_language: str | None = None) -> LanguageContext:
    """Use agent-understood task language, excluding quoted/code/tool material upstream."""
    for source, candidate in (
        ('user_explicit', explicit_language), ('user_message', task_message_language),
        ('session', session_language), ('agent_default', agent_default_language),
    ):
        language = normalize_language(candidate)
        if language:
            return LanguageContext(language, source, language)
    return LanguageContext('en-US', 'fallback', 'en-US')
