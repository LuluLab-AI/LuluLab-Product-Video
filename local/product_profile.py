"""Normalize confirmed product facts into retrieval mechanisms without inventing claims."""
from __future__ import annotations

from typing import Any, Mapping

from core.contracts import product_facts

PROFILE_KEYS = ("industry", "category", "productType", "painPoints", "sellingPoints",
                "useScenarios", "problemMechanisms", "solutionMechanisms",
                "interactionMechanisms", "proofMechanisms", "possibleProofTypes",
                "targetAudience", "targetCountry", "creativeRequirement")
MECHANISM_KEYS = ("problemMechanisms", "solutionMechanisms",
                  "interactionMechanisms", "proofMechanisms")


def normalize_profile(request: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    facts = product_facts(request)
    if not isinstance(profile, Mapping):
        raise ValueError("Product Profile 必须是对象")
    unknown = set(profile) - set(PROFILE_KEYS) - {"confirmedFacts", "embedding", "embeddingModel"}
    if unknown:
        raise ValueError(f"Product Profile 包含旧版或未知字段：{sorted(unknown)}")
    out: dict[str, Any] = {}
    for key in PROFILE_KEYS:
        value = profile.get(key)
        if key in ("painPoints", "sellingPoints", "useScenarios", "possibleProofTypes") + MECHANISM_KEYS:
            if value is None:
                value = []
            if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
                raise ValueError(f"{key} 必须是非空字符串组成的数组")
        else:
            value = value or ""
            if not isinstance(value, str):
                raise ValueError(f"{key} 必须是文字")
        out[key] = value
    if out["targetCountry"] and out["targetCountry"] != facts["targetCountry"]:
        raise ValueError("Product Profile 市场与用户确认事实不一致")
    out["targetCountry"] = facts["targetCountry"]
    out["targetAudience"] = facts["targetAudience"]
    out["creativeRequirement"] = request.get("creativeRequirement") or ""
    out["confirmedFacts"] = profile.get("confirmedFacts") or facts["confirmedFacts"]
    if not isinstance(out["confirmedFacts"], list):
        raise ValueError("confirmedFacts 必须是数组")
    seen_ids: set[str] = set()
    for fact in out["confirmedFacts"]:
        if not isinstance(fact, dict) or any(not isinstance(fact.get(k), str) or not fact[k].strip()
            for k in ("id", "fact", "source")):
            raise ValueError("confirmedFacts 每项需要 id、fact、source")
        if fact["source"] not in ("user", "product-image"):
            raise ValueError("confirmedFacts 来源只能是用户或可见产品图")
        if fact["id"] in seen_ids:
            raise ValueError("confirmedFacts id 重复")
        seen_ids.add(fact["id"])
        if fact["source"] == "product-image" and not facts["productImages"]:
            raise ValueError("图片可见事实必须有产品图")
        tags = fact.get("mechanisms") or []
        if not isinstance(tags,list) or any(not isinstance(x,str) or not x.strip() for x in tags):
            raise ValueError("confirmedFacts.mechanisms 必须是文字数组")
    for original in facts["confirmedFacts"]:
        if not any(f["id"] == original["id"] and f["fact"] == original["fact"] and
                   f["source"] == original["source"] for f in out["confirmedFacts"]):
            raise ValueError("Product Profile 不得修改用户已确认事实")
    if not out["confirmedFacts"] and any(out[k] for k in MECHANISM_KEYS):
        raise ValueError("机制标签必须有 confirmedFacts 溯源；不能凭检索需要新增功效")
    fact_text = " ".join(str(x["fact"]).casefold() for x in out["confirmedFacts"])
    for key in MECHANISM_KEYS:
        for mechanism in out[key]:
            # A precise grounding reference is required, not speculative string overlap.
            if not any(mechanism in str(x.get("mechanisms") or []) for x in out["confirmedFacts"]):
                raise ValueError(f"{key}: {mechanism} 未被 confirmedFacts.mechanisms 明确支持")
    if "embedding" in profile or "embeddingModel" in profile:
        out["embedding"] = profile.get("embedding")
        out["embeddingModel"] = profile.get("embeddingModel")
    return out
