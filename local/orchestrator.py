#!/usr/bin/env python3
"""Local planning gates only. This CLI never submits or generates a video."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.contracts import render_spec
from core.user_errors import failure
from local.creative_planner import validate_blueprints
from local.execution_spec import build_execution_spec
from local.product_profile import normalize_profile
from local.repository import default_db_path
from local.retrieval import retrieve


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path | None, value: dict):
    body = json.dumps(value, ensure_ascii=False, indent=2)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body + "\n", encoding="utf-8")
    print(body)


def prepare(request: dict, profile: dict, mode: str, db: Path) -> dict:
    if mode not in ("AUTO", "KNOWLEDGE", "DIRECT"):
        raise ValueError("strategy 必须是 AUTO、KNOWLEDGE 或 DIRECT")
    render_spec(request)
    if mode == "DIRECT":
        return {"strategyRequested": mode, "strategyUsed": "DIRECT", "fallbackReason": None,
                "status": "ready", "candidates": [], "diagnostics": {"knowledgeQueried": False}}
    normalized = normalize_profile(request, profile)
    pack = retrieve(db, normalized)
    pack["strategyRequested"] = mode
    pack["productProfile"] = normalized
    if pack["status"] != "ready":
        if mode == "KNOWLEDGE":
            pack["strategyUsed"] = None
            pack["status"] = "blocked"
        else:
            pack["strategyUsed"] = "DIRECT"
            pack["status"] = "ready_direct_fallback"
            pack["fallbackReason"] = pack.get("fallbackReason") or "NO_USABLE_KNOWLEDGE"
    return pack


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--request", type=Path, required=True)
    prep.add_argument("--profile", type=Path, required=True)
    prep.add_argument("--strategy", choices=("AUTO","KNOWLEDGE","DIRECT"), default="AUTO")
    prep.add_argument("--db", type=Path, default=default_db_path())
    prep.add_argument("--output", type=Path)
    plan = sub.add_parser("validate-plan")
    plan.add_argument("--candidate-pack", type=Path, required=True)
    plan.add_argument("--blueprints", type=Path, required=True)
    plan.add_argument("--count", type=int, required=True)
    plan.add_argument("--output", type=Path)
    spec = sub.add_parser("validate-spec")
    spec.add_argument("--request", type=Path, required=True)
    spec.add_argument("--candidate-pack", type=Path, required=True)
    spec.add_argument("--blueprint", type=Path, required=True)
    spec.add_argument("--authored-spec", type=Path, required=True)
    spec.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        if args.command == "prepare":
            output = prepare(_read(args.request), _read(args.profile), args.strategy, args.db)
        elif args.command == "validate-plan":
            pack = _read(args.candidate_pack)
            if pack.get("strategyUsed") != "KNOWLEDGE" or pack.get("status") != "ready":
                raise ValueError("没有可用 v3 知识，不能标记知识库规划")
            blueprints = _read(args.blueprints)
            validate_blueprints(blueprints, pack["candidates"], args.count,
                                (pack.get("productProfile") or {}).get("confirmedFacts") or [])
            output = {"status": "validated", "blueprints": blueprints}
        else:
            request = _read(args.request)
            pack = _read(args.candidate_pack)
            bp = _read(args.blueprint)
            candidate = next((x for x in pack.get("candidates",[]) if x["patternKey"] == bp.get("patternKey")), None)
            if pack.get("status") != "ready" or not candidate:
                raise ValueError("Execution Spec 引用的 v3 Pattern 当前不可用")
            validate_blueprints([bp], [candidate], 1,
                                (pack.get("productProfile") or {}).get("confirmedFacts") or [])
            output = build_execution_spec(bp, candidate, render_spec(request)["duration"], _read(args.authored_spec))
        _write(args.output, output)
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        failure(exc, "PLANNING_INVALID")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
