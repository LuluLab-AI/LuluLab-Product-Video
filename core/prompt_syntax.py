"""Localized human-readable prompt syntax, shared by all offline gates."""
from __future__ import annotations

import re
from core.language import normalize_language

# Capture groups remain (delivery, role, text) for existing quality consumers.
SPEECH = re.compile(r'(口播|旁白|Dialogue|Voiceover)[（(]([^）)\n]+)[）)]\s*[：:]\s*[“"]([^”"\n]*)[”"]')
SCREEN_TEXT = re.compile(r'(?:屏幕文字|On-screen text)\s*[：:]\s*[“"]([^”"\n]+)[”"]')
VOICE_PATTERN = re.compile(
    r'(?:人物固定声音|Fixed voice)[（(]([^）)\n]+)[）)]\s*[：:]'
    r'([^。\n\[]+。|[^\n\[]+)'
)
NO_SPEECH = re.compile(r'本段无人物口播。|No character speech in this segment\.')
VOICE_FIELD_ALIASES = (
    ('语言', 'language'), ('口音', 'accent'), ('成年性别', 'adult gender'),
    ('年龄感', 'age impression'), ('核心音色', 'core timbre'), ('音高', 'pitch'),
    ('基础语速', 'base speaking rate'), ('表达风格', 'delivery style'),
)


def voice_records(prompt):
    """Return role, original full declaration and missing/empty required fields."""
    records = []
    for match in VOICE_PATTERN.finditer(prompt):
        description = match.group(2).strip()
        values = {}
        for part in re.split(r'[；;]', description):
            key, separator, value = part.partition('=')
            if separator:
                values[key.strip()] = value.strip().rstrip('。.')
        missing = [en for zh, en in VOICE_FIELD_ALIASES
                   if not (values.get(zh) or values.get(en))]
        records.append((match.group(1).strip(), match.group(0).strip(), missing))
    return records


def validate_prompt_language(prompt, language):
    """Non-Chinese prompts use stable parser labels; absent locale keeps legacy syntax.

    Dialogue and existing packaging may have another language. Do not reject them.
    """
    language = normalize_language(language)
    if language and language.split('-')[0] != 'zh' and re.search(
        r'人物固定声音[（(]|(?:口播|旁白)[（(]|屏幕文字[：:]|本段无人物口播。', prompt
    ):
        raise ValueError('Prompt syntax must use Fixed voice, Dialogue, Voiceover, '
                         'On-screen text, or No character speech in this segment.')
    if language and language.split('-')[0] == 'en':
        for match in VOICE_PATTERN.finditer(prompt):
            if re.search(r'[\u4e00-\u9fff]', match.group(2)):
                raise ValueError('English fixed-voice fields and descriptions must be in English.')
