"""Language selection and normalization for LuluLab video workflow requests.

The agent supplies interactionLanguage derived from the user's explicit response
language, current task language or established context. Code must not infer it
from target country, filenames, product images or operating-system locale.
"""
import re

LANG_NAMES = {
    "中文":"zh-CN", "简体中文":"zh-CN", "chinese":"zh-CN", "mandarin":"zh-CN",
    "english":"en-US", "英语":"en-US", "美式英语":"en-US", "american english":"en-US",
    "portuguese":"pt-BR", "葡萄牙语":"pt-BR", "巴西葡萄牙语":"pt-BR", "brazilian portuguese":"pt-BR",
    "thai":"th-TH", "泰语":"th-TH", "spanish":"es-ES", "西班牙语":"es-ES",
    "日语":"ja-JP", "japanese":"ja-JP", "韩语":"ko-KR", "korean":"ko-KR",
}
COUNTRY_MEDIA = {
    "美国":"en-US", "us":"en-US", "usa":"en-US", "united states":"en-US",
    "英国":"en-GB", "uk":"en-GB", "united kingdom":"en-GB",
    "巴西":"pt-BR", "brazil":"pt-BR", "泰国":"th-TH", "thailand":"th-TH",
    "中国":"zh-CN", "china":"zh-CN", "日本":"ja-JP", "japan":"ja-JP",
    "韩国":"ko-KR", "south korea":"ko-KR", "墨西哥":"es-MX", "mexico":"es-MX",
    "西班牙":"es-ES", "spain":"es-ES", "葡萄牙":"pt-PT", "portugal":"pt-PT",
}

def normalize(value):
    if not isinstance(value,str) or not value.strip():
        raise ValueError('Language must be a nonempty BCP-47 code or supported language name')
    raw=value.strip(); lowered=raw.lower().replace('_','-')
    if lowered in LANG_NAMES: return LANG_NAMES[lowered]
    if not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z]{2,8}|-[0-9]{3})*',raw.replace('_','-')):
        raise ValueError('Invalid language tag: '+raw)
    parts=raw.replace('_','-').split('-')
    normalized=[parts[0].lower()]
    for part in parts[1:]:
        if len(part)==4 and part.isalpha():normalized.append(part.title())
        elif len(part)==2 and part.isalpha():normalized.append(part.upper())
        else:normalized.append(part.lower())
    return '-'.join(normalized)

def resolve(payload):
    """Fail closed when user's interaction language was not resolved by agent.
    Older tasks without language context must be confirmed at UI, not guessed.
    """
    if not isinstance(payload,dict) or not isinstance(payload.get('userConfig'),dict):
        raise ValueError('userConfig object required')
    config=payload['userConfig']; product=payload.get('productBrief') or {}
    explicit=config.get('interactionLanguage')
    if not explicit:
        raise ValueError('interactionLanguage missing; resolve from user instruction/message/context before submit')
    interaction=normalize(explicit)
    prompt=normalize(config.get('promptLanguage') or interaction)
    explicit_media=config.get('mediaLanguage') or product.get('targetLanguage')
    if explicit_media:
        media=normalize(explicit_media)
    else:
        country=str(product.get('targetCountry') or '').strip().lower()
        media=COUNTRY_MEDIA.get(country)
        if not media:
            raise ValueError('mediaLanguage missing and targetCountry has no verified default; ask user')
    result={**payload,'userConfig':{**config,'interactionLanguage':interaction,'promptLanguage':prompt,'mediaLanguage':media}}
    return result
