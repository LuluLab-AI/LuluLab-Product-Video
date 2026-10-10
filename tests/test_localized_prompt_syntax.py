"""Offline regression coverage for localized prompts at the submission gate."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from local_prompt import LocalPromptError, build_prompt, validate_result
from quality_gate import digest, validate_job, validate_mechanism

VOICE = ('Fixed voice(Creator): language=en-US; accent=General American; '
         'adult gender=female; age impression=late twenties; core timbre=warm; '
         'pitch=medium; base speaking rate=relaxed; delivery style=casual.')


def job(text='Look at the built-in brush.', delivery='Voiceover', language='en-US'):
    segments = [{'segmentId': 1, 'title': 'Brush close-up', 'duration': 4,
                 'prompt': VOICE + '\n[0s-4s] Hold the bottle. ' +
                           f'{delivery}(Creator): "{text}"'}]
    return {'videoModel': 'seedance-2-fast', 'strategyRequested': 'DIRECT',
            'strategyUsed': 'DIRECT', 'segments': segments,
            'qualityRequirements': {'promptLanguage': 'en', 'targetLanguage': language},
            'qualityReview': {
                'promptDigest': digest(segments), 'reviewer': 'offline-test',
                'reviewedAt': '2026-10-09', 'semanticPassed': True,
                'states': [{'beatRef': '1:1', 'initial': {'bottle': 'hand'},
                            'end': {'bottle': 'hand'}, 'visibleAction': 'Hold the bottle.'}],
                'hook': {'beatRef': '1:1', 'quote': text, 'rationale': 'Specific feature'},
                'buyReason': {'beatRef': '1:1', 'quote': text, 'rationale': 'Visible brush'},
                'ending': {'beatRef': '1:1', 'quote': 'Hold the bottle.',
                           'rationale': 'Product display', 'origin': 'no-cta'}}}


class LocalizedPromptTests(unittest.TestCase):
    def test_complete_english_job_reaches_gate_with_no_chinese(self):
        for delivery in ('Voiceover', 'Dialogue'):
            j = job(delivery=delivery)
            self.assertNotRegex(j['segments'][0]['prompt'], r'[\u4e00-\u9fff]')
            validate_job(j)

    def test_spanish_dialogue_in_english_prompt(self):
        j = job('Mira el cepillo integrado.', language='es-US')
        j['segments'][0]['prompt'] = j['segments'][0]['prompt'].replace('language=en-US', 'language=es-US')
        j['qualityReview']['promptDigest'] = digest(j['segments'])
        validate_job(j)

    def test_chinese_media_independent_from_english_syntax(self):
        j = job('看看这个刷头。', language='zh-CN')
        j['segments'][0]['prompt'] = j['segments'][0]['prompt'].replace('language=en-US', 'language=zh-CN')
        j['qualityReview']['promptDigest'] = digest(j['segments'])
        validate_job(j)

    def test_old_chinese_syntax_allowed_only_without_explicit_english_requirement(self):
        j = job()
        j['segments'][0]['prompt'] = j['segments'][0]['prompt'].replace('Voiceover(Creator):', '旁白（Creator）：')
        j['qualityReview']['promptDigest'] = digest(j['segments'])
        with self.assertRaises(ValueError):
            validate_job(j)
        del j['qualityRequirements']['promptLanguage']
        validate_job(j)

    def test_english_silence_requires_explicit_request(self):
        j = job()
        j['segments'][0]['prompt'] = 'No character speech in this segment.\n[0s-4s] Hold the bottle.'
        j['qualityReview']['promptDigest'] = digest(j['segments'])
        for key in ('hook', 'buyReason'):
            j['qualityReview'][key]['quote'] = 'Hold the bottle.'
        with self.assertRaises(ValueError):
            validate_job(j)
        j['qualityRequirements'].update(speechMode='none', explicitNoSpeechRequest=True)
        validate_job(j)
        j['segments'][0]['prompt'] += '\nVoiceover(Creator): "Look here."'
        with self.assertRaises(ValueError):
            validate_job(j)

    def test_incomplete_voice_and_speech_without_voice_rejected(self):
        for mutation in ('empty', 'missing', 'removed', 'no dialogue'):
            j = job()
            if mutation == 'empty':
                j['segments'][0]['prompt'] = j['segments'][0]['prompt'].replace('accent=General American', 'accent=')
            elif mutation == 'missing':
                j['segments'][0]['prompt'] = j['segments'][0]['prompt'].replace('accent=General American; ', '')
            elif mutation == 'removed':
                j['segments'][0]['prompt'] = j['segments'][0]['prompt'].replace(VOICE, '')
            else:
                j['segments'][0]['prompt'] = VOICE + '\n[0s-4s] Hold the bottle.'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_job(j)

    def test_voice_identity_must_match_across_segments(self):
        j = job()
        result = {'videoPrompts': {'segments': j['segments']}, 'creatorPrompts': {'creators': []}}
        second = copy.deepcopy(j['segments'][0]); second['segmentId'] = 2
        result['videoPrompts']['segments'].append(second)
        validate_result(result, video_model='seedance-2-fast', requirements=j['qualityRequirements'])
        second['prompt'] = second['prompt'].replace('pitch=medium', 'pitch=low')
        with self.assertRaises(LocalPromptError):
            validate_result(result, video_model='seedance-2-fast', requirements=j['qualityRequirements'])

    def test_english_screen_text_hook_recognized_and_conflicts_rejected(self):
        s = job()['segments']
        s[0]['prompt'] += '\nOn-screen text: "Built-in brush"'
        bp = {'hook': {'expressionChannels': ['text']},
              'hookRealization': {'message': 'Built-in brush', 'channels': ['text'], 'beatRef': '1:1'},
              'structure': {'requiredStages': ['show']},
              'structureRealization': [{'stage': 'show', 'beatRef': '1:1',
                                       'quote': 'Hold the bottle.', 'rationale': 'Show product'}]}
        validate_mechanism(s, bp, {})
        s[0]['prompt'] += '\nNo on-screen text.'
        with self.assertRaises(ValueError):
            validate_mechanism(s, bp, {})

    def test_language_builder_requests_english_syntax_independent_of_media(self):
        prompt = build_prompt({'productName': 'Cleaner', 'productImages': []},
                              {'videoModel': 'seedance-2-fast', 'duration': 15},
                              display_language='en', media_language='es-US')
        self.assertIn('Fixed voice(Role): language=', prompt)
        self.assertIn('Do not retain Chinese syntax labels', prompt)
        self.assertIn('Media language explicitly selected by user: es-US', prompt)
        self.assertNotIn('required machine-readable labels; keep them verbatim', prompt)

    def test_portuguese_and_spanish_prompt_generation_reach_quality_gate(self):
        for prompt_language, media_language, line in (
            ('pt-BR', 'pt-BR', 'Veja a escova integrada.'),
            ('es-ES', 'es-ES', 'Mira el cepillo integrado.'),
        ):
            with self.subTest(prompt_language=prompt_language):
                instruction = build_prompt({'productName': 'Cleaner', 'productImages': []},
                    {'videoModel': 'seedance-2-fast', 'duration': 4},
                    display_language=prompt_language, media_language=media_language)
                self.assertIn(f'Interface and prompt narration language: {prompt_language}', instruction)
                self.assertIn(f'Media language explicitly selected by user: {media_language}', instruction)
                j = job(line, language=media_language)
                j['qualityRequirements']['promptLanguage'] = prompt_language
                j['segments'][0]['prompt'] = j['segments'][0]['prompt'].replace('language=en-US',
                                                                               f'language={media_language}')
                j['qualityReview']['promptDigest'] = digest(j['segments'])
                j['qualityReview']['hook']['quote'] = line
                j['qualityReview']['buyReason']['quote'] = line
                validate_job(j)


if __name__ == '__main__':
    unittest.main()
