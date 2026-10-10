"""Review existing video and timestamped ASR locally; no uploads or generation."""
import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from difflib import SequenceMatcher
from quality_gate import validate_speech, beats, digest


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def normalized(text):
    tokens = re.findall(r"[^\W_\d\u4e00-\u9fff]+|\d+|[\u4e00-\u9fff]", text.lower())
    digits = {"0":"zero", "1":"one", "2":"two", "3":"three", "4":"four",
              "5":"five", "6":"six", "7":"seven", "8":"eight", "9":"nine"}
    result = []
    for token in tokens:
        result.extend(digits[digit] for digit in token) if token.isdigit() else result.append(token)
    return result


def valid_windows(windows, duration):
    if not isinstance(windows,list) or not windows:
        return False
    end=0.0
    for w in windows:
        if not isinstance(w,dict) or not isinstance(w.get('observation'),str) or not w['observation'].strip():
            return False
        start,stop=w.get('start'),w.get('end')
        if any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in (start,stop)):
            return False
        if not 0 <= start < stop <= duration+.15 or start > end+.15 or stop < end:
            return False
        end=stop
    return end >= duration-.15


def assess(job, video, transcript=None, visual=None):
    info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
    failures, pending = [], []
    diagnostics = []
    segments = job.get('segments') or job['videoPrompts']['segments']
    try:
        expected = validate_speech(segments, job.get('qualityRequirements'))
    except ValueError as exc:
        failures.append('SPEECH_SPEC_INVALID'); diagnostics.append(str(exc)); expected = []
    audio = any(s.get('codec_type') == 'audio' for s in info['streams'])
    if expected and not audio:
        failures.append('AUDIO_TRACK_MISSING')
    if transcript is None:
        pending.append('ASR_REQUIRED')
    else:
        if transcript.get('mediaSha256') != file_hash(video):
            failures.append('ASR_MEDIA_MISMATCH')
        offset = 0
        for segment in segments:
            for beat in beats([segment]).values():
                target = ' '.join(s[2] for s in beat['speech'])
                if not target:
                    continue
                heard_segments = [s['text'] for s in transcript.get('segments', [])
                    if s.get('no_speech_prob', 0) < .6 and s.get('avg_logprob', 0) > -1
                    and s['start'] < offset+beat['end']+.4 and s['end'] > offset+beat['start']-.4]
                candidates = heard_segments + ([' '.join(heard_segments)] if heard_segments else [])
                best_match = max(
                    (SequenceMatcher(None, normalized(target), normalized(heard)).ratio()
                     for heard in candidates),
                    default=0,
                )
                if best_match < .9:
                    failures.append(f"DIALOGUE_MISMATCH:segment={segment['segmentId']}:start={beat['start']}s")
            offset += segment['duration']
    if not visual or visual.get('mediaSha256') != file_hash(video) or visual.get('promptDigest') != digest(segments):
        pending.append('DIRECT_RENDER_REVIEW_REQUIRED')
    elif not visual.get('reviewer') or not visual.get('reviewedAt'):
        pending.append('REVIEWER_OR_TIME_MISSING')
    elif visual.get('inspectionMode') != 'direct-video-and-audio' or not valid_windows(
            visual.get('evidenceWindows'), float(info.get('format',{}).get('duration') or sum(s['duration'] for s in segments))):
        pending.append('DIRECT_VIDEO_AUDIO_EVIDENCE_REQUIRED')
    else:
        for field in ('hook','actions','product','continuity','speechAudible','dialogueComplete'):
            if (visual.get('checks') or {}).get(field) is not True:
                failures.append(f'RENDER_REVIEW_FAILED:{field}')
    return {'status':'failed' if failures else 'needs_review' if pending else 'passed',
            'audioStream':audio,'failures':failures,'pending':pending,'diagnostics':diagnostics,
            'automatedChecksAreNotSemanticProof':True}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--job',required=True,type=Path);p.add_argument('--video',required=True,type=Path)
    p.add_argument('--transcript',type=Path);p.add_argument('--visual-review',type=Path)
    a=p.parse_args()
    report=assess(json.loads(a.job.read_text()),a.video,
                  json.loads(a.transcript.read_text()) if a.transcript else None,
                  json.loads(a.visual_review.read_text()) if a.visual_review else None)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['status']=='passed' else 2)
