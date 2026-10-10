"""Hybrid recall over approved v3 Creative Patterns; no network or generated claims."""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any

from local.repository import read_patterns
from scripts.retrieval_terms import country as normalize_country, terms as bilingual_terms


def _terms(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [word for item in value.values() for word in _terms(item)]
    if isinstance(value, list):
        return [word for item in value for word in _terms(item)]
    return sorted(bilingual_terms(value))


def _cosine(left: Any, right: Any) -> float | None:
    if not isinstance(left, list) or not isinstance(right, list) or not left or len(left) != len(right):
        return None
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in left + right):
        return None
    denominator = math.sqrt(sum(x*x for x in left) * sum(x*x for x in right))
    return max(0.0, sum(a*b for a,b in zip(left,right)) / denominator) if denominator else None


def _bm25(query: list[str], document: list[str], df: Counter, corpus: int, average_length: float) -> float:
    frequencies = Counter(document)
    score = 0.0
    for term in set(query):
        count = frequencies[term]
        if count:
            inverse = math.log1p((corpus - df[term] + .5) / (df[term] + .5))
            score += inverse * count * 2.2 / (count + 1.2 * (.25 + .75 * len(document) / max(1,average_length)))
    return score


def retrieve(db: Path, profile: dict[str, Any], recall_limit: int = 80,
             shortlist_limit: int = 20) -> dict[str, Any]:
    if not 1 <= shortlist_limit <= recall_limit <= 80:
        raise ValueError("候选上限必须是 1..80 且 shortlist 不超过 recall")
    patterns = read_patterns(db)
    if not patterns:
        return {"status": "no_usable_knowledge", "strategyUsed": "DIRECT",
                "fallbackReason": "NO_APPROVED_V3_PATTERNS", "candidates": [],
                "diagnostics": {"patternCount": 0, "semanticAvailable": False,
                                "message": "旧版 Bundle 不等于已审核 v3 Creative Pattern"}}
    query = _terms([profile.get(k) for k in ("industry","category","productType","painPoints",
              "sellingPoints","useScenarios","problemMechanisms","solutionMechanisms",
              "interactionMechanisms","proofMechanisms","creativeRequirement")])
    mechanism = set(_terms([profile.get(k) for k in ("problemMechanisms","solutionMechanisms",
                              "interactionMechanisms","proofMechanisms")]))
    docs = [_terms([p["pattern"].get("mechanismTags"),p["pattern"].get("abstractFlow"),
                    p["pattern"].get("requiredRelationships"), p["pattern"].get("replaceableSlots"),
                    p["category"], p["executionPattern"].get("beatTimeline")]) for p in patterns]
    df = Counter(word for doc in docs for word in set(doc))
    avg = sum(map(len,docs)) / len(docs)
    raw = []
    embedding_model = profile.get("embeddingModel")
    semantic_available = False
    for p, doc in zip(patterns, docs):
        match = len(mechanism & set(doc)) / max(1,len(mechanism)) if mechanism else 0.0
        lexical = _bm25(query, doc, df, len(docs), avg)
        semantic = _cosine(profile.get("embedding"), p["embeddings"].get(embedding_model)) if embedding_model else None
        semantic_available |= semantic is not None
        raw.append((p, match, lexical, semantic))
    lexical_max = max((x[2] for x in raw), default=0.0)
    candidates = []
    for p, structured, lexical, semantic in raw:
        scores = p["scores"]
        strength = (scores.get("creativeStrength") or 0) / 5
        transfer = (scores.get("transferability") or 0) / 5
        generatable = (scores.get("aiGeneratable") or 0) / 5
        country_match = 1.0 if not p["country"] or normalize_country(p["country"]) == normalize_country(profile.get("targetCountry")) else .5
        feedback = p["feedback"]
        production = (feedback["renderPassRate"] or 0) if feedback["rankingEligible"] else 0
        # Trend is intentionally absent: market discovery already used it upstream.
        score = (.31 * structured + .25 * (lexical/lexical_max if lexical_max else 0) +
                 .14 * (semantic or 0) + .10 * transfer + .08 * generatable + .06 * strength +
                 .03 * min(1, (p["independentVideoCount"] or 1)/5) + .02 * production +
                 .01 * country_match)
        candidates.append({**{k:v for k,v in p.items() if k != "embeddings"},
                           "recallScore": round(score,4),
                           "match": {"structuredMechanism": round(structured,4),
                                     "bm25": round(lexical,4), "semantic": semantic,
                                     "semanticModel": embedding_model if semantic is not None else None}})
    candidates.sort(key=lambda p:p["recallScore"], reverse=True)
    all_zero = all(not (c["match"]["structuredMechanism"] or c["match"]["bm25"] or c["match"]["semantic"])
                   for c in candidates)
    return {"status": "needs_semantic_review" if all_zero else "ready",
            "strategyUsed": "KNOWLEDGE", "fallbackReason": None,
            "candidates": candidates[:shortlist_limit],
            "diagnostics": {"patternCount": len(patterns), "recalledCount": min(recall_limit,len(patterns)),
                            "semanticAvailable": semantic_available, "allZeroMatch": all_zero,
                            "message": "全部零匹配；不得称为高相关知识，须重新画像或明确跨品类迁移" if all_zero
                                       else "结构机制 + BM25 + 可用时同模型本地向量；仍需 AI 语义重排与物理审核"}}
