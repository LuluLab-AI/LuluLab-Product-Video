#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local.retrieval import retrieve as retrieve_v3
from retrieval_terms import lexical, category_fit, country as normalize_country, VISUAL, concepts, CATEGORIES

ASSET_TYPES = ("STRUCTURE", "HOOK", "SCENE", "CONFLICT", "ACTION", "PROOF", "CTA")

# These are not product claims. They only normalize already-confirmed selling-point wording
# into retrieval concepts so cross-category mechanisms can match each other.
MECHANISM_ALIASES: dict[str, tuple[str, ...]] = {
    **VISUAL,
    "CLEAN": ("清洁", "去污", "去渍", "clean", "stain"),
    "SMOOTH": ("顺滑", "润滑", "减少阻力", "smooth", "lubric"),
    "STRONG": ("强力", "高扭矩", "大扭矩", "强劲", "strong", "torque", "powerful"),
    "FAST": ("快速", "省时", "高效", "fast", "quick", "speed"),
    "WATERPROOF": ("防水", "防泼水", "waterproof", "water resistant"),
    "ABSORB": ("吸收", "吸水", "absorb"),
    "REMOVE": ("去除", "拆卸", "移除", "remove", "detach"),
    "FIX": ("修复", "固定", "维修", "repair", "fix"),
    "PROTECT": ("保护", "防护", "protect"),
    "SAVE_SPACE": ("收纳", "节省空间", "省空间", "save space", "compact"),
    "EASY_TO_USE": ("省力", "易用", "容易操作", "easy to use", "effortless"),
}

TRANSFER_POLICIES = {
    "STRUCTURE": "universal_by_default",
    "HOOK": "universal_by_default",
    "CTA": "universal_by_default_market_sensitive",
    "SCENE": "soft_category_and_scenario_constraint",
    "CONFLICT": "soft_category_and_scenario_constraint",
    "ACTION": "strict_physical_validation",
    "PROOF": "strict_product_mechanism_and_physical_validation",
}


def default_db_path() -> Path:
    env = os.getenv("LULULAB_VIRAL_DB")
    return Path(env).expanduser() if env else Path.home() / ".lululab" / "viral_knowledge" / "viral.db"


def text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).strip()


def parse_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [text(x) for x in v if text(x)]
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        try:
            x = json.loads(s)
            if isinstance(x, list):
                return [text(i) for i in x if text(i)]
        except Exception:
            pass
        return [s]
    return [text(v)] if text(v) else []


def rowv(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def tokens(value: str) -> list[str]:
    raw = re.split(r"[\s,，。；;、/|:_\-]+", value.lower())
    out: list[str] = []
    for x in raw:
        x = x.strip()
        if len(x) >= 2 and x not in out:
            out.append(x)
    return out[:100]


def norm(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if math.isnan(x) or math.isinf(x):
        return default
    if x > 1:
        x /= 100.0
    return max(0.0, min(1.0, x))


def lexical_score(query_text: str, search_text: str) -> float:
    return lexical(query_text, search_text)


def canonical_mechanisms(values: list[str] | str) -> set[str]:
    vals = parse_list(values) if not isinstance(values, list) else values
    joined = " ".join(text(v).lower() for v in vals if text(v))
    out: set[str] = set()
    # Preserve explicit canonical values supplied by ProductProfile.
    for v in vals:
        upper = text(v).upper().replace(" ", "_")
        if upper in MECHANISM_ALIASES:
            out.add(upper)
    for key, aliases in MECHANISM_ALIASES.items():
        if any(alias in joined for alias in aliases):
            out.add(key)
    return out


def _mechanism_terms(profile: dict[str, Any]) -> list[str]:
    raw: list[str] = []
    for key in ("sellingPointMechanisms", "sellingPointTypes", "desiredProofTypes", "possibleProofTypes"):
        raw.extend(parse_list(profile.get(key)))
    raw.extend(sorted(canonical_mechanisms(raw)))
    return list(dict.fromkeys(x for x in raw if x))


def mechanism_score(profile: dict[str, Any], candidate_values: list[str], candidate_text: str = "") -> float:
    wanted = _mechanism_terms(profile)
    if not wanted:
        return 0.0
    candidate_all = list(candidate_values) + [candidate_text]
    wanted_c = canonical_mechanisms(wanted)
    cand_c = canonical_mechanisms(candidate_all)
    canonical = len(wanted_c & cand_c) / max(1, len(wanted_c)) if wanted_c else 0.0
    lexical = lexical_score(" ".join(wanted), " ".join(candidate_all))
    return min(1.0, 0.65 * canonical + 0.35 * lexical)


def category_score(profile: dict[str, Any], industry: str, category: str, search_text: str, *, default: float = 0.0) -> float:
    q = " ".join([text(profile.get("industry")), text(profile.get("category")), text(profile.get("productType"))]).lower()
    target = " ".join([industry, category, search_text]).lower()
    if not q.strip():
        return default
    qts = tokens(q)
    if not qts:
        return default
    hit = sum(1 for t in qts if t in target)
    exact = 0.35 if text(profile.get("category")).lower() == category.lower() and category else 0.0
    return max(category_fit(q, target), min(1.0, hit / max(1, min(len(qts), 4)) + exact))


def scenario_score(profile: dict[str, Any], candidate_values: list[str], candidate_text: str = "") -> float:
    wanted = parse_list(profile.get("useScenarios"))
    if not wanted:
        return 0.5
    return lexical_score(" ".join(wanted), " ".join(candidate_values) + " " + candidate_text)


def country_score(profile: dict[str, Any], applicable: list[str] | str) -> float:
    country = normalize_country(profile.get("targetCountry"))
    values = [normalize_country(v) for v in parse_list(applicable)]
    if not country or not values:
        return 0.55
    return 1.0 if country in values else 0.3


def trend_score(label: Any, hot_score: Any = None, final_score: Any = None, fallback: Any = None) -> float:
    labels = {"RISING_FAST": 1.0, "RISING": 0.78, "NORMAL": 0.45}
    label_s = labels.get(text(label).upper(), 0.5)
    numeric_candidates = [v for v in (hot_score, final_score) if v is not None]
    numeric = max((norm(v) for v in numeric_candidates), default=norm(fallback))
    return 0.55 * label_s + 0.45 * numeric


def _profile_text(profile: dict[str, Any]) -> str:
    fields = [
        profile.get("industry"), profile.get("category"), profile.get("productType"),
        profile.get("targetAudience"), profile.get("targetCountry"),
        profile.get("productProblem"), profile.get("creativeDirection")
    ]
    for key in (
        "useScenarios", "painPoints", "sellingPointTypes", "sellingPointMechanisms",
        "desiredProofTypes", "possibleProofTypes", "keywords"
    ):
        fields.extend(parse_list(profile.get(key)))
    return " ".join(text(x) for x in fields if text(x))


def _contract(row):
    try:
        obj = json.loads(rowv(row, "contract_json", "{}") or "{}")
        return obj if isinstance(obj, dict) else {}
    except (ValueError, TypeError):
        return {}


def _asset_contract(conn, row):
    contract = _contract(row)
    evidence, constraints = [], []
    if "provenance_json" in table_columns(conn, "bundle_assets"):
        rows = conn.execute(
            """SELECT ba.provenance_json,gb.contract_json,gb.avoid_json
               FROM bundle_assets ba JOIN gene_bundles gb ON gb.id=ba.bundle_id
               WHERE ba.asset_id=? AND gb.approved=1""", (rowv(row, "id"),)).fetchall()
        for link in rows:
            if _contract(link).get('generationReadiness') == 'needs_review':
                continue
            provenance = json.loads(link["provenance_json"] or "{}")
            if provenance.get("analysisVersion") not in ('2.3', '2.4'):
                continue
            refs = provenance.get("evidenceRefs") or []
            for item in provenance.get("evidenceCatalog") or []:
                if item.get("id") in refs:
                    evidence.append({**item, "sourceUrl": provenance.get("sourceUrl"),
                                     "analysisId": provenance.get("analysisId")})
            bc = _contract(link)
            constraints += (bc.get("transferConditions") or []) + (bc.get("incompatibleUses") or [])
            constraints += parse_list(link["avoid_json"])
    return {**contract, "sourceClass": rowv(row, "source_class", "UNKNOWN"),
            "evidence": evidence, "sourceConstraints": list(dict.fromkeys(constraints)),
            "requiresReview": not bool(evidence and contract.get("promptSpec")) or contract.get('generationReadiness') == 'needs_review'}


def _bundle_assets(conn: sqlite3.Connection, bundle_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT va.*,ba.role,ba.sort_order
           FROM bundle_assets ba JOIN viral_assets va ON va.id=ba.asset_id
           WHERE ba.bundle_id=? ORDER BY ba.sort_order ASC""",
        (bundle_id,),
    ).fetchall()
    out = []
    for r in rows:
        out.append({
            **_asset_contract(conn, r),
            "assetKey": rowv(r, "asset_key", ""), "assetType": rowv(r, "asset_type", ""),
            "name": rowv(r, "name", ""), "pattern": rowv(r, "pattern", ""),
            "abstractPattern": rowv(r, "abstract_pattern", ""), "function": rowv(r, "function", ""),
            "timing": rowv(r, "timing", ""),
            "applicableCategories": parse_list(rowv(r, "applicable_categories_json", "[]")),
            "applicableProducts": parse_list(rowv(r, "applicable_products_json", "[]")),
            "applicableVideoTypes": parse_list(rowv(r, "applicable_video_types_json", "[]")),
            "applicableCountries": parse_list(rowv(r, "applicable_countries_json", "[]")),
            "applicableSellingPoints": parse_list(rowv(r, "applicable_selling_points_json", "[]")),
            "constraints": parse_list(rowv(r, "constraints_json", "[]")),
            "searchKeywords": parse_list(rowv(r, "search_keywords_json", "[]")),
            "qualityScore": rowv(r, "quality_score"), "reusabilityScore": rowv(r, "reusability_score"),
            "aiGeneratableScore": rowv(r, "ai_generatable_score"), "role": rowv(r, "role", "support")
        })
    return out


def _bundle_query(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    gb_cols = table_columns(conn, "gene_bundles")
    src_cols = table_columns(conn, "sources")
    optional = ("views_per_hour", "hot_score", "knowledge_score", "final_candidate_score", "trend_label", "published_at")
    aliases = []
    can_join = bool(src_cols) and "source_id" in gb_cols and "id" in src_cols
    for name in optional:
        if can_join and name in src_cols:
            aliases.append(f"s.{name} AS source_{name}")
        else:
            aliases.append(f"NULL AS source_{name}")
    sql = "SELECT gb.*, " + ",".join(aliases) + " FROM gene_bundles gb"
    if can_join:
        sql += " LEFT JOIN sources s ON s.id=gb.source_id"
    sql += " WHERE gb.approved=1"
    return conn.execute(sql).fetchall()


def _asset_source_context(conn: sqlite3.Connection, asset_id: int) -> dict[str, Any]:
    gb_cols = table_columns(conn, "gene_bundles")
    src_cols = table_columns(conn, "sources")
    if not src_cols or "source_id" not in gb_cols:
        return {"trendScore": 0.5, "trendLabels": [], "sourceCategories": []}
    wanted = [x for x in ("trend_label", "hot_score", "final_candidate_score", "views_per_hour") if x in src_cols]
    select = ["gb.category AS bundle_category"] + [f"s.{x} AS {x}" for x in wanted]
    rows = conn.execute(
        f"""SELECT {','.join(select)} FROM bundle_assets ba
             JOIN gene_bundles gb ON gb.id=ba.bundle_id
             LEFT JOIN sources s ON s.id=gb.source_id
             WHERE ba.asset_id=? AND gb.approved=1""",
        (asset_id,),
    ).fetchall()
    if not rows:
        return {"trendScore": 0.5, "trendLabels": [], "sourceCategories": []}
    scores = [trend_score(rowv(r, "trend_label"), rowv(r, "hot_score"), rowv(r, "final_candidate_score")) for r in rows]
    labels = list(dict.fromkeys(text(rowv(r, "trend_label")) for r in rows if text(rowv(r, "trend_label"))))
    cats = list(dict.fromkeys(text(rowv(r, "bundle_category")) for r in rows if text(rowv(r, "bundle_category"))))
    vph = max((float(rowv(r, "views_per_hour") or 0) for r in rows), default=0.0)
    return {"trendScore": max(scores) if scores else 0.5, "trendLabels": labels, "sourceCategories": cats, "maxViewsPerHour": vph}


def _asset_compatibility(profile: dict[str, Any], a: sqlite3.Row, asset_type: str, source_ctx: dict[str, Any]) -> dict[str, Any]:
    app_categories = parse_list(rowv(a, "applicable_categories_json", "[]"))
    app_products = parse_list(rowv(a, "applicable_products_json", "[]"))
    app_scenarios = parse_list(rowv(a, "search_keywords_json", "[]"))
    app_selling = parse_list(rowv(a, "applicable_selling_points_json", "[]"))
    search_text = text(rowv(a, "search_text", ""))
    source_categories = source_ctx.get("sourceCategories") or []
    cat_target = " ".join(app_categories + app_products + source_categories + [search_text])
    cat = category_score(profile, "", "", cat_target)
    mech = mechanism_score(profile, app_selling, search_text)
    scen = scenario_score(profile, app_scenarios, search_text)
    country = country_score(profile, parse_list(rowv(a, "applicable_countries_json", "[]")))
    if asset_type in ("STRUCTURE", "HOOK"):
        compatibility = 0.15 * cat + 0.55 * mech + 0.30 * scen
    elif asset_type == "CTA":
        compatibility = 0.10 * cat + 0.15 * mech + 0.15 * scen + 0.60 * country
    elif asset_type in ("SCENE", "CONFLICT"):
        compatibility = 0.40 * cat + 0.20 * mech + 0.40 * scen
    elif asset_type == "ACTION":
        compatibility = 0.30 * cat + 0.50 * mech + 0.20 * scen
    else:  # PROOF
        compatibility = 0.25 * cat + 0.60 * mech + 0.15 * scen
    explicit_mechanism_mismatch = bool(app_selling and _mechanism_terms(profile) and mech < 0.18)
    requires_physical = asset_type in ("ACTION", "PROOF")
    hard_warning = explicit_mechanism_mismatch and requires_physical
    reasons = []
    if asset_type in ("STRUCTURE", "HOOK") and cat < 0.35:
        reasons.append("允许跨品类：优先迁移抽象机制，不复制原品类动作/产品事实")
    if requires_physical:
        reasons.append("必须由 AI Rerank 校验当前产品真实用法、卖点与物理可执行性")
    if hard_warning:
        reasons.append("已检测到卖点机制低匹配，除非能做等效且真实的最小适配，否则不得选用")
    return {
        "transferPolicy": TRANSFER_POLICIES[asset_type],
        "compatibilityScore": round(compatibility, 4),
        "categoryFit": round(cat, 4), "mechanismFit": round(mech, 4), "scenarioFit": round(scen, 4),
        "countryFit": round(country, 4), "requiresPhysicalValidation": requires_physical,
        "lowMechanismMatchWarning": hard_warning, "notes": reasons,
    }


def search_candidates(db: Path, request: dict[str, Any], profile: dict[str, Any], bundle_top: int = 30, asset_top: int = 30) -> dict[str, Any]:
    if not db.exists():
        return {"schemaVersion": "2.3", "status": "unavailable", "source": "local-sqlite", "bundles": [], "assetPools": {}, "warning": f"本地爆款库不存在：{db}"}
    conn = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    if 'creative_patterns' in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
        conn.close()
        from local.product_profile import normalize_profile
        return retrieve_v3(db, normalize_profile(request, profile),
                           recall_limit=min(max(bundle_top, asset_top, 1), 80),
                           shortlist_limit=min(max(bundle_top, 1), 20))
    try:
        rows = _bundle_query(conn)
    except sqlite3.Error as exc:
        return {"schemaVersion": "2.3", "status": "unavailable", "source": "local-sqlite", "bundles": [], "assetPools": {}, "warning": f"本地爆款库不可用：{exc}"}
    if not rows:
        return {"schemaVersion": "2.3", "status": "unavailable", "source": "local-sqlite", "bundles": [], "assetPools": {}, "warning": "本地爆款库暂无已审核 Gene Bundle"}

    uc = request.get("userConfig") or {}
    profile = dict(profile or {})
    profile.setdefault("targetCountry", (request.get("productBrief") or {}).get("targetCountry"))
    profile.setdefault("targetAudience", (request.get("productBrief") or {}).get("targetAudience"))
    profile['normalizedCountry'] = normalize_country(profile.get('targetCountry'))
    profile['normalizedCategories'] = sorted(concepts(' '.join(text(profile.get(k)) for k in ('industry','category','productType')), CATEGORIES))
    query_text = _profile_text(profile)
    country = normalize_country(profile.get("targetCountry"))

    scored: list[tuple[float, sqlite3.Row, dict[str, float]]] = []
    for r in rows:
        search_text = text(rowv(r, "search_text", ""))
        cat = category_score(profile, text(rowv(r, "industry", "")), text(rowv(r, "category", "")), search_text)
        lex = lexical_score(query_text, search_text)
        mech = mechanism_score(profile, parse_list(rowv(r, "selling_point_types_json", "[]")), search_text)
        row_country = normalize_country(rowv(r, "country", ""))
        country_match = 0.55 if not country or not row_country else (1.0 if country == row_country else 0.35)
        quality = norm(rowv(r, "quality_score"))
        reuse = norm(rowv(r, "reusability_score"))
        ai = norm(rowv(r, "ai_generatable_score"))
        commercial = norm(rowv(r, "commercial_clarity_score"))
        trend = trend_score(
            rowv(r, "source_trend_label"), rowv(r, "source_hot_score"),
            rowv(r, "source_final_candidate_score"), rowv(r, "viral_score")
        )
        # Category is deliberately only a soft signal. Mechanism and reusability allow cross-category transfer.
        score = (
            0.12 * cat + 0.25 * mech + 0.10 * lex + 0.05 * country_match +
            0.13 * quality + 0.10 * reuse + 0.05 * ai + 0.05 * commercial + 0.05 * trend
        )
        scored.append((score, r, {"category": cat, "mechanism": mech, "lexical": lex, "trend": trend}))
    scored.sort(key=lambda x: x[0], reverse=True)

    bundles = []
    for score, r, parts in scored[: max(1, min(bundle_top, 50))]:
        bundles.append({
            **_contract(r),
            "knowledgeClass": rowv(r, "knowledge_class", "UNKNOWN"),
            "requiresReview": _contract(r).get("bundleVersion") not in ('2.3', '2.4') or _contract(r).get('generationReadiness') == 'needs_review',
            "dataCompleteness": {k: rowv(r, k) is not None for k in ('quality_score', 'reusability_score', 'ai_generatable_score', 'commercial_clarity_score')},
            "bundleKey": rowv(r, "bundle_key", ""), "score": round(max(0.0, min(1.0, score)), 4),
            "title": rowv(r, "title", ""), "industry": rowv(r, "industry", ""), "category": rowv(r, "category", ""),
            "videoType": rowv(r, "video_type", ""), "country": rowv(r, "country", ""),
            "productProblem": rowv(r, "product_problem", ""),
            "sellingPointTypes": parse_list(rowv(r, "selling_point_types_json", "[]")), "summary": rowv(r, "summary", ""),
            "suitableIndustries": parse_list(rowv(r, "suitable_industries_json", "[]")),
            "suitableProducts": parse_list(rowv(r, "suitable_products_json", "[]")),
            "suitableScenarios": parse_list(rowv(r, "suitable_scenarios_json", "[]")), "avoid": parse_list(rowv(r, "avoid_json", "[]")),
            "match": {k: round(v, 4) for k, v in parts.items()},
            "trend": {
                "label": text(rowv(r, "source_trend_label")),
                "viewsPerHour": rowv(r, "source_views_per_hour"),
                "hotScore": rowv(r, "source_hot_score"),
                "knowledgeScore": rowv(r, "source_knowledge_score"),
                "finalCandidateScore": rowv(r, "source_final_candidate_score"),
                "trendScore": round(parts["trend"], 4),
            },
            "assets": _bundle_assets(conn, int(rowv(r, "id", 0)))
        })

    asset_pools: dict[str, list[dict[str, Any]]] = {}
    for asset_type in ASSET_TYPES:
        ars = conn.execute("""SELECT va.* FROM viral_assets va WHERE asset_type=?
            AND EXISTS (SELECT 1 FROM bundle_assets ba JOIN gene_bundles gb ON gb.id=ba.bundle_id
                        WHERE ba.asset_id=va.id AND gb.approved=1)""", (asset_type,)).fetchall()
        ascored: list[tuple[float, sqlite3.Row, dict[str, Any], dict[str, Any]]] = []
        for a in ars:
            source_ctx = _asset_source_context(conn, int(rowv(a, "id", 0)))
            comp = _asset_compatibility(profile, a, asset_type, source_ctx)
            lex = lexical_score(query_text, text(rowv(a, "search_text", "")))
            quality = norm(rowv(a, "quality_score"))
            reuse = norm(rowv(a, "reusability_score"))
            ai = norm(rowv(a, "ai_generatable_score"))
            source_bonus = min(1.0, math.log1p(rowv(a, "source_count", 1) or 1) / math.log(12))
            trend = float(source_ctx.get("trendScore", 0.5))
            compatibility = float(comp["compatibilityScore"])

            # Different gene types have intentionally different transfer constraints.
            if asset_type in ("STRUCTURE", "HOOK"):
                score = 0.22 * lex + 0.18 * compatibility + 0.20 * quality + 0.20 * reuse + 0.10 * ai + 0.05 * source_bonus + 0.05 * trend
            elif asset_type == "CTA":
                score = 0.18 * lex + 0.22 * compatibility + 0.18 * quality + 0.17 * reuse + 0.10 * ai + 0.05 * source_bonus + 0.05 * trend + 0.05 * comp["countryFit"]
            elif asset_type in ("SCENE", "CONFLICT"):
                score = 0.20 * lex + 0.30 * compatibility + 0.15 * quality + 0.15 * reuse + 0.10 * ai + 0.05 * source_bonus + 0.05 * trend
            elif asset_type == "ACTION":
                score = 0.15 * lex + 0.40 * compatibility + 0.15 * quality + 0.10 * reuse + 0.10 * ai + 0.05 * source_bonus + 0.05 * trend
            else:  # PROOF
                score = 0.10 * lex + 0.45 * compatibility + 0.15 * quality + 0.10 * reuse + 0.10 * ai + 0.05 * source_bonus + 0.05 * trend
            if comp["lowMechanismMatchWarning"]:
                score -= 0.22
            ascored.append((score, a, comp, source_ctx))
        ascored.sort(key=lambda x: x[0], reverse=True)
        asset_pools[asset_type] = [
            {
                **_asset_contract(conn, a), "assetType": asset_type,
                "assetKey": rowv(a, "asset_key", ""), "score": round(max(0.0, min(1.0, s)), 4),
                "name": rowv(a, "name", ""), "pattern": rowv(a, "pattern", ""),
                "abstractPattern": rowv(a, "abstract_pattern", ""), "function": rowv(a, "function", ""),
                "timing": rowv(a, "timing", ""),
                "applicableCategories": parse_list(rowv(a, "applicable_categories_json", "[]")),
                "applicableProducts": parse_list(rowv(a, "applicable_products_json", "[]")),
                "applicableVideoTypes": parse_list(rowv(a, "applicable_video_types_json", "[]")),
                "applicableCountries": parse_list(rowv(a, "applicable_countries_json", "[]")),
                "applicableSellingPoints": parse_list(rowv(a, "applicable_selling_points_json", "[]")),
                "constraints": parse_list(rowv(a, "constraints_json", "[]")),
                "searchKeywords": parse_list(rowv(a, "search_keywords_json", "[]")),
                "sourceCount": rowv(a, "source_count", 1), "compatibility": comp,
                "dataCompleteness": {k: rowv(a, k) is not None for k in ('quality_score', 'reusability_score', 'ai_generatable_score')},
                "sourceTrend": source_ctx,
            }
            for s, a, comp, source_ctx in ascored[: max(1, min(asset_top, 50))]
        ]

    version = datetime.fromtimestamp(db.stat().st_mtime, tz=timezone.utc).isoformat()
    all_zero = all(not any(parts[k] for k in ('category', 'mechanism', 'lexical')) for _, _, parts in scored)
    conn.close()
    return {
        "schemaVersion": "2.3", "status": "ready", "source": "local-sqlite", "version": version,
        "retrievalDiagnostics": {"lexicalOnly": True, "allZeroMatch": all_zero,
            "semanticRerankRequired": True, "message": '全部零匹配，须重新画像或显式跨品类重排；不是高相关召回' if all_zero else '词面/概念粗召回，仍需语义重排'},
        "productProfile": profile, "bundles": bundles, "assetPools": asset_pools,
        "plannerRule": (
            "先按产品机制/真实痛点/使用场景 AI Rerank Gene Bundle；品类不是硬过滤。"
            "STRUCTURE/HOOK/CTA允许跨品类迁移；SCENE/CONFLICT中等约束；ACTION/PROOF必须严格校验卖点机制和物理可执行性。"
            "趋势仅作为小权重/同等适配时的优先信号；同批次避免重复STRUCTURE+HOOK+PROOF组合。"
        ),
        "warning": ""
    }


def build_prompt_context(blueprint: dict[str, Any], candidates: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(candidates, dict) and 'candidates' in candidates:
        raise ValueError('v3 不再 build-context；请先生成 Execution Spec，再用 local_prompt.py --execution-spec')
    from blueprint_contract import resolve_blueprint
    blueprint = resolve_blueprint(blueprint, candidates)
    required = ["blueprintId", "primaryBundleKey", "structure", "hook"]
    missing = [k for k in required if not blueprint.get(k)]
    if missing:
        raise ValueError(f"Creative Blueprint 缺少字段：{','.join(missing)}")

    def pat(v: Any) -> str:
        if isinstance(v, dict):
            return text(v.get("pattern") or v.get("abstractPattern") or v.get("name"))
        return text(v)

    actions = blueprint.get("actions") or []
    action_text = " → ".join(pat(x) for x in actions if pat(x))
    scene = pat(blueprint.get("scene"))
    conflict = pat(blueprint.get("conflict"))
    proof = pat(blueprint.get("proof"))
    cta = pat(blueprint.get("cta"))
    primary = text(blueprint.get("primaryBundleKey"))
    prompt = "；".join(x for x in [
        f"Primary Gene Bundle：{primary}" if primary else "",
        f"场景：{scene}" if scene else "",
        f"冲突：{conflict}" if conflict else "",
        f"动作链：{action_text}" if action_text else "",
        f"示意演示（不是真实功效证明）：{proof}" if proof else f"不使用Proof：{text(blueprint.get('proofOmissionReason'))}",
        f"CTA：{cta}" if cta else "",
        f"卖点映射：{text(blueprint.get('sellingPointMapping'))}" if text(blueprint.get('sellingPointMapping')) else "",
        f"跨品类迁移约束：{text(blueprint.get('transferNotes'))}" if text(blueprint.get('transferNotes')) else "",
        f"组合理由：{text(blueprint.get('rationale'))}" if text(blueprint.get('rationale')) else "",
    ] if x)
    prompt += "\n强制约束：" + text(blueprint.get("avoid"))
    prompt += "\n来源局限：" + text(blueprint.get("sourceLimitations"))
    prompt += "\n开场落实：" + json.dumps(blueprint.get('hookRealization'), ensure_ascii=False)
    prompt += "\n结构落实：" + json.dumps(blueprint.get('structureRealization'), ensure_ascii=False)
    prompt += "\n已通过结构校验的资产合同（必须落实状态、动作、构图、节奏、条件和降级方案）：" + json.dumps(blueprint["resolvedAssets"], ensure_ascii=False)
    prompt += "\n禁止把原片功效、平台文案、达人声称或AI生成画面当作当前产品的真实效果证据；不得保证爆款或转化。"
    conversion = "；".join(x for x in [f"Proof：{proof}" if proof else "", f"CTA：{cta}" if cta else ""] if x)
    return {
        "schemaVersion": "1.0",
        "status": "ready",
        "source": "local-viral-creative-blueprint",
        "version": "2.4",
        "matches": [{
            "templateId": text(blueprint["blueprintId"]),
            "score": blueprint.get('retrievalScore', 0.0),
            "title": text(blueprint.get("title")) or "爆款知识库 Creative Blueprint",
            "hook": pat(blueprint.get("hook")),
            "structure": pat(blueprint.get("structure")),
            "shotRhythm": text(blueprint.get("shotRhythm")),
            "conversionPattern": conversion,
            "sellingPoints": text(blueprint.get("sellingPointMapping")),
            "avoid": "；".join(parse_list(blueprint.get("avoid"))),
            "prompt": prompt,
        }],
        "warning": "候选分为词面/概念粗召回分，不是语义相关性或生成质量保证"
    }


def mark_used(db: Path, bundle_keys: list[str], asset_keys: list[str]) -> dict[str, int]:
    if not db.exists():
        raise ValueError("数据库不存在")
    conn = sqlite3.connect(db)
    now = datetime.now(timezone.utc).isoformat()
    b = 0
    a = 0
    for key in bundle_keys:
        cur = conn.execute("UPDATE gene_bundles SET use_count=use_count+1,last_used_at=? WHERE bundle_key=?", (now, key))
        b += cur.rowcount
    for key in asset_keys:
        cur = conn.execute("UPDATE viral_assets SET use_count=use_count+1,last_used_at=? WHERE asset_key=?", (now, key))
        a += cur.rowcount
    conn.commit()
    return {"bundlesUpdated": b, "assetsUpdated": a}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("search", "build-context", "mark-used"))
    p.add_argument("--db", type=Path, default=default_db_path())
    p.add_argument("--input", type=Path)
    p.add_argument("--product-profile", type=Path)
    p.add_argument("--candidate-pack", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--bundle-top", type=int, default=30)
    p.add_argument("--asset-top", type=int, default=30)
    p.add_argument("--bundle-ids", default="")
    p.add_argument("--asset-ids", default="")
    a = p.parse_args()

    if a.command == "search":
        if not a.input or not a.product_profile:
            p.error("search requires --input and --product-profile")
        request = json.loads(a.input.read_text(encoding="utf-8"))
        profile = json.loads(a.product_profile.read_text(encoding="utf-8"))
        out_obj = search_candidates(a.db, request, profile, a.bundle_top, a.asset_top)
    elif a.command == "build-context":
        if not a.input or not a.candidate_pack:
            p.error("build-context requires --input and --candidate-pack")
        blueprint = json.loads(a.input.read_text(encoding="utf-8"))
        candidates = json.loads(a.candidate_pack.read_text(encoding="utf-8"))
        out_obj = build_prompt_context(blueprint, candidates)
    else:
        bundles = [x.strip() for x in a.bundle_ids.split(",") if x.strip()]
        assets = [x.strip() for x in a.asset_ids.split(",") if x.strip()]
        out_obj = mark_used(a.db, bundles, assets)

    out = json.dumps(out_obj, ensure_ascii=False, indent=2)
    if a.output:
        a.output.write_text(out, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
