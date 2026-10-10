"""Small bilingual retrieval vocabulary; aliases never establish product claims."""
import re
import unicodedata

CATEGORIES = {
    'beauty': ('beauty', '美妆', '彩妆', '护肤'),
    'lip_makeup': ('lip makeup', 'lip gloss', 'lip tint', 'lipstick', '唇彩', '唇染', '唇釉', '口红', '唇部彩妆'),
    'foundation': ('foundation', '底妆', '粉底', '气垫'),
    'pimple_patch': ('pimple patch', 'acne patch', '痘痘贴'),
    'sunscreen': ('sunscreen', '防晒'),
    'serum': ('serum', '精华'),
    'setting_spray': ('setting spray', '定妆喷雾'),
}
VISUAL = {
    'VISIBLE_COLOR': ('visible color', 'color payoff', 'colour payoff', '色泽', '颜色', '色号', '试色', '唇色'),
    'SHIMMER': ('shimmer', 'pearlescent', '珠光'),
    'GLOSS': ('glossy', 'gloss', 'shine', '光泽', '亮泽', '反光'),
    'TEXTURE_DEMO': ('texture', '质地', '质感'),
    'VISIBLE_FINISH': ('visible finish', '妆效', '妆面'),
}
COUNTRIES = {'美国':'US', 'usa':'US', 'united states':'US', 'us':'US', '英国':'GB', 'uk':'GB',
             'gb':'GB', 'united kingdom':'GB', '中国':'CN', 'china':'CN', 'cn':'CN'}


def normalize(value):
    return unicodedata.normalize('NFKC', str(value or '')).lower().strip()


def country(value):
    v = normalize(value)
    return COUNTRIES.get(v, v.upper())


def concepts(value, mapping):
    value = normalize(value)
    return {key for key, aliases in mapping.items() if any(
        (alias in value if re.search(r'[\u4e00-\u9fff]', alias)
         else re.search(r'(?<![a-z])' + re.escape(alias) + r'(?![a-z])', value)) for alias in aliases)}


def terms(value):
    value = normalize(value)
    result = set(re.findall(r'[a-z][a-z0-9]+', value))
    for phrase in re.findall(r'[\u4e00-\u9fff]+', value):
        if len(phrase) <= 4:
            result.add(phrase)
        for size in (2, 3):
            result.update(phrase[i:i+size] for i in range(len(phrase)-size+1))
    result |= {'concept:' + k for k in concepts(value, {**CATEGORIES, **VISUAL})}
    return result


def lexical(query, target):
    q, t = terms(query), terms(target)
    return len(q & t) / max(1, len(q))


def category_fit(query, target):
    q, t = concepts(query, CATEGORIES), concepts(target, CATEGORIES)
    detailed = q - {'beauty'}
    if detailed:
        return .9 * len(detailed & t) / len(detailed) + .1 * bool('beauty' in q & t)
    return len(q & t) / max(1, len(q))
