#!/usr/bin/env python3
"""Validate SalesVideoPromptV2 output against the attachment's result contract.

The creative master prompt is held only in the private n8n workflow.
"""
from __future__ import annotations
import math
import re
from typing import Any, Mapping

class LocalPromptError(RuntimeError):
    pass

def _duration_allowed(model: str, duration: int) -> bool:
    model = model.strip().lower()
    if model in {"seedance-2", "seedance-2-fast", "seedance-2-mini"}:
        return 4 <= duration <= 15
    if model == "seedance-2-5":
        return 4 <= duration <= 30
    return False


TIMELINE_PATTERN = re.compile(r"\[(\d+(?:\.\d+)?)s-(\d+(?:\.\d+)?)s\]")
VOICE_PATTERN = re.compile(r"人物固定声音（([^\uff09]+)）：([^\u3002\n]+。)")
VOICE_FIELDS = (
    "语言=",
    "口音=",
    "成年性别=",
    "年龄感=",
    "核心音色=",
    "音高=",
    "基础语速=",
    "表达风格=",
)
CROSS_SEGMENT_REFERENCES = (
    "上一段",
    "下一段",
    "承接上段",
    "承接前段",
    "继续前段",
    "同一个达人",
    "同一位达人",
    "同一人物",
    "相同人物",
    "同上一人物",
    "声音同上段",
    "保持相同声音",
)


def _validate_timeline(prompt: str, duration: int, segment_index: int) -> None:
    ranges = [(float(start), float(end)) for start, end in TIMELINE_PATTERN.findall(prompt)]
    if not ranges:
        raise LocalPromptError(f"第 {segment_index} 个 Segment 缺少 [0s-3s] 格式的连续时间轴。")
    if abs(ranges[0][0]) > 1e-6:
        raise LocalPromptError(f"第 {segment_index} 个 Segment 时间轴必须从 0 秒开始。")
    previous_end = 0.0
    for block_index, (start, end) in enumerate(ranges, 1):
        if abs(start - previous_end) > 1e-6:
            raise LocalPromptError(
                f"第 {segment_index} 个 Segment 的第 {block_index} 个时间块与前一块不连续。"
            )
        if end <= start:
            raise LocalPromptError(f"第 {segment_index} 个 Segment 存在无效或倒序时间块。")
        if end - start > 4.000001:
            raise LocalPromptError(f"第 {segment_index} 个 Segment 的单个时间块不得超过 4 秒。")
        previous_end = end
    if abs(previous_end - duration) > 1e-6:
        raise LocalPromptError(
            f"第 {segment_index} 个 Segment 时间轴结束于 {previous_end:g} 秒，必须等于 duration {duration} 秒。"
        )


def _validate_prompt_independence(prompt: str, segment_index: int) -> None:
    for forbidden in CROSS_SEGMENT_REFERENCES:
        if forbidden in prompt:
            raise LocalPromptError(
                f"第 {segment_index} 个 Segment 含跨段引用“{forbidden}”，必须改为本段的绝对描述。"
            )


def _voice_fingerprints(prompt: str, segment_index: int) -> dict[str, str]:
    if "本段无人物口播。" in prompt:
        if VOICE_PATTERN.search(prompt):
            raise LocalPromptError(f"第 {segment_index} 个 Segment 同时声明无口播和人物固定声音。")
        return {}
    matches = VOICE_PATTERN.findall(prompt)
    if not matches:
        raise LocalPromptError(
            f"第 {segment_index} 个 Segment 未写人物固定声音，无口播时必须明确写“本段无人物口播。”"
        )
    voices: dict[str, str] = {}
    for role, description in matches:
        missing = [field for field in VOICE_FIELDS if field not in description]
        if missing:
            raise LocalPromptError(
                f"第 {segment_index} 个 Segment 的角色“{role}”声音特征缺少：{' '.join(missing)}"
            )
        fingerprint = f"人物固定声音（{role}）：{description}"
        if role in voices and voices[role] != fingerprint:
            raise LocalPromptError(f"第 {segment_index} 个 Segment 重复且冲突地定义角色“{role}”的声音。")
        voices[role] = fingerprint
    return voices


def validate_result(
    result: Mapping[str, Any],
    *,
    video_model: str | None = None,
    target_duration: int | None = None,
) -> dict[str, Any]:
    """Validate the former workflow's public JSON contract and return normalized data."""
    if not isinstance(result, Mapping):
        raise LocalPromptError("本地提示词结果必须是 JSON 对象。")
    if set(result) != {"videoPrompts", "creatorPrompts"}:
        raise LocalPromptError("本地提示词结果顶层只能包含 videoPrompts 和 creatorPrompts。")

    video_prompts = result.get("videoPrompts")
    creator_prompts = result.get("creatorPrompts")
    if not isinstance(video_prompts, Mapping):
        raise LocalPromptError("videoPrompts 必须是对象。")
    if not isinstance(creator_prompts, Mapping):
        raise LocalPromptError("creatorPrompts 必须是对象。")

    segments = video_prompts.get("segments")
    creators = creator_prompts.get("creators")
    if not isinstance(segments, list) or not segments:
        raise LocalPromptError("videoPrompts.segments 必须是非空数组。")
    if not isinstance(creators, list):
        raise LocalPromptError("creatorPrompts.creators 必须是数组。")

    voice_fingerprints: dict[str, str] = {}
    total_duration = 0
    for index, segment in enumerate(segments, 1):
        if not isinstance(segment, Mapping):
            raise LocalPromptError(f"第 {index} 个 Segment 必须是对象。")
        for key in ("segmentId", "title", "duration", "prompt"):
            if key not in segment:
                raise LocalPromptError(f"第 {index} 个 Segment 缺少 {key}。")
        duration = segment.get("duration")
        if isinstance(duration, bool) or not isinstance(duration, int):
            raise LocalPromptError(f"第 {index} 个 Segment duration 必须是整数。")
        if video_model and not _duration_allowed(video_model, duration):
            raise LocalPromptError(
                f"第 {index} 个 Segment 时长 {duration} 不符合模型 {video_model} 的限制。"
            )
        total_duration += duration
        if not isinstance(segment.get("prompt"), str) or not segment["prompt"].strip():
            raise LocalPromptError(f"第 {index} 个 Segment prompt 不能为空。")
        prompt = segment["prompt"].strip()
        _validate_timeline(prompt, duration, index)
        _validate_prompt_independence(prompt, index)
        segment_voices = _voice_fingerprints(prompt, index)
        for role, fingerprint in segment_voices.items():
            if role in voice_fingerprints and voice_fingerprints[role] != fingerprint:
                raise LocalPromptError(
                    f"角色“{role}”跨 Segment 的人物固定声音必须逐字一致。"
                )
            voice_fingerprints[role] = fingerprint

    if target_duration is not None and total_duration != target_duration:
        raise LocalPromptError(
            f"Segment 总时长 {total_duration} 秒与目标时长 {target_duration} 秒不一致。"
        )
    if target_duration is not None and video_model:
        max_duration = 30 if video_model.strip().lower() == "seedance-2-5" else 15
        minimum_segments = math.ceil(target_duration / max_duration)
        if len(segments) != minimum_segments:
            raise LocalPromptError(
                f"模型 {video_model} 生成 {target_duration} 秒视频应使用最少 "
                f"{minimum_segments} 个 Segment，实际为 {len(segments)} 个。"
            )

    for index, creator in enumerate(creators, 1):
        if not isinstance(creator, Mapping):
            raise LocalPromptError(f"第 {index} 个 Creator 必须是对象。")
        for key in ("creatorId", "role", "appearsInSegments", "consistencyReason", "prompt"):
            if key not in creator:
                raise LocalPromptError(f"第 {index} 个 Creator 缺少 {key}。")

    return {
        "videoPrompts": dict(video_prompts),
        "creatorPrompts": dict(creator_prompts),
        "segments": list(segments),
        "summary": video_prompts.get("summary", ""),
        "success": True,
        "errorMessage": "",
    }
