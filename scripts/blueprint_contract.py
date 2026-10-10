"""Resolve blueprints against retrieved, approved assets; never trust copied asset text."""
import copy

def resolve_blueprint(blueprint, candidates):
    if not isinstance(candidates, dict) or candidates.get('status') != 'ready':
        raise ValueError('build-context requires a ready --candidate-pack; legacy blueprints must be re-planned')
    bp = copy.deepcopy(blueprint)
    if (candidates.get('retrievalDiagnostics') or {}).get('allZeroMatch'):
        decision = bp.get('zeroMatchReview') or {}
        if decision.get('decision') != 'cross-category-transfer' or not decision.get('reason') or not decision.get('productGrounding'):
            raise ValueError('all candidates have zero lexical match: re-profile or explicitly justify cross-category transfer')
    if not bp.get('blueprintId') or not bp.get('primaryBundleKey'):
        raise ValueError('blueprintId and primaryBundleKey required')
    bundles = {b['bundleKey']: b for b in candidates.get('bundles', [])}
    primary = bundles.get(bp['primaryBundleKey'])
    if not primary or primary.get('knowledgeClass') not in ('COMMERCE_CORE', 'CREATIVE_REFERENCE') or primary.get('requiresReview', True):
        raise ValueError('primary bundle missing or requires evidence re-audit')
    if primary.get('generationReadiness') == 'needs_review':
        raise ValueError('primary bundle is restricted pending review')
    if primary.get('generationReadiness') == 'limited':
        checks = bp.get('primaryLimitationChecks') or []
        if any(not any(c.get('limitation') == limit and str(c.get('handling','')).strip() for c in checks)
               for limit in primary.get('readinessReasons', [])):
            raise ValueError('limited primary bundle needs primaryLimitationChecks')
    assets = {}
    for pool in candidates.get('assetPools', {}).values():
        for a in pool:
            assets[a['assetKey']] = a
    for b in bundles.values():
        for a in b.get('assets', []):
            assets[a['assetKey']] = a
    profile = candidates.get('productProfile') or {}
    facts = {}
    for fact in profile.get('confirmedFacts', []):
        if isinstance(fact, dict) and fact.get('id') and fact.get('fact') and fact.get('source'):
            if fact['id'] in facts:
                raise ValueError('duplicate confirmedFacts id')
            facts[fact['id']] = fact
    selected = []
    def resolve(value, kind):
        if not isinstance(value, dict):
            raise ValueError(f'{kind} must reference an assetKey')
        a = assets.get(value.get('assetKey'))
        if not a or a.get('assetType') != kind:
            raise ValueError(f'{kind}: unknown assetKey or wrong type')
        if a.get('requiresReview', True) or not a.get('evidence') or not a.get('promptSpec'):
            raise ValueError(f'{kind}: timestamped evidence/promptSpec missing; re-audit source')
        if a.get('generationReadiness') == 'needs_review':
            raise ValueError(f'{kind}: asset needs review')
        limitations = a.get('readinessReasons', [])
        if a.get('generationReadiness') == 'limited':
            checks = value.get('limitationChecks') or []
            if any(not any(c.get('limitation') == limit and str(c.get('handling', '')).strip() for c in checks) for limit in limitations):
                raise ValueError(f'{kind}: limited asset requires explicit handling of each limitation')
            a = copy.deepcopy(a)
            a['limitationChecks'] = checks
        if a.get('sourceClass') not in ('COMMERCE_CORE', 'CREATIVE_REFERENCE'):
            raise ValueError(f'{kind}: unknown sourceClass')
        if kind in ('PROOF', 'CTA') and a['sourceClass'] != 'COMMERCE_CORE':
            raise ValueError(f'{kind}: creative reference cannot supply commerce evidence')
        for key in ('pattern', 'abstractPattern', 'constraints', 'promptSpec', 'proofKind', 'claimLimit', 'expressionChannels', 'requiredStages', 'generationReadiness', 'readinessReasons'):
            if key in value and value[key] != a.get(key):
                raise ValueError(f'{kind}: canonical {key} changed; use adaptation separately')
        a = copy.deepcopy(a)
        if kind in ('ACTION', 'PROOF'):
            adaptation = value.get('adaptation') or {}
            for key in ('initialState', 'action', 'endState', 'riskMitigation'):
                if not isinstance(adaptation.get(key), str) or not adaptation[key].strip():
                    raise ValueError(f'{kind}: adaptation.{key} required')
            refs = adaptation.get('productFactRefs')
            if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in facts for r in refs):
                raise ValueError(f'{kind}: productFactRefs must resolve to confirmedFacts')
            checks = adaptation.get('conditionChecks') or []
            for condition in a['promptSpec'].get('physicalPrerequisites', []):
                matches = [c for c in checks if isinstance(c, dict) and c.get('condition') == condition]
                if not any(c.get('rationale') and isinstance(c.get('productFactRefs'), list) and c['productFactRefs'] and all(isinstance(r, str) and r in facts for r in c['productFactRefs']) for c in matches):
                    raise ValueError(f'{kind}: physical prerequisite not grounded: {condition}')
            if kind == 'PROOF':
                if a.get('proofKind') not in ('demonstration', 'visible-comparison', 'verified-performance'):
                    raise ValueError('creator-claim/unknown cannot be selected as PROOF')
                if adaptation.get('presentation') != 'illustration':
                    raise ValueError('AI-generated PROOF must be an illustration, never authentic efficacy evidence')
            a['adaptation'] = adaptation
            a['currentProductFacts'] = [facts[r] for r in refs]
        selected.append(a)
        return a
    for field, kind in (('structure', 'STRUCTURE'), ('hook', 'HOOK')):
        bp[field] = resolve(bp.get(field), kind)
    if primary.get('contractRevision') == '2.4' or primary.get('bundleVersion') == '2.4':
        realization = bp.get('hookRealization') or {}
        if not realization.get('message') or not realization.get('channels') or not realization.get('beatRef'):
            raise ValueError('Hook needs explicit message, channels and final timeline beatRef')
        source_channels = bp['hook'].get('expressionChannels', [])
        if any(c in source_channels for c in ('speech', 'text')) and not set(realization['channels']) & {'speech', 'text'}:
            raise ValueError('semantic Hook cannot be silently replaced by generic action')
        if not bp.get('structureRealization'):
            raise ValueError('Structure needs stage-to-timeline mapping')
    for field, kind in (('scene', 'SCENE'), ('conflict', 'CONFLICT'), ('proof', 'PROOF'), ('cta', 'CTA')):
        if bp.get(field):
            bp[field] = resolve(bp[field], kind)
    actions = bp.get('actions')
    if not isinstance(actions, list) or not 1 <= len(actions) <= 4:
        raise ValueError('actions must contain 1..4 grounded assets')
    bp['actions'] = [resolve(a, 'ACTION') for a in actions]
    if not bp.get('proof') and not str(bp.get('proofOmissionReason') or '').strip():
        raise ValueError('no PROOF: provide proofOmissionReason, do not invent efficacy')
    primary_keys = {a['assetKey'] for a in primary.get('assets', [])}
    if not any(bp[f]['assetKey'] in primary_keys for f in ('structure', 'hook')):
        raise ValueError('primary bundle must supply STRUCTURE or HOOK')
    constraints = list(bp.get('avoid') or []) + list(primary.get('avoid') or [])
    constraints += list(primary.get('transferConditions') or []) + list(primary.get('incompatibleUses') or [])
    for a in selected:
        constraints += list(a.get('constraints') or []) + list(a.get('sourceConstraints') or [])
        constraints += list(a.get('readinessReasons') or [])
    bp['avoid'] = list(dict.fromkeys(constraints))
    bp['resolvedAssets'] = selected
    bp['knowledgeClass'] = primary['knowledgeClass']
    bp['retrievalScore'] = primary.get('score', 0.0)
    bp['sourceLimitations'] = {k: primary.get(k) for k in ('productRole', 'viralityDrivers', 'creatorDependency', 'observedProducts')}
    return bp
