import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from quality_gate import validate_speech, validate_review, validate_mechanism, digest, check_diversity, validate_job
from retrieval_terms import concepts, CATEGORIES, country, category_fit, lexical
from blueprint_contract import resolve_blueprint
from test_viral_knowledge import candidate_fixture
import local_video_generate
import review_render

VOICE='人物固定声音（主角）：语言=美式英语；口音=美国本地口音；成年性别=女性；年龄感=约28岁；核心音色=清晰柔和的中音；音高=适中；基础语速=中等；表达风格=亲切。'

def segments(text='Look at this pink.', duration=4):
    return [{'segmentId':1,'title':'test','duration':duration,
             'prompt':VOICE+f'[0s-{duration}s] 举瓶。口播（主角）：“{text}”'}]

def review(s):
    return {'promptDigest':digest(s),'reviewer':'unit-fixture','reviewedAt':'2026-09-24','semanticPassed':True,
            'states':[{'beatRef':'1:1','initial':{'bottle':'hand'},'end':{'bottle':'hand'},'visibleAction':'举瓶'}],
            'hook':{'beatRef':'1:1','quote':'举瓶','rationale':'fixture'},
            'buyReason':{'beatRef':'1:1','quote':'pink','rationale':'fixture'},
            'ending':{'beatRef':'1:1','quote':'举瓶','rationale':'fixture','origin':'original'}}

class QualityTests(unittest.TestCase):
    def test_default_silence_rejected(self):
        with self.assertRaises(ValueError): validate_speech([{'segmentId':1,'prompt':'本段无人物口播。[0s-4s] 举瓶'}])

    def test_explicit_silence_allowed(self):
        s=[{'segmentId':1,'prompt':'本段无人物口播。[0s-4s] 举瓶'}]
        self.assertEqual(validate_speech(s,{'speechMode':'none','explicitNoSpeechRequest':True}),[])
        with self.assertRaises(ValueError):validate_speech(s,{'speechMode':'none'})

    def test_complete_job_accepts_spoken_and_explicit_silent(self):
        s=segments()
        job={'videoModel':'seedance-2-fast','promptMode':'aiDirect','segments':s,
             'qualityRequirements':{'targetLanguage':'en-US'},'qualityReview':review(s)}
        validate_job(job)
        silent=[{'segmentId':1,'title':'silent fixture','duration':4,
                 'prompt':'本段无人物口播。[0s-4s] 举瓶展示粉色。'}]
        r=review(silent);r['buyReason']['quote']='粉色'
        job.update(segments=silent,qualityReview=r,
                   qualityRequirements={'speechMode':'none','explicitNoSpeechRequest':True})
        validate_job(job)

    def test_voice_description_is_not_dialogue(self):
        with self.assertRaises(ValueError):validate_speech([{'segmentId':1,'prompt':VOICE+'[0s-4s] 举瓶'}])

    def test_empty_and_excessive_dialogue(self):
        for text in ('',' '.join(['pink']*20)):
            with self.subTest(text=text),self.assertRaises(ValueError):validate_speech(segments(text))

    def test_target_language(self):
        with self.assertRaises(ValueError):validate_speech(segments('粉色很好看'),{'targetLanguage':'en-US'})
        self.assertEqual(len(validate_speech(segments(),{'targetLanguage':'en-US'})),1)

    def test_application_uses_voiceover(self):
        s=segments();s[0]['prompt']=s[0]['prompt'].replace('举瓶','沿下唇涂抹')
        with self.assertRaises(ValueError):validate_speech(s)
        s[0]['prompt']=s[0]['prompt'].replace('口播（','旁白（')
        validate_speech(s)

    def test_known_start_state_contradiction(self):
        s=segments();s[0]['prompt']='涂抹头在唇部外侧。'+s[0]['prompt'].replace('举瓶','从瓶口抽出涂抹头')
        with self.assertRaises(ValueError):validate_speech(s)

    def test_review_binds_actual_prompt(self):
        s=segments();r=review(s);validate_review(s,r)
        s[0]['prompt']+=' changed'
        with self.assertRaises(ValueError):validate_review(s,r)

    def test_state_discontinuity(self):
        s=segments();s[0]['prompt']+='[4s-8s] 放瓶。';r=review(s)
        r['states'].append({'beatRef':'1:2','initial':{'bottle':'table'},'end':{'bottle':'table'},'visibleAction':'放瓶'})
        with self.assertRaises(ValueError):validate_review(s,r)

    def test_hook_retention_and_text_conversion(self):
        s=segments();bp={'hook':{'expressionChannels':['text']},
            'hookRealization':{'message':'Look at this pink.','channels':['speech'],'beatRef':'1:1','adaptationReason':'no subtitles'},
            'structure':{'requiredStages':['show']},'structureRealization':[{'stage':'show','beatRef':'1:1','quote':'举瓶','rationale':'show'}]}
        validate_mechanism(s,bp,{})
        for mutation in ('message','action','stage','speech','text'):
            b=copy.deepcopy(bp);ss=copy.deepcopy(s)
            if mutation=='message':b['hookRealization']['message']='not in prompt'
            if mutation=='action':b['hookRealization']['channels']=['action']
            if mutation=='stage':b['structureRealization']=[]
            if mutation=='speech':ss[0]['prompt']=VOICE+'[0s-4s] Look at this pink. 举瓶。'
            if mutation=='text':
                b['hookRealization']['channels']=['text'];ss[0]['prompt']+=' 禁止字幕。'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):validate_mechanism(ss,b,{})

    def test_limited_and_pending_cannot_bypass(self):
        bp={'blueprintId':'CB','primaryBundleKey':'VB-1','structure':{'assetKey':'S'},'hook':{'assetKey':'H'},
            'actions':[{'assetKey':'A'}],'proofOmissionReason':'no proof'}
        pack=candidate_fixture(bp)
        a=pack['bundles'][0]['assets'][1];a.update(generationReadiness='limited',readinessReasons=['text must survive'])
        with self.assertRaises(ValueError):resolve_blueprint(bp,pack)
        bp['hook']['limitationChecks']=[{'limitation':'text must survive','handling':'spoken hook'}]
        resolve_blueprint(bp,pack)
        a['generationReadiness']='needs_review'
        with self.assertRaises(ValueError):resolve_blueprint(bp,pack)

    def test_actual_content_not_asset_id_diversity(self):
        self.assertTrue(check_diversity([{'segments':segments(),'assetKey':'A'},{'segments':segments(),'assetKey':'B'}]))

    def test_zero_match_requires_explicit_review(self):
        bp={'blueprintId':'CB','primaryBundleKey':'VB-1','structure':{'assetKey':'S'},'hook':{'assetKey':'H'},
            'actions':[{'assetKey':'A'}],'proofOmissionReason':'no proof'}
        pack=candidate_fixture(bp);pack['retrievalDiagnostics']={'allZeroMatch':True}
        with self.assertRaises(ValueError):resolve_blueprint(bp,pack)
        bp['zeroMatchReview']={'decision':'cross-category-transfer','reason':'reuse only task structure','productGrounding':'fixture fact P1'}
        resolve_blueprint(bp,pack)

    def test_aliases_and_chinese_phrases(self):
        self.assertEqual(concepts('lip gloss',CATEGORIES),concepts('唇彩',CATEGORIES))
        self.assertEqual(country('美国'),country('US'))
        self.assertGreater(category_fit('lip gloss','唇染颜色展示'),0)
        self.assertGreater(lexical('珠光光泽','展示粉色珠光光泽'),0)

    def test_submit_entry_blocks_before_provider(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'job.json';p.write_text(json.dumps({'videoModel':'seedance-2-fast','segments':[
                {'segmentId':1,'title':'test','duration':4,'prompt':'本段无人物口播。[0s-4s] 举瓶。'}]}))
            with patch.object(sys,'argv',['test','--job',str(p),'--provider','dreamina_cli','--generation-approved']), \
                 patch.object(local_video_generate.video_cli,'submit_local_video') as submit, \
                 patch.object(local_video_generate.video_cli,'local_cli_supports_model') as capability:
                self.assertEqual(local_video_generate.main(),1)
                submit.assert_not_called();capability.assert_not_called()

    def test_audio_stream_is_not_speech(self):
        with patch.object(review_render.subprocess,'check_output',return_value=b'{"streams":[{"codec_type":"audio"}]}'), \
             patch.object(review_render,'file_hash',return_value='hash'):
            out=review_render.assess({'segments':segments()},'fixture',{'mediaSha256':'hash','segments':[]})
            self.assertEqual(out['status'],'failed');self.assertTrue(out['audioStream'])

    def test_stills_cannot_approve_render(self):
        s=segments();asr={'mediaSha256':'hash','segments':[{'start':0,'end':4,'text':'Look at this pink.'}]}
        visual={'mediaSha256':'hash','promptDigest':digest(s),'reviewer':'fixture','reviewedAt':'now',
                'checks':{k:True for k in ('hook','actions','product','continuity','speechAudible','dialogueComplete')}}
        with patch.object(review_render.subprocess,'check_output',return_value=b'{"streams":[{"codec_type":"audio"}]}'), \
             patch.object(review_render,'file_hash',return_value='hash'):
            self.assertEqual(review_render.assess({'segments':s},'fixture',asr,visual)['status'],'needs_review')

    def test_empty_or_partial_windows_cannot_approve(self):
        self.assertFalse(review_render.valid_windows([{}],4))
        self.assertFalse(review_render.valid_windows([{'start':1,'end':4,'observation':'missing opening'}],4))
        self.assertFalse(review_render.valid_windows([{'start':0,'end':2,'observation':'missing ending'}],4))
        self.assertTrue(review_render.valid_windows([{'start':0,'end':4,'observation':'fixture full review'}],4))

    def test_hook_text_must_be_on_screen(self):
        s=segments();s[0]['prompt']+=' 策划说明：What changed? 屏幕文字：“Pink”'
        bp={'hook':{'expressionChannels':['text']},'hookRealization':{'channels':['text'],'message':'What changed?','beatRef':'1:1'},
            'structure':{'requiredStages':['show']},'structureRealization':[{'stage':'show','beatRef':'1:1','quote':'举瓶','rationale':'fixture'}]}
        with self.assertRaises(ValueError):validate_mechanism(s,bp,{})
        s[0]['prompt']=s[0]['prompt'].replace('屏幕文字：“Pink”','屏幕文字：“What changed?”')
        validate_mechanism(s,bp,{})

if __name__=='__main__':unittest.main()
