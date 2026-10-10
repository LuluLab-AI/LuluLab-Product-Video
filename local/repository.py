"""Read approved v3 knowledge and recorded feedback from the local SQLite database."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


def default_db_path() -> Path:
    value = os.getenv("LULULAB_VIRAL_DB")
    return Path(value).expanduser() if value else Path.home() / ".lululab/viral_knowledge/viral.db"


def _json(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw) if raw else fallback
    except (TypeError, ValueError):
        return fallback


def read_patterns(db: Path) -> list[dict[str, Any]]:
    if not db.is_file():
        return []
    conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"creative_patterns", "execution_patterns", "gene_bundles", "viral_assets", "bundle_assets"} <= tables:
            return []
        rows = conn.execute("""SELECT p.*, e.execution_json, b.id AS bundle_id,
                             b.contract_json AS bundle_contract_json,b.category, b.industry,
                             b.country, b.knowledge_class, b.source_id
                             FROM creative_patterns p
                             JOIN execution_patterns e USING(pattern_key)
                             JOIN gene_bundles b ON b.bundle_key=p.bundle_key
                             WHERE b.approved=1 ORDER BY p.pattern_key""").fetchall()
        embeddings = {}
        if "knowledge_embeddings" in tables:
            for r in conn.execute("SELECT pattern_key,model_id,vector_json FROM knowledge_embeddings"):
                embeddings.setdefault(r["pattern_key"], {})[r["model_id"]] = _json(r["vector_json"], [])
        feedback = {}
        if "generation_feedback" in tables:
            for r in conn.execute("""SELECT pattern_key,scores_json,rendered_passed FROM generation_feedback
                                     WHERE review_stage='render-review' AND pattern_key IS NOT NULL"""):
                feedback.setdefault(r["pattern_key"], []).append(r)
        output = []
        for r in rows:
            pattern = _json(r["pattern_json"], {})
            execution = _json(r["execution_json"], {})
            scores = _json(r["scores_json"], {})
            if not pattern.get("requiredRelationships") or not execution.get("beatTimeline"):
                continue
            contract = _json(r["bundle_contract_json"], {})
            if r["knowledge_class"] not in ("COMMERCE_CORE", "CREATIVE_REFERENCE") or contract.get("generationReadiness") not in ("ready", "limited"):
                continue
            linked = conn.execute("""SELECT a.asset_key,a.asset_type,a.contract_json
                         FROM bundle_assets ba JOIN viral_assets a ON a.id=ba.asset_id
                         WHERE ba.bundle_id=?""", (r["bundle_id"],)).fetchall()
            selected_keys = set(pattern.get("assetKeys") or [])
            selected = {a["asset_key"]: a for a in linked if a["asset_key"] in selected_keys}
            if not selected_keys or selected_keys != set(selected):
                continue
            if any(_json(a["contract_json"],{}).get("generationReadiness") not in ("ready", "limited") for a in selected.values()):
                continue
            asset_contracts = [{"assetKey":a["asset_key"],"assetType":a["asset_type"],
                                **_json(a["contract_json"],{})} for a in selected.values()]
            refs = feedback.get(r["pattern_key"], [])
            n = len(refs)
            pass_values = [x["rendered_passed"] for x in refs if x["rendered_passed"] is not None]
            output.append({"patternKey": r["pattern_key"], "bundleKey": r["bundle_key"],
                           "clusterKey": r["cluster_key"], "pattern": pattern,
                           "executionPattern": execution, "scores": scores,
                           "category": r["category"], "industry": r["industry"],
                           "country": r["country"], "knowledgeClass": r["knowledge_class"],
                           "generationReadiness": contract.get("generationReadiness") or "ready",
                           "readinessReasons": contract.get("readinessReasons") or [],
                           "assets": asset_contracts,
                           "sourceId": r["source_id"], "independentVideoCount": r["independent_video_count"],
                           "independentCreatorCount": r["independent_creator_count"],
                           "embeddings": embeddings.get(r["pattern_key"], {}),
                           "feedback": {"sampleCount": n, "rankingEligible": n >= 5,
                                        "renderPassRate": sum(pass_values) / len(pass_values) if n >= 5 and pass_values else None}})
        return output
    finally:
        conn.close()
