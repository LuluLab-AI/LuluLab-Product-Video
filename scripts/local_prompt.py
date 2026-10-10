#!/usr/bin/env python3
"""Local prompt builder/validator; v3 knowledge requires a reviewed Execution Spec."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prompt_library import load_context as load_prompt_library_context
from prompt_library import normalize_context as normalize_prompt_library_context
from prompt_library import PromptLibraryError
from local.prompt_generator import DIRECT_GUIDANCE, DIRECT_GUIDANCE_EN, render_execution_prompt
from core.prompt_syntax import NO_SPEECH, VOICE_PATTERN, voice_records, validate_prompt_language
from core.language import normalize_language
from core.user_errors import failure


class LocalPromptError(RuntimeError):
    pass


COMMON_RULES = r'''你是短视频执行导演和 AI 视频提示词专家。

# 任务

根据输入信息生成可直接用于视频模型的视频生成提示词。

# 1.任务

根据输入信息生成可直接用于视频模型的视频Prompt。

输出必须符合真实商业短视频生产要求。


# 2. 输出结构

最终只能输出以下 JSON：

{
  "videoPrompts": {
    "summary": "",
    "segments": [
      {
        "segmentId": 1,
        "title": "",
        "duration": 10,
        "prompt": ""
      }
    ]
  },
  "creatorPrompts": {
    "summary": "",
    "creators": [
      {
        "creatorId": 1,
        "role": "",
        "appearsInSegments": [1],
        "consistencyReason": "",
        "prompt": ""
      }
    ]
  }
}

禁止输出：
- 解释
- 分析
- Markdown
- 额外字段


# 3. videoPrompts规则

用于生成最终视频。


## summary

一句话描述：

- 视频模型
- 总时长
- Segment数量


## segments

每个 Segment 是独立视频生成任务。


字段：
segmentId：
Segment编号。


title：

格式：

第X段｜时长｜视频功能


duration：

Segment实际生成时长。

要求：

- 必须整数
- 必须符合当前视频模型的单段时长限制
- 具体限制以【Segment拆分规则】中的模型规则为准
- 拼接后的总时长必须尽量接近用户目标时长
- 当无法精确匹配时，优先选择总时长略高于目标时长，而不是明显低于目标时长


prompt：

完整视频生成 Prompt。Segment 是模型的生成任务容器，不是内容阶段；一个 Segment 内可以包含多个镜头、硬切、景别变化和多个营销节拍。

每个 Segment 必须包含：

1. 本次任务的参考图及其职责：产品图只锁定产品外观，达人图只锁定人物身份和穿戴。
2. 完整的人物、产品、场景、光线、机位和本段初始状态。
3. 从 0 秒开始的连续时间轴，覆盖画面、动作、运镜、环境声、音效、音乐和口播。
4. 本段 Execution Spec 指定的动作、产品可见状态和人物反应；有依据才使用效果对比，Proof 和自然 CTA 均可省略，不得凑齐结构而编造。
5. 声音规则与必要限制。

每个 Segment 必须遵守：

- 时间轴使用 `[0s-3s]` 格式，从 0 秒开始，无空档、重叠或倒序，最后结束时间等于 Segment duration。
- 每个时间块不超过 4 秒，只安排一个核心镜头或连续动作链。
- prompt字符串必须使用真实换行组织内容：参考图职责一段；人物、产品、场景、光线、机位和初始状态一段；人物固定声音或无口播声明独占一行；每个时间块各占一行；结尾限制独占一行。不得把完整Prompt写成一个连续长段落，也不得输出字面量`\\n`代替换行。
- 禁止字幕、水印，禁止擅自新增或修改产品元素，不得编造参数、功效或承诺。
- 每段使用绝对、自包含描述；禁止出现“上一段”“下一段”“承接”“继续前段”“同一个达人”“同一人物”“相同人物”“同上一人物”“声音同上段”“保持相同声音”等跨段引用。
- 后续 Segment 可以在最终成片中推进前面的剧情，但必须绝对描述自己的初始画面和人物状态，不重演前段内容来补背景。

# 4. Segment拆分规则


根据当前视频模型限制进行 Segment 拆分。


## 通用规则：

- 必须先根据目标总时长和模型单段限制确定最少 Segment 数，再在这些 Segment 内安排内容。
- Segment 不得按 Hook、Problem、Solution、Proof、CTA 或场景阶段拆分。
- 当目标总时长不超过模型单段上限时，必须只生成 1 个 Segment。
- 每个Segment必须可以独立生成。
- 连续动作、连续口播、连续产品展示尽量保持在同一个Segment。
- 不允许为了满足目标总时长生成模型不支持的Segment时长。
- 如果模型限制导致无法精确匹配目标时长，需要通过多个合法Segment组合，使最终总时长尽量接近目标时长。
- 不要为了减少Segment数量而明显缩短最终视频时长。


## 模型时长限制：
* seedance-2 / seedance-2-fast / seedance-2-mini：单段 4～15 秒。
* seedance-2-5：单段 4～30 秒。


# 5. creatorPrompts规则

用于生成达人产品参考图。用户未提供达人图时，必须结合用户上传的产品图，生成一张同一人物的多视角达人产品参考图。

达人设计必须综合使用输入中的：

- productBrief.targetCountry
- productBrief.targetAudience
- productBrief.productName
- productBrief.sellingPoints
- 产品图呈现的品类、风格与使用场景
- creativeRequirement中的达人或创意要求

生成达人产品参考图时，必须把productBrief.productImages中的有效产品图作为实际生图参考输入，不得只在文字Prompt中描述产品。

产品必须融入三个全身视角；脸部特写以锁定人物身份为首要目标，不强行塞入与脸部无关的产品。只有产品本来用于脸部、头部或能自然出现在近景中时才展示，并与全身视图保持一致：

- 穿戴类产品默认由达人正确穿戴，成套服装必须完整穿着。
- 手持或使用型产品由达人自然持有或使用。
- 不适合穿戴或手持的大型产品与达人同场展示并保持可信比例。
- 严格保留产品图中可见的颜色、版型、结构、图案、材质观感与部件。
- 不得把产品替换成普通占位服装，不得凭空补造看不见的细节。

用户明确提供的达人要求优先级最高。达人年龄感、整体气质、妆发、体型和穿搭应与目标市场的内容语境、产品定位和目标受众自然匹配。不得脱离输入生成泛化达人。

目标市场只用于本地化内容语境，不得仅凭国家或地区套用种族、肤色、五官或文化刻板印象，不得虚构职业、身份或生活方式。

creator按照人物生成，不按照 Segment 生成。

同一人物多个 Segment出现：

只生成一个 Creator。


字段：


summary：

一句话介绍达人信息。


creators：

role：

人物角色，例如：

- 主达人
- 演示达人
- 旁观者


appearsInSegments：

填写出现的 Segment。


consistencyReason：

说明保持人物一致原因。


prompt：

完整多视角达人参考图 Prompt。


必须包含：

- 9:16竖图
- 真人摄影风格
- 单张四视图参考板，只呈现同一位达人
- 四个清晰分区固定为：人物脸部特写、人物全身正面、人物全身侧面、人物全身背面
- 不得用三分之四侧面替代标准侧面，不得缺少背面
- 脸部特写完整显示五官、发际线、双耳附近和自然皮肤纹理，不裁切关键脸部特征
- 正面、侧面、背面三个全身视图均从头顶完整显示到鞋底
- 四个视图的身份、脸部特征、肤色、发型、体型、服装、鞋履和固定配饰完全一致
- 三个全身视图中的产品外观与穿戴、持有或使用方式一致
- 四个视图采用统一光线、色彩和人物比例
- 自然站姿
- 浅色干净背景
- 均匀光线
- 五官
- 肤色
- 发型
- 体型
- 完整服装
- 鞋履
- 固定配饰
- 自然皮肤纹理
- 真实UGC达人感
- 自然表情与真实人体比例
- 生活化妆发和合身日常服装


禁止：

- 忽略产品参考图或使用与产品无关的占位服装
- 修改产品颜色、版型、结构、图案、材质观感或部件
- 文字
- Logo
- 边框
- 额外人物
- 过度磨皮
- 夸张身材
- 僵硬姿势
- 塑料皮肤
- 奢华影棚模特感
- 明显AI面孔


不要生成：

- 一次性路人
- 背景人物



# 7. 产品规则

产品外观由产品参考图锁定。

每个 Segment 要独立写清本段产品可见特征和初始状态，不依赖前段叙述。


禁止：

- 修改产品结构
- 修改颜色
- 添加不存在功能
- 编造参数


# 8. 声音与口播规则

原创带货视频默认必须有清楚、可听的成片语言台词；只有用户明确选择无口播才可整条无口播。
每句台词写在对应时间块内。英文提示词使用 `Dialogue(Role): "actual media-language line"` 或 `Voiceover(Role): "actual media-language line"`；中文提示词使用 `口播（角色名）：“实际台词”` 或 `旁白（角色名）：“实际台词”`。
只写固定声音不算台词。英语每秒不超过3.5词，中文每秒不超过5字；保留呼吸和操作时间。
涂唇镜头使用旁白或无台词，不边涂边对镜口播。每个镜头写清产品、工具及人物的起止状态。
无字幕是画面文字要求，不是禁止声音；文字型 Hook 应转写成自然口播，不得直接删除含义。


口播：

必须：

- 使用指定成片语言的自然口语；未指定时按目标市场选择
- 不逐字翻译
- 符合人物身份、年龄和场景
- 保持真实UGC表达


禁止：

- 生成字幕


人物固定声音：

- 只要本段有人物口播，必须在时间轴之前独立写完整声音句。英文使用 `Fixed voice(Role): language=...; accent=...; adult gender=...; age impression=...; core timbre=...; pitch=...; base speaking rate=...; delivery style=....`；中文使用 `人物固定声音（角色名）：语言=...；口音=...；成年性别=...；年龄感=...；核心音色=...；音高=...；基础语速=...；表达风格=...。`。字段名和描述跟随提示词叙述语言，不跟随成片语言。
- 同一角色跨 Segment 说话时，每个相关 Segment 都必须逐字复用这一整句，包括字段顺序、用词和标点；不得缩写成“同上段”或“保持同一声音”。
- 固定声音只锁定语言、口音、成年性别、年龄感、核心音色、音高、基础语速和表达风格。惊讶、紧张、兴奋、放松、音量变化和关键词强调写入对应时间块，不改动固定声纹。
- 多个主要说话人物必须分别写固定声音，不得共用。
- 无人物口播的 Segment：英文写 `No character speech in this segment.`，中文写 `本段无人物口播。`。


# 9. 输出语言规则


除台词和允许的画面文字外，生成内容使用本次指定的交互语言，可为任意有效 BCP-47 语言。


包括：

- videoPrompts.summary
- segments[].title
- segments[].prompt
- creatorPrompts.summary
- creators[].prompt
- consistencyReason


口播、旁白、允许新增的画面或图片文字必须使用用户指定的成片语言；未指定时才按目标市场选择自然的当地语言，例如：

- 美国：美式英语
- 巴西：葡萄牙语
- 泰国：泰语


视频描述、镜头描述、人物描述、声音描述等 Prompt 叙述按指定交互语言输出。中文任务用中文结构标签；其他语言使用可解析的英文结构标签，其字段值与周围叙述按交互语言。JSON键和 `[0s-3s]` 时间轴保持不变。非中文提示词不保留中文格式标记。产品图上已有的包装/商标文字按原样保留，不擅自翻译。


# 10. 模型限制

所有人物必须为成年人。禁止危险动作、性化服装、恐吓式表达。'''


COMMON_RULES_EN = r'''You are a short-form video director and AI video prompt specialist.

Return only JSON with exactly videoPrompts and creatorPrompts. videoPrompts has summary and segments; each segment has segmentId, title, integer duration and prompt. creatorPrompts has summary and creators; each creator has creatorId, role, appearsInSegments, consistencyReason and prompt. Do not add explanations, Markdown or fields.

Each segment is a separate model generation task, not a narrative phase. Its prompt must state the role of the product and creator reference images; fully describe the adult person, product, setting, lighting, camera and initial state; and contain a continuous timeline from [0s-3s] style blocks starting at zero, ending at segment duration, with no gaps or overlaps. Each block is at most four seconds and contains one central shot or continuous action chain. Include visual action, camera, ambient sound, music and actual dialogue when applicable. Use real newline characters: reference image roles, scene description, fixed voice declaration or silence, each timeline block, and closing constraints on separate lines. Never output literal \n.

Use the fewest valid segments. seedance-2, seedance-2-fast and seedance-2-mini allow 4–15 seconds per segment; seedance-2-5 allows 4–30. Keep the total as close to the requested duration as valid limits permit. Every segment must be self-contained and use absolute initial states; do not refer to earlier or later segments or reuse a prior voice description by reference. Preserve all approved Execution Spec beats and factual product details. Avoid invented effects, specifications, prices, promotions, sales claims or certifications. Do not add subtitles or watermarks, alter the product, or fill time with empty shots.

Spoken dialogue in the media language is required by default; complete silence is allowed only by explicit request. Put each actual line in its timeline block. A speaking segment needs a complete fixed voice declaration before the timeline with language, accent, adult gender, age impression, core timbre, pitch, base speaking rate and delivery style. Repeat the identical declaration word for word for a role across segments. Put momentary emotion in the relevant timeline block. During lip application use voiceover or silence, not synchronized on-camera dialogue. Keep dialogue naturally speakable with breathing and action time. Newly added screen or image text uses the media language; retain existing packaging and trademarks unchanged.

When no creator image is supplied, produce one 9:16 photorealistic four-view creator/product reference board of the same adult person: complete face close-up and full-body front, true side and back views, each fully visible. Keep identity, face, skin tone, hair, build, clothing, shoes, fixed accessories, lighting, scale and product appearance consistent. Integrate the real product reference image in every applicable full-body view, worn, held or used naturally. Respect the user's creator requirements and target audience without market-based stereotypes. Use a clean light background and natural UGC styling. No text, logo, border, extra people, plastic skin, excessive retouching or invented product details. One creator entry per recurring person.

All people must be adults. Avoid dangerous actions, sexualized clothing and fear-based claims.'''


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def build_prompt(
    product_brief: Mapping[str, Any],
    user_config: Mapping[str, Any],
    creator_brief: Mapping[str, Any] | None = None,
    creative_requirement: str | None = None,
    prompt_library_context: Mapping[str, Any] | None = None,
    execution_spec: Mapping[str, Any] | None = None,
    display_language: str = "en",
    media_language: str | None = None,
) -> str:
    """Render a neutral direct brief or translate one reviewed Execution Spec."""
    if not isinstance(product_brief, Mapping):
        raise LocalPromptError("productBrief 必须是对象。")
    if not isinstance(user_config, Mapping):
        raise LocalPromptError("userConfig 必须是对象。")
    try:
        display_language = normalize_language(display_language) or 'en-US'
    except ValueError as exc:
        raise LocalPromptError(str(exc)) from exc
    chinese = display_language.split('-')[0] == 'zh'
    normalized_product_brief = dict(product_brief)
    if not _text(normalized_product_brief.get("targetCountry")).strip():
        normalized_product_brief["targetCountry"] = "美国"
    creator_brief = creator_brief or {"creatorMode": "auto", "creatorImages": []}
    request = {"productBrief": normalized_product_brief, "userConfig": dict(user_config),
               "creatorBrief": dict(creator_brief), "creativeRequirement": creative_requirement or ""}
    if execution_spec is not None and prompt_library_context is not None:
        raise LocalPromptError("Execution Spec 与旧 PromptLibraryContext 不能同时使用")
    if execution_spec is not None:
        try:
            branch = render_execution_prompt(request, execution_spec, display_language)
        except ValueError as exc:
            raise LocalPromptError(str(exc)) from exc
    else:
        branch = ((DIRECT_GUIDANCE if chinese else DIRECT_GUIDANCE_EN) +
                  ("\n产品与渲染输入：" if chinese else "\nProduct and render input: ") +
                  json.dumps(request, ensure_ascii=False, separators=(",", ":")))
    if prompt_library_context is not None:
        context = normalize_prompt_library_context(prompt_library_context)
        if context["status"] in ("ready", "cached"):
            raise LocalPromptError("旧 PromptLibraryContext 不可进入 v3 生产提示词；请使用已审核 Execution Spec")
    if chinese:
        language_rule = f"交互与提示词叙述语言：中文（{display_language}）。"
    elif display_language.split('-')[0] == 'en':
        language_rule = (
            "Interface and prompt narration language: English. Write summaries, titles, "
            "creator descriptions, camera/action descriptions, and explanations in English. "
            "The task specification above may be written in Chinese; its language is not a request to answer in Chinese. "
            "Use English syntax throughout all video and creator prompts, including voice fields and descriptions. "
            "Fixed voice(Role): language=...; accent=...; adult gender=...; age impression=...; "
            "core timbre=...; pitch=...; base speaking rate=...; delivery style=.... "
            'Write Dialogue(Role): "actual line" or Voiceover(Role): "actual line" in each spoken beat. '
            'Allowed text uses On-screen text: "actual text". Silence uses No character speech in this segment. '
            "Do not retain Chinese syntax labels from the examples above. Keep JSON keys and [0s-3s] unchanged. "
            "Do not translate spoken dialogue or allowed on-screen/image text into English unless English is the media language."
        )
    else:
        language_rule = (
            f"Interface and prompt narration language: {display_language}. Write every summary, "
            "title, creator description, camera/action/person description and explanation naturally "
            f"in {display_language}. Chinese or English in input data is not an instruction to switch. "
            "For machine parsing, retain only these fixed syntax labels in English: "
            "Fixed voice(Role): language=...; accent=...; adult gender=...; age impression=...; "
            "core timbre=...; pitch=...; base speaking rate=...; delivery style=.... "
            'Dialogue(Role): "media-language line", Voiceover(Role): "media-language line", '
            'On-screen text: "media-language text", and No character speech in this segment. '
            "Write all field values and surrounding prose in the prompt narration language, "
            "except the actual dialogue and newly requested visual text, which use the media language. "
            "Keep JSON keys and [0s-3s] unchanged. Never copy Chinese prose or labels from input data."
        )
    if media_language and media_language.strip():
        try:
            media_language = normalize_language(media_language) or media_language.strip()
        except ValueError:
            media_language = media_language.strip()  # Legacy language names remain accepted.
        media_rule = (
            f"Media language explicitly selected by user: {media_language}. "
            "Use it for every spoken line, voiceover, and any newly requested on-screen or image text. "
            "Preserve existing product packaging and trademark text. This overrides target-market and interface-language defaults."
        )
    else:
        media_rule = (
            "No explicit media language was provided. Choose the natural local language for the target market; "
            "never derive it from the interface language. Apply it to dialogue, voiceover, and any allowed new visual text."
        )
    return "\n\n".join([COMMON_RULES if chinese else COMMON_RULES_EN,
                         branch, language_rule, media_rule])


def _duration_allowed(model: str, duration: int) -> bool:
    model = model.strip().lower()
    if model in {"seedance-2", "seedance-2-fast", "seedance-2-mini"}:
        return 4 <= duration <= 15
    if model == "seedance-2-5":
        return 4 <= duration <= 30
    return False


TIMELINE_PATTERN = re.compile(r"\[(\d+(?:\.\d+)?)s-(\d+(?:\.\d+)?)s\]")
CROSS_SEGMENT_REFERENCES = (
    "上一段",
    "下一段",
    "承接上段",
    "承接前段",
    "继续前段",
    "同一个达人",
    "同一位达人",
    "同一人物",
    "相同人物",
    "同上一人物",
    "声音同上段",
    "保持相同声音",
)


def _validate_timeline(prompt: str, duration: int, segment_index: int) -> None:
    ranges = [(float(start), float(end)) for start, end in TIMELINE_PATTERN.findall(prompt)]
    if not ranges:
        raise LocalPromptError(f"第 {segment_index} 个 Segment 缺少 [0s-3s] 格式的连续时间轴。")
    if abs(ranges[0][0]) > 1e-6:
        raise LocalPromptError(f"第 {segment_index} 个 Segment 时间轴必须从 0 秒开始。")
    previous_end = 0.0
    for block_index, (start, end) in enumerate(ranges, 1):
        if abs(start - previous_end) > 1e-6:
            raise LocalPromptError(
                f"第 {segment_index} 个 Segment 的第 {block_index} 个时间块与前一块不连续。"
            )
        if end <= start:
            raise LocalPromptError(f"第 {segment_index} 个 Segment 存在无效或倒序时间块。")
        if end - start > 4.000001:
            raise LocalPromptError(f"第 {segment_index} 个 Segment 的单个时间块不得超过 4 秒。")
        previous_end = end
    if abs(previous_end - duration) > 1e-6:
        raise LocalPromptError(
            f"第 {segment_index} 个 Segment 时间轴结束于 {previous_end:g} 秒，必须等于 duration {duration} 秒。"
        )


def _validate_prompt_independence(prompt: str, segment_index: int) -> None:
    for forbidden in CROSS_SEGMENT_REFERENCES:
        if forbidden in prompt:
            raise LocalPromptError(
                f"第 {segment_index} 个 Segment 含跨段引用“{forbidden}”，必须改为本段的绝对描述。"
            )


def _voice_fingerprints(prompt: str, segment_index: int) -> dict[str, str]:
    records = voice_records(prompt)
    if NO_SPEECH.search(prompt):
        if records:
            raise LocalPromptError(f"Segment {segment_index}: silence conflicts with a fixed voice declaration")
        return {}
    if not records:
        raise LocalPromptError(f"Segment {segment_index}: missing fixed voice or explicit no-speech declaration")
    voices: dict[str, str] = {}
    for role, fingerprint, missing in records:
        if missing:
            raise LocalPromptError(f"Segment {segment_index}, {role}: missing/empty voice fields: {', '.join(missing)}")
        if role in voices and voices[role] != fingerprint:
            raise LocalPromptError(f"Segment {segment_index}: conflicting fixed voices for {role}")
        voices[role] = fingerprint
    return voices


def validate_result(
    result: Mapping[str, Any],
    *,
    video_model: str | None = None,
    target_duration: int | None = None,
    requirements: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the former workflow's public JSON contract and return normalized data."""
    if not isinstance(result, Mapping):
        raise LocalPromptError("本地提示词结果必须是 JSON 对象。")
    if set(result) != {"videoPrompts", "creatorPrompts"}:
        raise LocalPromptError("本地提示词结果顶层只能包含 videoPrompts 和 creatorPrompts。")

    video_prompts = result.get("videoPrompts")
    creator_prompts = result.get("creatorPrompts")
    if not isinstance(video_prompts, Mapping):
        raise LocalPromptError("videoPrompts 必须是对象。")
    if not isinstance(creator_prompts, Mapping):
        raise LocalPromptError("creatorPrompts 必须是对象。")

    segments = video_prompts.get("segments")
    creators = creator_prompts.get("creators")
    if not isinstance(segments, list) or not segments:
        raise LocalPromptError("videoPrompts.segments 必须是非空数组。")
    if not isinstance(creators, list):
        raise LocalPromptError("creatorPrompts.creators 必须是数组。")

    voice_fingerprints: dict[str, str] = {}
    total_duration = 0
    for index, segment in enumerate(segments, 1):
        if not isinstance(segment, Mapping):
            raise LocalPromptError(f"第 {index} 个 Segment 必须是对象。")
        for key in ("segmentId", "title", "duration", "prompt"):
            if key not in segment:
                raise LocalPromptError(f"第 {index} 个 Segment 缺少 {key}。")
        duration = segment.get("duration")
        if isinstance(duration, bool) or not isinstance(duration, int):
            raise LocalPromptError(f"第 {index} 个 Segment duration 必须是整数。")
        if video_model and not _duration_allowed(video_model, duration):
            raise LocalPromptError(
                f"第 {index} 个 Segment 时长 {duration} 不符合模型 {video_model} 的限制。"
            )
        total_duration += duration
        if not isinstance(segment.get("prompt"), str) or not segment["prompt"].strip():
            raise LocalPromptError(f"第 {index} 个 Segment prompt 不能为空。")
        prompt = segment["prompt"].strip()
        try:
            validate_prompt_language(prompt, (requirements or {}).get("promptLanguage"))
        except ValueError as exc:
            raise LocalPromptError(str(exc)) from exc
        _validate_timeline(prompt, duration, index)
        _validate_prompt_independence(prompt, index)
        segment_voices = _voice_fingerprints(prompt, index)
        for role, fingerprint in segment_voices.items():
            if role in voice_fingerprints and voice_fingerprints[role] != fingerprint:
                raise LocalPromptError(
                    f"角色“{role}”跨 Segment 的人物固定声音必须逐字一致。"
                )
            voice_fingerprints[role] = fingerprint

    if target_duration is not None and total_duration != target_duration:
        raise LocalPromptError(
            f"Segment 总时长 {total_duration} 秒与目标时长 {target_duration} 秒不一致。"
        )
    if target_duration is not None and video_model:
        max_duration = 30 if video_model.strip().lower() == "seedance-2-5" else 15
        minimum_segments = math.ceil(target_duration / max_duration)
        if len(segments) != minimum_segments:
            raise LocalPromptError(
                f"模型 {video_model} 生成 {target_duration} 秒视频应使用最少 "
                f"{minimum_segments} 个 Segment，实际为 {len(segments)} 个。"
            )

    for index, creator in enumerate(creators, 1):
        if not isinstance(creator, Mapping):
            raise LocalPromptError(f"第 {index} 个 Creator 必须是对象。")
        for key in ("creatorId", "role", "appearsInSegments", "consistencyReason", "prompt"):
            if key not in creator:
                raise LocalPromptError(f"第 {index} 个 Creator 缺少 {key}。")

    from quality_gate import validate_speech
    try:
        validate_speech(segments, requirements)
    except ValueError as exc:
        raise LocalPromptError(str(exc)) from exc

    return {
        "videoPrompts": dict(video_prompts),
        "creatorPrompts": dict(creator_prompts),
        "segments": list(segments),
        "summary": video_prompts.get("summary", ""),
        "success": True,
        "errorMessage": "",
    }


def _load_request(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LocalPromptError("输入 JSON 必须是对象。")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--input", required=True, type=Path)
    build.add_argument("--prompt-library-context", type=Path)
    build.add_argument("--execution-spec", type=Path)
    build.add_argument("--display-language", default="en-US")
    build.add_argument("--media-language", default="")

    validate = sub.add_parser("validate")
    validate.add_argument("--input", required=True, type=Path)
    validate.add_argument("--model", default="")
    validate.add_argument("--display-language", help="BCP-47 prompt narration language; omit for legacy prompts")
    validate.add_argument("--target-duration", type=int)
    validate.add_argument("--requirements", type=Path, help="内部声音配置；默认必须有台词")

    args = parser.parse_args()
    try:
        if args.command == "build":
            request = _load_request(args.input)
            library_context = (
                load_prompt_library_context(args.prompt_library_context)
                if args.prompt_library_context
                else None
            )
            print(
                build_prompt(
                    request.get("productBrief", {}),
                    request.get("userConfig", {}),
                    request.get("creatorBrief", {}),
                    request.get("creativeRequirement", ""),
                    prompt_library_context=library_context,
                    execution_spec=_load_request(args.execution_spec) if args.execution_spec else None,
                    display_language=args.display_language,
                    media_language=args.media_language or None,
                )
            )
            return
        result = _load_request(args.input)
        requirements = _load_request(args.requirements) if args.requirements else {}
        if args.display_language:
            requirements["promptLanguage"] = normalize_language(args.display_language)
        normalized = validate_result(
            result,
            video_model=args.model or None,
            target_duration=args.target_duration,
            requirements=requirements,
        )
        print(json.dumps(normalized, ensure_ascii=False))
    except (OSError, json.JSONDecodeError, ValueError, LocalPromptError, PromptLibraryError) as exc:
        failure(exc, "PROMPT_INVALID")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
