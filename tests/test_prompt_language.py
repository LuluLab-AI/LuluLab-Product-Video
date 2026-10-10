from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from local_prompt import LocalPromptError, build_prompt
from core.language import normalize_language, resolve_language_context
from review_render import normalized


class PromptLanguageTests(unittest.TestCase):
    def setUp(self):
        self.product = {"productName": "Travel cup", "productImages": [], "targetCountry": "美国"}
        self.config = {"videoModel": "seedance-2-fast", "duration": 15}

    def test_english_interface_and_spanish_media_are_independent(self):
        prompt = build_prompt(self.product, self.config, display_language="en", media_language="es-US")
        self.assertIn("Interface and prompt narration language: English", prompt)
        self.assertIn("Media language explicitly selected by user: es-US", prompt)
        self.assertIn("Do not translate spoken dialogue", prompt)
        self.assertNotIn("所有生成内容必须使用中文", prompt)

    def test_chinese_interface_can_request_english_media(self):
        prompt = build_prompt(self.product, self.config, display_language="zh", media_language="en-US")
        self.assertIn("交互与提示词叙述语言：中文", prompt)
        self.assertIn("Media language explicitly selected by user: en-US", prompt)

    def test_missing_media_language_uses_market_not_interface(self):
        prompt = build_prompt(self.product, self.config, display_language="en")
        self.assertIn("never derive it from the interface language", prompt)

    def test_invalid_interface_language_rejected(self):
        with self.assertRaises(LocalPromptError):
            build_prompt(self.product, self.config, display_language="not a language")

    def test_multiple_languages_generate_complete_constraints(self):
        for language in ('pt-BR', 'es-ES', 'fr-FR', 'de-DE', 'ja-JP', 'ko-KR', 'th-TH', 'ar-SA'):
            with self.subTest(language=language):
                prompt = build_prompt(self.product, self.config, display_language=language,
                                      media_language='en-US')
                self.assertIn(f'Interface and prompt narration language: {language}', prompt)
                self.assertIn('creatorPrompts', prompt)
                self.assertIn('Fixed voice(Role): language=', prompt)
                self.assertIn('Media language explicitly selected by user: en-US', prompt)
                self.assertNotIn('你是短视频执行导演', prompt)

    def test_language_precedence_and_normalization(self):
        self.assertEqual(normalize_language('PT_br'), 'pt-BR')
        cases = [
            ({'task_message_language': 'zh-CN', 'agent_default_language': 'en-US'}, 'zh-CN', 'user_message'),
            ({'task_message_language': 'en-US', 'agent_default_language': 'zh-CN'}, 'en-US', 'user_message'),
            ({'task_message_language': 'pt-BR'}, 'pt-BR', 'user_message'),
            ({'task_message_language': 'es-ES'}, 'es-ES', 'user_message'),
            ({'task_message_language': 'fr-FR'}, 'fr-FR', 'user_message'),
            ({'agent_default_language': 'en-US'}, 'en-US', 'agent_default'),
            ({'agent_default_language': 'zh-CN'}, 'zh-CN', 'agent_default'),
            ({'explicit_language': 'en-US', 'task_message_language': 'zh-CN'}, 'en-US', 'user_explicit'),
            ({'session_language': 'es-ES'}, 'es-ES', 'session'),
            ({'session_language': 'pt-BR', 'agent_default_language': 'zh-CN'}, 'pt-BR', 'session'),
            ({'session_language': 'es-ES', 'agent_default_language': 'en-US'}, 'es-ES', 'session'),
            ({}, 'en-US', 'fallback'),
        ]
        for inputs, language, source in cases:
            with self.subTest(inputs=inputs):
                context = resolve_language_context(**inputs)
                self.assertEqual(context.as_dict(), {'interactionLanguage': language,
                                  'languageSource': source, 'promptLanguage': language})

    def test_missing_display_language_defaults_to_english_without_changing_media(self):
        prompt = build_prompt(self.product, self.config)
        self.assertIn("Interface and prompt narration language: English", prompt)
        self.assertIn("No explicit media language was provided", prompt)
        self.assertIn("never derive it from the interface language", prompt)

    def test_render_review_keeps_accented_speech_tokens(self):
        self.assertEqual(normalized("Olá, corazón!"), ["olá", "corazón"])


if __name__ == "__main__":
    unittest.main()
