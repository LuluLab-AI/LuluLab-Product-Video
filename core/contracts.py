"""Product and render contracts; no provider, database, or prompt implementation."""
from __future__ import annotations

from typing import Any, Mapping


def require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 必须是非空文字")
    return value.strip()


def require_list(value: Any, field: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{field} 必须是数组")
    return value


def product_facts(request: Mapping[str, Any]) -> dict[str, Any]:
    brief = request.get("productBrief")
    if not isinstance(brief, Mapping):
        raise ValueError("productBrief 必须是对象")
    name = require_text(brief.get("productName"), "productName")
    images = require_list(brief.get("productImages") or [], "productImages")
    facts = brief.get("confirmedFacts") or []
    require_list(facts, "confirmedFacts")
    for index, fact in enumerate(facts):
        if not isinstance(fact, Mapping):
            raise ValueError(f"confirmedFacts[{index}] 必须是对象")
        require_text(fact.get("id"), f"confirmedFacts[{index}].id")
        require_text(fact.get("fact"), f"confirmedFacts[{index}].fact")
        require_text(fact.get("source"), f"confirmedFacts[{index}].source")
    return {"productName": name, "sellingPoints": brief.get("sellingPoints") or "",
            "targetCountry": brief.get("targetCountry") or "美国",
            "targetAudience": brief.get("targetAudience") or "",
            "productImages": images, "confirmedFacts": facts}


def render_spec(request: Mapping[str, Any]) -> dict[str, Any]:
    config = request.get("userConfig") or {}
    model = require_text(config.get("videoModel"), "videoModel")
    duration = config.get("duration")
    if isinstance(duration, bool) or not isinstance(duration, int) or not 4 <= duration <= 60:
        raise ValueError("duration 必须是 4～60 秒整数")
    return {"videoModel": model, "duration": duration,
            "aspectRatio": "9:16", "creativeRequirement": request.get("creativeRequirement") or ""}
