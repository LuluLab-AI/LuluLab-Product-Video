from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_TEXT = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
CLI_TEXT = (SKILL_ROOT / "scripts" / "lzstudio_cli.py").read_text(encoding="utf-8")
VIDEO_CLI_TEXT = (SKILL_ROOT / "scripts" / "video_cli.py").read_text(encoding="utf-8")
LIBTV_TEXT = (SKILL_ROOT / "scripts" / "libtv_batch_generate.py").read_text(encoding="utf-8")
OPENAI_YAML = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
PROMPT_LIBRARY_TEXT = (SKILL_ROOT / "scripts" / "prompt_library.py").read_text(encoding="utf-8")
LOCAL_PROMPT_TEXT = (SKILL_ROOT / "scripts" / "local_prompt.py").read_text(encoding="utf-8")
PROMPT_LIBRARY_INTERFACE = (SKILL_ROOT / "references" / "prompt-library-interface.md").read_text(encoding="utf-8")


class SkillContractTests(unittest.TestCase):
    def test_lululab_runtime_uses_private_local_credentials(self):
        self.assertIn("LINGZHI_API_KEY", SKILL_TEXT + VIDEO_CLI_TEXT)
        self.assertIn("LZSTUDIO_API_KEY", SKILL_TEXT + VIDEO_CLI_TEXT)
        self.assertNotIn("--api-key", VIDEO_CLI_TEXT)
        self.assertIn("不得把 API Key 写入任务 JSON、日志或回复", SKILL_TEXT)
        self.assertNotIn("请提供LuluLab API Key", SKILL_TEXT)

    def test_official_oauth_flow_is_declared(self):
        for text in ("dreamina login", "OAuth", "dreamina user_credit", "multimodal2video"):
            with self.subTest(text=text):
                self.assertIn(text, SKILL_TEXT)

    def test_lululab_creator_image_is_primary_multiview_and_product_grounded(self):
        self.assertIn("scripts/local_creator_image_generate.py", SKILL_TEXT)
        self.assertIn("`gpt-image-2-5-sunburst`", SKILL_TEXT)
        self.assertIn("`ImageGenV2`", SKILL_TEXT)
        self.assertIn("单张四视图参考板", SKILL_TEXT)
        for view in ("人物脸部特写", "人物全身正面", "人物全身侧面", "人物全身背面"):
            with self.subTest(view=view):
                self.assertIn(view, SKILL_TEXT)
                self.assertIn(view, LOCAL_PROMPT_TEXT)
        self.assertIn("不得用三分之四侧面替代标准侧面", SKILL_TEXT)
        self.assertIn("不得缺少背面", SKILL_TEXT)
        self.assertIn("该前置步骤不可跳过", SKILL_TEXT)
        self.assertIn("--reference-image <产品图1>", SKILL_TEXT)
        self.assertIn("不调用内置生图工具、Dreamina 或远程 PromptGen", SKILL_TEXT)

    def test_auto_creator_visibly_uses_product_reference(self):
        for text in (
            "必须把 `productBrief.productImages` 中所有有效产品图作为实际生图参考输入",
            "穿戴类产品默认由达人正确穿戴",
            "成套服装必须完整穿着",
            "产品必须融入三个全身视图",
            "脸部特写以锁定人物身份为首要目标",
            "不得把产品替换成普通占位服装",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SKILL_TEXT)

    def test_default_market_does_not_depend_on_conversation_language(self):
        self.assertIn("目标市场默认美国", SKILL_TEXT)
        self.assertIn("不得由对话语言推断", SKILL_TEXT)

    def test_generated_creator_images_are_displayed(self):
        self.assertIn("必须在进入 Seedance 视频生成前立即向用户显示", SKILL_TEXT)
        self.assertIn("不得只发送文件路径", SKILL_TEXT)

    def test_auto_creator_is_shared_by_default_and_used_as_reference(self):
        self.assertIn("批量任务中默认只生成一张并跨视频复用", SKILL_TEXT)
        self.assertIn("只有用户明确要求每条视频使用不同达人时", SKILL_TEXT)
        self.assertIn("默认向每条视频传入同一张共享图", SKILL_TEXT)

    def test_auto_creator_uses_user_context_and_stays_natural(self):
        for text in (
            "目标市场、目标受众、产品名称、可见卖点、产品风格和自定义创作要求",
            "用户明确提供的达人要求优先级最高",
            "不得仅凭国家或地区套用种族、肤色、五官或文化刻板印象",
            "真实自然的普通 UGC 创作者质感",
            "避免过度磨皮、夸张身材、僵硬姿势、塑料皮肤",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SKILL_TEXT)

    def test_confirmation_uses_auto_strategy_without_style_choice(self):
        self.assertIn("创意策略：AUTO（默认）", SKILL_TEXT)
        self.assertIn("KNOWLEDGE 或 DIRECT", SKILL_TEXT)
        self.assertIn("本地用户不再选择", SKILL_TEXT)
        self.assertIn("creativeRequirement", SKILL_TEXT)

    def test_confirmation_includes_supported_models_and_count(self):
        for text in (
            "1. Seedance 2 Fast（默认）",
            "2. Seedance 2 Mini",
            "3. Seedance 2",
            "4. Seedance 2.5",
            "数量：1–10条（默认1条）",
            "[1] 按当前配置继续",
            "[2] 修改配置",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SKILL_TEXT)

    def test_user_language_controls_confirmation_independently_of_media(self):
        for text in (
            "primary language of the user's current task message",
            "agent's default response language",
            "Do not infer the agent default from operating-system locale",
            "interactionLanguage",
            "Identified product (editable)",
            "Video language:",
            "[1] Continue with these settings",
            "[2] Change settings",
            "Changing only the interaction language does not change video language",
            "--display-language <interactionLanguage>",
            "--media-language <mediaLanguage>",
            "### Video 1",
            "![Multi-view creator reference]",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SKILL_TEXT)
        self.assertIn('default="en-US"', LOCAL_PROMPT_TEXT)

    def test_removed_models_are_not_offered(self):
        menu = re.search(r"模型：\n(?:.*\n){4}", SKILL_TEXT)
        self.assertIsNotNone(menu)
        for removed in ("Minimax", "Google Omni", "Grok Imagine"):
            self.assertNotIn(removed, menu.group(0))

    def test_video_count_is_not_added_to_user_config(self):
        self.assertIn("`userConfig` 只需 `videoModel` 和 `duration`", SKILL_TEXT)
        self.assertIn("生成数量只在本地循环，不得加入 `userConfig`", SKILL_TEXT)

    def test_batch_and_output_rules_are_preserved(self):
        for text in (
            "1–10条（默认1条）",
            "最多同时运行 3 条",
            "video_01/",
            "final_video.mp4",
            "不得跨视频拼接",
            "不自动换模型",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SKILL_TEXT)

    def test_all_models_use_bounded_concurrency(self):
        for text in (
            "所有受支持模型的批量任务均允许并发生成",
            "`seedance-2-mini`、`seedance-2-fast`、`seedance-2` 和 `seedance-2-5`",
            "最多同时运行 3 条完整视频工作流",
            "不在单条视频内部并发 Segment",
            "非终态任务都计入并发数",
            "`ExceedConcurrencyLimit`",
            "所有模型最多同时运行 3 条完整视频工作流",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SKILL_TEXT)

    def test_logical_models_use_exact_vip_provider_ids(self):
        mappings = (
            "Seedance 2 Fast → `seedance-2-fast` → `seedance2.0fast_vip`",
            "Seedance 2 Mini → `seedance-2-mini` → `seedance2.0mini_vip`",
            "Seedance 2 → `seedance-2` → `seedance2.0_vip`",
        )
        for text in mappings:
            with self.subTest(text=text):
                self.assertIn(text, SKILL_TEXT)
        self.assertIn("不得静默改用", SKILL_TEXT)
        self.assertIn("必须在提交前通过该命令的 `--help` 明确声明对应 provider ID", SKILL_TEXT)

    def test_video_provider_priority_and_lock_are_declared(self):
        for text in (
            "默认只检测并使用 `lululab_cli`",
            "只有用户明确指定 LibTV、小云雀或即梦时",
            "整条视频锁定该 provider",
            "不得自动切到下一渠道重新提交",
            "scripts/libtv_batch_generate.py",
            "scripts/local_video_generate.py",
        ):
            self.assertIn(text, SKILL_TEXT)
        self.assertIn('PROVIDER_ORDER = ("lululab_cli",)', VIDEO_CLI_TEXT)
        self.assertIn("run_started_uncertain", LIBTV_TEXT)

    def test_local_prompt_contract_is_preserved(self):
        for text in ("scripts/local_prompt.py", "videoPrompts", "creatorPrompts", "validate_result()"):
            self.assertIn(text, SKILL_TEXT)

    def test_prompt_quality_rules_cover_story_density_voice_and_independence(self):
        for text in (
            "不套固定“痛点→产品→满意”",
            "禁止用走路、空镜、重复惊讶",
            "单个时间块不超过 4 秒",
            "人物固定声音（角色名）",
            "这一整句必须逐字相同",
            "禁止“上一段”",
            "校验失败不得进入计费生成",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SKILL_TEXT)

    def test_video_prompts_are_displayed_with_readable_line_breaks(self):
        for text in (
            "视频提示词展示规范",
            "不得直接倾倒原始 JSON",
            "视频 → Segment",
            "独立的 `text` 代码块",
            "使用真实换行",
            "每个 `[0s-3s]` 时间块各占一行",
            "不截断、不省略为摘要",
            "只允许调整空白和换行",
        ):
            with self.subTest(text=text):
                self.assertIn(text, SKILL_TEXT)
        self.assertIn("prompt字符串必须使用真实换行组织内容", LOCAL_PROMPT_TEXT)
        self.assertIn("每个时间块各占一行", LOCAL_PROMPT_TEXT)
        self.assertIn("不得把完整Prompt写成一个连续长段落", LOCAL_PROMPT_TEXT)

    def test_local_viral_library_uses_v3_contract(self):
        for text in (
            "四个顶层输入名称保留",
            "Hybrid Retrieval",
            "Execution Spec",
            "strategyUsed=DIRECT",
            "不静默回退",
        ):
            self.assertIn(text, SKILL_TEXT)

    def test_prompt_library_context_has_stable_bounded_contract(self):
        for text in ("schemaVersion", "disabled", "ready", "cached", "unavailable", "MAX_MATCHES = 1"):
            self.assertIn(text, PROMPT_LIBRARY_TEXT + PROMPT_LIBRARY_INTERFACE)

    def test_prompt_library_reserves_no_network_or_credentials(self):
        combined = PROMPT_LIBRARY_TEXT + PROMPT_LIBRARY_INTERFACE
        for forbidden in ("urlopen(", "requests.", "FEISHU_APP_ID", "FEISHU_APP_SECRET"):
            self.assertNotIn(forbidden, combined)

    def test_ui_metadata_mentions_batch_generation(self):
        self.assertIn("multiple", OPENAI_YAML.lower())


if __name__ == "__main__":
    unittest.main()
