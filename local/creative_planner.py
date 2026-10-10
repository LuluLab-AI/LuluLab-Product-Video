"""Check agent-authored batch Blueprints against retrieved Creative Patterns."""
from __future__ import annotations

from typing import Any

from core.contracts import require_text

FORMATS = {"demonstration", "micro_drama", "review", "comparison", "tutorial",
           "reaction", "transformation", "challenge", "hybrid"}


def validate_blueprints(blueprints: list[dict[str, Any]], candidates: list[dict[str, Any]],
                        expected_count: int, confirmed_facts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if len(blueprints) != expected_count or not 1 <= expected_count <= 10:
        raise ValueError("Blueprint 数量必须等于本批视频数量 1～10")
    by_key = {c["patternKey"]: c for c in candidates}
    seen_ids: set[str] = set()
    signatures: set[tuple[str, str, str, str, str]] = set()
    narratives: set[str] = set()
    facts = {f.get("id") for f in (confirmed_facts or []) if isinstance(f,dict) and f.get("id")}
    for index, bp in enumerate(blueprints, 1):
        if not isinstance(bp, dict):
            raise ValueError(f"Blueprint {index} 必须是对象")
        key = require_text(bp.get("patternKey"), f"Blueprint {index}.patternKey")
        source = by_key.get(key)
        if not source:
            raise ValueError(f"Blueprint {index} 引用了未召回/未批准 Pattern")
        required_assets = set(source["pattern"].get("assetKeys") or [])
        if not required_assets or set(bp.get("assetKeys") or []) != required_assets:
            raise ValueError("Blueprint 必须保留 Pattern 关联的全部已审核原子资产")
        restrictions = list(source.get("readinessReasons") or [])
        restrictions.extend(reason for asset in source.get("assets",[])
                            for reason in asset.get("readinessReasons") or [])
        checks = bp.get("limitationChecks") or []
        for limitation in restrictions:
            if not any(isinstance(c,dict) and c.get("limitation") == limitation and
                       isinstance(c.get("handling"),str) and c["handling"].strip() for c in checks):
                raise ValueError("有限可用资产必须逐项说明限制如何处理")
        identity = require_text(bp.get("blueprintId"), "blueprintId")
        if identity in seen_ids:
            raise ValueError("blueprintId 重复")
        seen_ids.add(identity)
        if bp.get("format") not in FORMATS:
            raise ValueError("视频形式必须由 Planner 从受支持的内部标签中选择")
        hypothesis = require_text(bp.get("creativeHypothesis"), "creativeHypothesis")
        hook = require_text(bp.get("hook"), "hook")
        scene = require_text(bp.get("scene"), "scene")
        conflict = str(bp.get("conflict") or "").strip()
        actions = bp.get("actions")
        if not isinstance(actions,list) or not actions or any(not isinstance(a,str) or not a.strip() for a in actions):
            raise ValueError("actions 必须是有实际产品动作的非空数组")
        grounding = bp.get("actionGrounding")
        if not isinstance(grounding,list) or len(grounding) != len(actions):
            raise ValueError("每项产品动作必须有独立的 actionGrounding")
        for action, item in zip(actions,grounding):
            if not isinstance(item,dict) or item.get("action") != action:
                raise ValueError("actionGrounding 必须逐项匹配实际产品动作")
            refs = item.get("factRefs")
            if not isinstance(refs,list) or not refs or not set(refs) <= facts:
                raise ValueError("产品动作必须引用当前产品已确认事实")
            for field in ("initialState","endState","physicalCheck"):
                require_text(item.get(field), f"actionGrounding.{field}")
        proof = str(bp.get("proof") or "").strip()
        if not proof and not str(bp.get("proofOmissionReason") or "").strip():
            raise ValueError("省略 Proof 必须解释，不能编造功效")
        if proof:
            evidence = bp.get("proofGrounding") or {}
            refs = evidence.get("factRefs")
            if not isinstance(refs,list) or not refs or not set(refs) <= facts:
                raise ValueError("Proof 必须引用当前产品已确认事实")
            require_text(evidence.get("physicalCheck"), "proofGrounding.physicalCheck")
        mappings = bp.get("relationshipMappings")
        required = source["pattern"]["requiredRelationships"]
        if not isinstance(mappings,list) or len(mappings) != len(required):
            raise ValueError("必须逐项映射 Creative Pattern.requiredRelationships")
        for relation, mapped in zip(required,mappings):
            if not isinstance(mapped,dict) or mapped.get("sourceRelationship") != relation:
                raise ValueError("requiredRelationships 不得删改或重排")
            require_text(mapped.get("realization"), "relationshipMappings.realization")
            if not isinstance(mapped.get("beatRefs"),list) or not mapped["beatRefs"]:
                raise ValueError("每个必要关系必须映射到最终节拍")
        signature = (bp["format"],hook,scene,conflict,proof)
        if signature in signatures or hypothesis.casefold() in narratives:
            raise ValueError("同批视频不能只换口播或资产编号；需不同创意假设和实际表达")
        signatures.add(signature)
        narratives.add(hypothesis.casefold())
        if source.get("knowledgeClass") == "CREATIVE_REFERENCE" and (proof or bp.get("ctaOrigin") == "source"):
            raise ValueError("CREATIVE_REFERENCE 不能提供产品证明或来源 CTA")
        if bp.get("ctaOrigin") not in (None,"original","source","no-cta"):
            raise ValueError("CTA 必须区分原创、来源或无 CTA")
        if bp.get("ctaOrigin") == "source" and not bp.get("ctaAssetKey"):
            raise ValueError("来源 CTA 需要真实资产引用")
        if bp.get("claimFactRefs") and not set(bp["claimFactRefs"]) <= facts:
            raise ValueError("卖点必须引用当前产品已确认事实")
    return blueprints
