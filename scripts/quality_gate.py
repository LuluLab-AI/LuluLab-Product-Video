"""Validate a video execution job before any upload or paid submission."""
from pathlib import Path
from prompt_validator import validate_result, LocalPromptError
from model_catalog import model_id_for


def validate_job(job):
    if not isinstance(job, dict):
        raise ValueError("视频任务必须是对象")
    model = model_id_for(job.get("videoModel", ""))
    segments = job.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("视频任务缺少 segments")
    for index, segment in enumerate(segments, 1):
        if not isinstance(segment, dict) or segment.get("segmentId") != index:
            raise ValueError("Segment 编号必须从 1 连续递增")
        files = segment.get("referenceFiles")
        if not isinstance(files, list) or len(files) < 2 or len(set(files)) != len(files):
            raise ValueError("每段必须带去重后的产品图和达人图")
        if any(not isinstance(path, str) or not Path(path).is_file() for path in files):
            raise ValueError("Segment 参考图不存在")
    target = job.get("targetDuration", sum(s.get("duration", 0) for s in segments))
    try:
        validate_result(
            {"videoPrompts": {"segments": segments}, "creatorPrompts": {"creators": []}},
            video_model=model, target_duration=target,
        )
    except (LocalPromptError, TypeError) as exc:
        raise ValueError(str(exc)) from exc
    return job
