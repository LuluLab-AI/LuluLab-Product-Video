"""Derive and validate a shootable Execution Spec from one reviewed Blueprint."""
from __future__ import annotations

from typing import Any

from core.contracts import require_text


def build_execution_spec(blueprint: dict[str, Any], source: dict[str, Any],
                         duration: int, authored: dict[str, Any]) -> dict[str, Any]:
    if source.get("patternKey") != blueprint.get("patternKey"):
        raise ValueError("Execution Spec 来源 Pattern 与 Blueprint 不一致")
    if not isinstance(authored,dict):
        raise ValueError("Execution Spec 必须是对象")
    if authored.get("blueprintId") != blueprint.get("blueprintId") or authored.get("duration") != duration:
        raise ValueError("Execution Spec 必须绑定 Blueprint 与目标时长")
    if authored.get("format") != blueprint.get("format"):
        raise ValueError("Prompt 阶段不得重新选择视频形式")
    beats = authored.get("beats")
    if not isinstance(beats,list) or not beats:
        raise ValueError("Execution Spec 需要完整时间轴")
    ids: set[str] = set()
    position = 0.0
    visible_hooks = []
    previous_end = None
    for beat in beats:
        if not isinstance(beat,dict):
            raise ValueError("Execution beat 必须是对象")
        ref = require_text(beat.get("beatRef"), "beatRef")
        if ref in ids:
            raise ValueError("Execution beatRef 重复")
        ids.add(ref)
        start,end = beat.get("start"),beat.get("end")
        if not all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in (start,end)) or abs(start-position)>.01 or end<=start or end-start>4:
            raise ValueError("Execution Spec 时间轴必须从0连续、每块不超过4秒")
        position=float(end)
        for field in ("visual","action","camera","audio"):
            require_text(beat.get(field), f"{ref}.{field}")
        for field in ("initialState","endState"):
            state = beat.get(field)
            if not isinstance(state,dict) or not state or any(not isinstance(v,str) or not v.strip() for v in state.values()):
                raise ValueError(f"{ref}.{field} 必须描述非空产品/人物状态")
        if previous_end is not None and previous_end != beat["initialState"] and not str(beat.get("transitionExplanation") or "").strip():
            raise ValueError("相邻节拍状态改变必须说明可见动作或合理剪辑")
        previous_end = beat["endState"]
        if str(blueprint["hook"]) in " ".join(str(beat.get(k) or "") for k in ("visual","action","speech","screenText")):
            visible_hooks.append(beat)
        if beat.get("speech") and not isinstance(beat["speech"],dict):
            raise ValueError("speech 必须包含角色和实际台词")
        if isinstance(beat.get("speech"),dict):
            require_text(beat["speech"].get("role"), "speech.role")
            require_text(beat["speech"].get("text"), "speech.text")
    if abs(position-duration)>.01:
        raise ValueError("Execution Spec 必须覆盖完整视频时长")
    if not visible_hooks or min(b["start"] for b in visible_hooks)>=3:
        raise ValueError("Blueprint Hook 必须在前3秒可感知地落实")
    for mapping in blueprint["relationshipMappings"]:
        if not set(mapping["beatRefs"]) <= ids:
            raise ValueError("必要创意关系引用了不存在的节拍")
    hook_channel = authored.get("hookChannel")
    source_channels = source["pattern"].get("expressionChannels") or [
        channel for asset in source.get("assets",[]) if asset.get("assetType") == "HOOK"
        for channel in asset.get("expressionChannels") or []]
    if hook_channel not in ("speech","text","action","combination"):
        raise ValueError("Hook 需记录语音/文字/动作或组合依赖")
    if any(c in source_channels for c in ("speech","text")) and hook_channel == "action":
        raise ValueError("语义型 Hook 不能静默退化为普通动作")
    if hook_channel in ("text","combination") and authored.get("noOnScreenText"):
        raise ValueError("无字幕/无屏幕文字时必须改成有效口播或重新选 Hook")
    if hook_channel in ("speech","combination") and not any(isinstance(b.get("speech"),dict) and
            str(blueprint["hook"]) in b["speech"].get("text","") for b in visible_hooks):
        raise ValueError("语音型 Hook 缺少实际台词")
    for action in blueprint["actions"]:
        if not any(action in str(b["action"]) for b in beats):
            raise ValueError(f"Blueprint 产品动作未落实：{action}")
    proof = blueprint.get("proof")
    if proof and not any(proof in " ".join(str(b.get(k) or "") for k in ("visual","action")) for b in beats):
        raise ValueError("Blueprint Proof 未落实")
    cta = blueprint.get("cta")
    if cta and not any(cta in " ".join(str(b.get(k) or "") for k in ("visual","action","speech")) for b in beats):
        raise ValueError("Blueprint CTA 未落实")
    for field in ("buyReason","endingIntent","voiceDescription","productContinuity","creatorContinuity"):
        require_text(authored.get(field), field)
    # Source execution ratios are inspiration, not exact absolute timing mandates.
    output = dict(authored)
    output["patternKey"] = source["patternKey"]
    output["requiredRelationshipMappings"] = blueprint["relationshipMappings"]
    output["sourceTimingRatios"] = source["executionPattern"].get("timing") or {}
    output["sourceExecutionInvariants"] = source["executionPattern"].get("executionInvariants") or []
    output["sourceRisks"] = source["executionPattern"].get("generationRisks") or []
    return output
