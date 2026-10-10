"""Offline UGC delivery checks. Structural checks do not certify visual semantics."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from difflib import SequenceMatcher
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TIME = re.compile(r'\[(\d+(?:\.\d+)?)s\s*[-–]\s*(\d+(?:\.\d+)?)s\]')
from core.prompt_syntax import SPEECH, SCREEN_TEXT, NO_SPEECH, VOICE_PATTERN, voice_records



def digest(segments):
    return hashlib.sha256(json.dumps(segments, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def beats(segments):
    result = {}
    for segment in segments:
        prompt = segment['prompt']
        times = list(TIME.finditer(prompt))
        for i, match in enumerate(times):
            start, end = map(float, match.groups())
            content = prompt[match.end():times[i+1].start() if i+1 < len(times) else len(prompt)]
            key = f"{segment['segmentId']}:{i+1}"
            result[key] = dict(start=start, end=end, text=content, prompt=prompt,
                               segmentId=segment['segmentId'], speech=SPEECH.findall(content))
    return result


def validate_speech(segments, requirements=None):
    requirements = requirements or {}
    mode = requirements.get('speechMode', 'required')
    if mode not in ('required', 'none'):
        raise ValueError('speechMode must be required or none')
    if mode == 'none' and requirements.get('explicitNoSpeechRequest') is not True:
        raise ValueError('整条无口播需要用户明确选择：explicitNoSpeechRequest')
    spoken = []
    for key, beat in beats(segments).items():
        seconds = beat['end'] - beat['start']
        units = 0
        for delivery, role, text in beat['speech']:
            if not text.strip() or not any(unicodedata.category(ch).startswith('L') for ch in text):
                raise ValueError(f'{key}: 台词不能为空')
            if NO_SPEECH.search(beat['prompt']):
                raise ValueError(f'{key}: 无口播声明与台词冲突')
            if role.strip() not in {record[0] for record in voice_records(beat['prompt'])}:
                raise ValueError(f'{key}: 台词角色缺少固定声音')
            latin = len(re.findall(r"[A-Za-zÀ-ž]+(?:['’-][A-Za-zÀ-ž]+)*", text))
            chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
            other_letters = sum(unicodedata.category(ch).startswith('L') for ch in text) - sum(
                len(word) for word in re.findall(r"[A-Za-zÀ-ž]+(?:['’-][A-Za-zÀ-ž]+)*", text)
            ) - chinese
            units += latin / 3.5 + chinese / 5.0 + max(other_letters, 0) / 5.0
            language = requirements.get('targetLanguage', '')
            if language.lower().split('-')[0] == 'en' and (chinese or not latin):
                raise ValueError(f'{key}: 目标英语台词语言不符')
            # Speaking with an applicator touching lips is not a credible on-camera beat.
            if delivery in ('口播', 'Dialogue') and re.search(r'(涂[上下]?唇|涂抹[上下]?唇|沿[上下]唇|轻触[上下]唇|apply(?:ing)? (?:lip gloss|lipstick)|applicator touch(?:es|ing) (?:the )?lips)', beat['text'], re.I):
                raise ValueError(f'{key}: 涂唇镜头请用旁白或静音，不安排同步口播')
            spoken.append(text.strip())
        if units > seconds:
            raise ValueError(f'{key}: 台词超过时间块可读语速')
        header = beat['prompt'].split('[', 1)[0]
        if ('涂抹头' in header and re.search(r'(唇部外侧|唇外|嘴唇外侧)', header)
                and beat['start'] == 0 and re.search(r'(从瓶口取出|从瓶口抽出)', beat['text'])):
            raise ValueError(f'{key}: 涂抹头初态已在唇外，不能又从瓶口取出')
    if mode == 'required' and not spoken:
        raise ValueError('默认 UGC 必须有明确台词；固定声音或无口播声明不能替代台词')
    if mode == 'none' and spoken:
        raise ValueError('用户选择无口播，但存在台词')
    for segment in segments:
        if VOICE_PATTERN.search(segment['prompt']) and not SPEECH.search(segment['prompt']):
            raise ValueError('有固定声音却没有明确台词')
    return spoken


def validate_review(segments, review):
    if not isinstance(review, dict) or review.get('promptDigest') != digest(segments):
        raise ValueError('需要与最终提示词摘要一致的 qualityReview，修改提示词后须重新审核')
    timeline = beats(segments)
    if not review.get('reviewer') or not review.get('reviewedAt') or review.get('semanticPassed') is not True:
        raise ValueError('qualityReview 缺少实际语义审核人、时间或通过结论')
    states = review.get('states', [])
    if {s.get('beatRef') for s in states} != set(timeline) or len(states) != len(timeline):
        raise ValueError('每个时间块需要唯一的初态/末态审核')
    previous = None
    for state in states:
        if not isinstance(state.get('initial'), dict) or not state['initial'] or not isinstance(state.get('end'), dict) or not state['end']:
            raise ValueError('动作状态必须为非空对象')
        for value in (state['initial'], state['end']):
            if any(not isinstance(v, str) or not v.strip() for v in value.values()):
                raise ValueError('状态值必须为明确字符串')
        if previous and previous['end'] != state['initial'] and not state.get('transitionExplanation'):
            raise ValueError('相邻镜头状态改变但缺少动作或剪辑解释')
        if not state.get('visibleAction') or state['visibleAction'] not in timeline[state['beatRef']]['text']:
            raise ValueError('状态审核必须引用实际镜头动作')
        previous = state
    if [s['beatRef'] for s in states] != list(timeline):
        raise ValueError('状态审核顺序必须与镜头顺序一致')
    for field in ('hook', 'buyReason', 'ending'):
        item = review.get(field) or {}
        beat = timeline.get(item.get('beatRef'))
        if not beat or not item.get('quote') or item['quote'] not in beat['text'] or not item.get('rationale'):
            raise ValueError(f'{field}: 必须引用实际时间块内容并解释表达目的')
        if field == 'hook' and (beat['segmentId'] != segments[0]['segmentId'] or beat['start'] >= 3):
            raise ValueError('Hook 必须在整条视频前3秒落实')
    if review['ending'].get('origin') not in ('original', 'source', 'no-cta'):
        raise ValueError('结尾须区分原创引导、来源CTA或无CTA')
    if review['ending']['origin'] == 'source' and not review['ending'].get('assetKey'):
        raise ValueError('来源CTA必须有真实assetKey')


def validate_job(job):
    from local_prompt import validate_result, LocalPromptError
    segments = job.get('segments', [])
    result = {'videoPrompts': {'segments': segments}, 'creatorPrompts': {'creators': []}}
    try:
        validate_result(result, video_model=job.get('videoModel'),
                        target_duration=sum(s['duration'] for s in segments),
                        requirements=job.get('qualityRequirements'))
    except LocalPromptError as exc:
        raise ValueError(str(exc)) from exc
    validate_review(segments, job.get('qualityReview'))
    strategy = job.get('strategyUsed')
    if strategy is not None and strategy not in ('DIRECT','KNOWLEDGE'):
        raise ValueError('strategyUsed 必须是 DIRECT 或 KNOWLEDGE')
    if strategy is None and job.get('promptMode') not in ('aiDirect','viralKnowledge'):
        raise ValueError('执行job必须声明 strategyUsed 或旧版 promptMode')
    if strategy == 'DIRECT' and job.get('strategyRequested') == 'AUTO' and not job.get('fallbackReason'):
        raise ValueError('AUTO 回退 Direct 必须记录 fallbackReason')
    if (job.get('qualityRequirements') or {}).get('speechMode','required') == 'required' and not (job.get('qualityRequirements') or {}).get('targetLanguage'):
        raise ValueError('口播必须声明目标市场语言targetLanguage')
    if strategy == 'KNOWLEDGE':
        validate_execution_translation(job, segments)
    elif strategy is None and job.get('promptMode') == 'viralKnowledge':
        # Re-resolve current restrictions, not an old or hand-edited candidate pack.
        from pathlib import Path
        from viral_knowledge import search_candidates, default_db_path
        from blueprint_contract import resolve_blueprint
        db = Path(job.get('knowledgeDb') or default_db_path())
        candidates = search_candidates(db, job.get('request') or {}, job.get('productProfile') or {},
                                       bundle_top=10000, asset_top=10000)
        blueprint = resolve_blueprint(job.get('creativeBlueprint') or {}, candidates)
        validate_mechanism(segments, blueprint, job['qualityReview'])


def validate_execution_translation(job, segments):
    """Reject prompt drift from the approved v3 Pattern and authored Execution Spec."""
    from pathlib import Path
    from local.repository import read_patterns, default_db_path
    from local.creative_planner import validate_blueprints
    from local.execution_spec import build_execution_spec
    bp = job.get('creativeBlueprint') or {}
    spec = job.get('executionSpec') or {}
    pattern = next((p for p in read_patterns(Path(job.get('knowledgeDb') or default_db_path()))
                    if p['patternKey'] == bp.get('patternKey')), None)
    if pattern is None:
        raise ValueError('知识库 Pattern 已失效或未经 v3 审核')
    validate_blueprints([bp], [pattern], 1,
                        (job.get('productProfile') or {}).get('confirmedFacts') or [])
    duration = sum(s['duration'] for s in segments)
    checked = build_execution_spec(bp, pattern, duration, spec)
    prompt_timeline = []
    offset = 0.0
    for segment in segments:
        for prompt_beat in beats([segment]).values():
            prompt_timeline.append((offset + prompt_beat['start'],offset + prompt_beat['end'],prompt_beat['text']))
        offset += segment['duration']
    prompt_text = '\n'.join(s['prompt'] for s in segments)
    for beat in checked['beats']:
        matching = [text for start,end,text in prompt_timeline
                    if abs(start-beat['start']) < .02 and abs(end-beat['end']) < .02]
        if len(matching) != 1:
            raise ValueError(f"Execution Spec {beat['beatRef']} 时间与最终镜头不一致")
        actual = matching[0]
        for field in ('action','visual'):
            if beat[field] not in actual:
                raise ValueError(f"Execution Spec {beat['beatRef']} 的 {field} 未进入最终提示词")
        speech = beat.get('speech')
        if speech and speech['text'] not in actual:
            raise ValueError(f"Execution Spec {beat['beatRef']} 的台词被改写/删除")
        if beat.get('screenText') and beat['screenText'] not in actual:
            raise ValueError(f"Execution Spec {beat['beatRef']} 的屏幕文字被改写/删除")
    if checked['buyReason'] not in prompt_text or checked['endingIntent'] not in prompt_text:
        raise ValueError('购买理由或结尾意图未进入最终提示词')
    if checked['voiceDescription'] not in prompt_text:
        raise ValueError('固定声音描述未进入最终提示词')
    if checked.get('noOnScreenText') and SCREEN_TEXT.search(prompt_text):
        raise ValueError('无屏幕文字要求与最终 Prompt 冲突')
    if not job.get('qualityReview',{}).get('mechanismChecked'):
        raise ValueError('审核记录须确认必要关系、Hook渠道及源限制已落实')


def validate_mechanism(segments, blueprint, review):
    realization = blueprint.get('hookRealization') or {}
    required = (blueprint.get('hook') or {}).get('expressionChannels')
    if not required or not realization.get('message') or not realization.get('channels'):
        raise ValueError('知识库Hook缺少表达渠道与具体落实方案')
    channels = realization['channels']
    if not set(channels) <= {'speech', 'text', 'action'}:
        raise ValueError('未知Hook表达渠道')
    if any(c in required for c in ('speech', 'text')) and not set(channels) & {'speech', 'text'}:
        raise ValueError('语义型Hook不能退化为无法表达其含义的普通动作')
    beat = beats(segments).get(realization.get('beatRef'))
    if not beat or beat['segmentId'] != segments[0]['segmentId'] or beat['start'] >= 3:
        raise ValueError('知识库Hook必须落实在前3秒')
    if realization['message'] not in beat['text']:
        raise ValueError('Hook消息未进入最终提示词')
    if 'speech' in channels and not any(realization['message'] in s[2] for s in beat['speech']):
        raise ValueError('Hook缺少实际口播/旁白台词')
    if 'text' in channels and (any(w in beat['prompt'].lower() for w in ('无字幕', '禁止字幕', '无文字', '不加字幕', '无屏幕文字', 'no subtitles', 'no on-screen text'))
                              or not any(realization['message'] in t for t in SCREEN_TEXT.findall(beat['text']))):
        raise ValueError('文字型Hook与无字幕要求冲突或没有指定屏幕文字')
    if set(required) != set(channels) and not realization.get('adaptationReason'):
        raise ValueError('Hook表达渠道迁移必须说明理由')
    if not blueprint.get('structureRealization'):
        raise ValueError('缺少Structure各阶段到实际镜头的映射')
    stages = (blueprint.get('structure') or {}).get('requiredStages', [])
    mapped = blueprint['structureRealization']
    if not stages or {x.get('stage') for x in mapped} != set(stages):
        raise ValueError('不得删除原结构的必要阶段；不适用时重新选择结构')
    for item in mapped:
        target = beats(segments).get(item.get('beatRef'))
        if not target or not item.get('quote') or item['quote'] not in target['text'] or not item.get('rationale'):
            raise ValueError('结构阶段未落实到可核对镜头')


def check_diversity(jobs):
    """Compare creative content, excluding shared identity/packaging headers."""
    failures = []
    for i, left in enumerate(jobs):
        for j, right in enumerate(jobs[:i]):
            a = ' '.join(b['text'] for b in beats(left['segments']).values())
            b = ' '.join(b['text'] for b in beats(right['segments']).values())
            if SequenceMatcher(None, a, b).ratio() > .85:
                failures.append(f'{j+1}/{i+1}: 实际镜头与台词高度相似，需重新设计')
    return failures


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', nargs='+', required=True, type=Path)
    args = parser.parse_args()
    try:
        jobs = [json.loads(p.read_text()) for p in args.jobs]
        for job in jobs:
            validate_job(job)
        issues = check_diversity(jobs)
        if issues:
            raise ValueError('; '.join(issues))
        print(json.dumps({'ok': True, 'jobs': len(jobs)}))
    except (ValueError, KeyError, TypeError) as exc:
        from core.user_errors import failure
        failure(exc, "QUALITY_GATE_FAILED")
        raise SystemExit(2)
