"""Translate an approved Execution Spec into model instructions, without new creative decisions."""
from __future__ import annotations

import json
from typing import Any, Mapping

from core.contracts import product_facts, render_spec


def render_execution_prompt(request: Mapping[str, Any], spec: Mapping[str, Any], prompt_language: str = 'zh-CN') -> str:
    facts = product_facts(request)
    render = render_spec(request)
    if not isinstance(spec,Mapping) or spec.get("duration") != render["duration"]:
        raise ValueError("Execution Spec 与视频时长不一致")
    # Deliberately exclude retrieval candidates, provenance, evidence catalogs and raw bundles.
    compact = {key:spec.get(key) for key in ("blueprintId","patternKey","format","duration",
               "beats","hookChannel","buyReason","endingIntent","voiceDescription","mediaLanguage",
               "productContinuity","creatorContinuity","requiredRelationshipMappings",
               "sourceExecutionInvariants","sourceRisks")}
    if prompt_language.split('-')[0] != 'zh':
        return f'''# Sole creative source: reviewed Execution Spec

Translate the Execution Spec below into independently executable video segments for {render['videoModel']}. Write all narrative descriptions in {prompt_language}; write actual dialogue and newly requested visual text in the media language. Preserve every beat, actual spoken line, initial and final state, hook channel and buying reason. Do not redesign the format, opening, setting, conflict, proof, CTA or beat order. A segment is only a model duration container. If the spec cannot be executed, report the error and return to planning; do not invent a new concept.

Product facts: {json.dumps(facts, ensure_ascii=False, separators=(',',':'))}
Creator facts: {json.dumps(request.get('creatorBrief') or {}, ensure_ascii=False, separators=(',',':'))}
Render settings: {json.dumps(render, ensure_ascii=False, separators=(',',':'))}
Execution Spec: {json.dumps(compact, ensure_ascii=False, separators=(',',':'))}

Constraints: the product image fixes product appearance and the creator image fixes identity; actions must be physically credible, with product and person continuity. Do not add unconfirmed effects, prices, promotions, sales figures or certifications. Spoken dialogue in the media language is required by default; complete silence requires an explicit user request. Repeat the complete fixed voice declaration in every speaking segment. Each segment's timeline starts at zero, is continuous and has blocks of at most four seconds. No garbled text or watermarks. Output only the required videoPrompts/creatorPrompts JSON.'''
    return f'''# 唯一创意来源：已审核 Execution Spec

你只把下方 Execution Spec 翻译成可供 {render['videoModel']} 执行的分段视频 Prompt；叙述语言按本次交互语言规则，实际台词与允许新增的画面文字按成片语言规则。保留全部 beat、实际台词、起止状态、Hook 表达渠道和购买理由，不得重新设计形式、开场、场景、冲突、Proof、CTA 或节拍顺序。Segment 只是模型时长容器。若 Spec 不可执行，报告错误并回到 Planner，不得自行编造新创意。

产品事实：{json.dumps(facts, ensure_ascii=False, separators=(',',':'))}
达人事实：{json.dumps(request.get('creatorBrief') or {}, ensure_ascii=False, separators=(',',':'))}
渲染参数：{json.dumps(render, ensure_ascii=False, separators=(',',':'))}
Execution Spec：{json.dumps(compact, ensure_ascii=False, separators=(',',':'))}

硬约束：产品图锁定产品外观，达人图锁定人物身份；物理动作合理，保持产品及人物连续性；无已确认事实不得增加功效、价格、促销、销量或认证；默认有成片语言的明确口播台词，整条无口播只在用户明确选择时允许；每段固定声音句独立完整；每段时间轴从0连续覆盖，单块不超过4秒；无乱码、无水印。输出只用既定 videoPrompts/creatorPrompts JSON。'''


DIRECT_GUIDANCE = '''# Direct 基线模式

本模式不读取知识库，直接根据产品已确认事实与用户特别要求设计一个原创创意假设。可选择演示、微剧情、测评、教程、反应、挑战或混合形式；不得机械套用固定痛点→产品→满意结构，也不得为了凑结构强加 Proof 或 CTA。先在内部建立完整动作、起止状态、开场表达和声音节拍，再生成视频 Prompt。默认明确口播台词，只有用户明确要求整条无口播才例外。'''

DIRECT_GUIDANCE_EN = '''# Direct baseline

Do not consult the knowledge base. Develop one original creative hypothesis from confirmed product facts and the user's specific requirements. Demonstration, micro drama, review, tutorial, reaction, challenge and hybrid formats are available. Do not force a fixed problem-to-solution structure or invent proof or a CTA. Establish the complete action, initial and final states, opening and audio beats before writing video prompts. Include actual spoken dialogue by default; use a fully silent video only when explicitly requested.'''
