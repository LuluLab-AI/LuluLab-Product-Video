import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from local.orchestrator import prepare
from local.product_profile import normalize_profile
from local.retrieval import retrieve
from local.creative_planner import validate_blueprints
from local.execution_spec import build_execution_spec
from local_prompt import build_prompt
from quality_gate import validate_execution_translation
from scripts.retrieval_terms import country, concepts, CATEGORIES


PATTERN = {"patternKey":"P1","patternClusterKey":"task-retry","name":"失败后重试",
           "abstractFlow":["任务失败","产品介入","重试成功"],
           "requiredRelationships":["重试必须是同一个任务"],
           "replaceableSlots":["产品","场景"],"mechanismTags":["任务失败","重试"],
           "assetKeys":["A1"]}
EXECUTION = {"firstFrame":{"visualMechanism":"失败动作"},
             "beatTimeline":[{"evidenceRefs":["E1"]}],"timing":{"hookEndRatio":.2},
             "executionInvariants":["任务一致"],"generationRisks":["物体瞬移"]}
FACTS = [{"id":"F1","fact":"产品可被真实操作","source":"user"}]


def make_db(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE gene_bundles(id INTEGER PRIMARY KEY,bundle_key TEXT UNIQUE,source_id INTEGER,category TEXT,
      industry TEXT,country TEXT,knowledge_class TEXT,approved INTEGER,use_count INTEGER,contract_json TEXT);
    CREATE TABLE viral_assets(id INTEGER PRIMARY KEY,asset_key TEXT,asset_type TEXT,contract_json TEXT);
    CREATE TABLE bundle_assets(bundle_id INTEGER,asset_id INTEGER);
    CREATE TABLE creative_patterns(pattern_key TEXT PRIMARY KEY,bundle_key TEXT,cluster_key TEXT,
      pattern_json TEXT,scores_json TEXT,independent_video_count INTEGER,independent_creator_count INTEGER);
    CREATE TABLE execution_patterns(pattern_key TEXT PRIMARY KEY,execution_json TEXT);
    CREATE TABLE knowledge_embeddings(pattern_key TEXT,model_id TEXT,vector_json TEXT);
    CREATE TABLE generation_feedback(pattern_key TEXT,review_stage TEXT,scores_json TEXT,rendered_passed INTEGER);
    """)
    conn.execute("INSERT INTO gene_bundles VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (1,"B1",1,"hardware","tools","美国","COMMERCE_CORE",1,0,
                  '{"generationReadiness":"ready"}'))
    conn.execute("INSERT INTO viral_assets VALUES(?,?,?,?)",(1,"A1","HOOK",'{"generationReadiness":"ready"}'))
    conn.execute("INSERT INTO bundle_assets VALUES(?,?)",(1,1))
    conn.execute("INSERT INTO creative_patterns VALUES(?,?,?,?,?,?,?)",
                 ("P1","B1","task-retry",json.dumps(PATTERN,ensure_ascii=False),
                  json.dumps({"creativeStrength":4,"transferability":5,"aiGeneratable":4}),1,1))
    conn.execute("INSERT INTO execution_patterns VALUES(?,?)",("P1",json.dumps(EXECUTION,ensure_ascii=False)))
    conn.commit()
    return conn


def blue(index, hook=None, scene=None):
    return {"blueprintId":f"CB-{index}","patternKey":"P1","format":"demonstration",
            "assetKeys":["A1"],
            "creativeHypothesis":f"假设{index}:从不同任务切入","hook":hook or f"开场失败{index}",
            "scene":scene or f"场景{index}","conflict":f"冲突{index}",
            "actions":[f"真实动作{index}"],"proof":None,"proofOmissionReason":"无效果证明",
            "actionGrounding":[{"action":f"真实动作{index}","factRefs":["F1"],
                                "initialState":"待操作","endState":"已操作","physicalCheck":"可真实执行"}],
            "cta":None,"ctaOrigin":"no-cta",
            "relationshipMappings":[{"sourceRelationship":"重试必须是同一个任务",
                                     "realization":f"任务{index}前后保持一致","beatRefs":["1"]}]}


class LocalV3Tests(unittest.TestCase):
    def test_bilingual_category_and_country_normalization(self):
        self.assertEqual(concepts("lip gloss", CATEGORIES), concepts("唇彩", CATEGORIES))
        self.assertEqual(country("美国"), country("US"))

    def test_auto_fallback_but_explicit_knowledge_blocks_when_no_v3_patterns(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/"empty.db"
            sqlite3.connect(db).close()
            request={"productBrief":{"productName":"唇彩","targetCountry":"美国","productImages":[]},
                     "userConfig":{"videoModel":"seedance-2-fast","duration":15}}
            direct=prepare(request,{},"AUTO",db)
            self.assertEqual(direct["strategyUsed"],"DIRECT")
            self.assertEqual(direct["fallbackReason"],"NO_APPROVED_V3_PATTERNS")
            blocked=prepare(request,{},"KNOWLEDGE",db)
            self.assertEqual(blocked["status"],"blocked")
            self.assertIsNone(blocked["strategyUsed"])

    def test_profile_cannot_invent_selling_point_mechanism(self):
        request={"productBrief":{"productName":"唇彩","targetCountry":"美国","productImages":[{"path":"/fixture/lip.jpg"}]},
                 "userConfig":{"videoModel":"seedance-2-fast","duration":15}}
        profile={"confirmedFacts":[{"id":"F1","fact":"粉色珠光可见","source":"product-image",
                                    "mechanisms":["SHIMMER"]}],"solutionMechanisms":["WATERPROOF"]}
        with self.assertRaisesRegex(ValueError,"未被 confirmedFacts"):
            normalize_profile(request,profile)
        profile["solutionMechanisms"]=["SHIMMER"]
        self.assertEqual(normalize_profile(request,profile)["solutionMechanisms"],["SHIMMER"])

    def test_cross_category_pattern_recalled_and_use_count_does_not_penalize(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"v3.db"
            conn=make_db(db)
            profile={"category":"hair-care","productType":"护发产品","problemMechanisms":["任务失败"],
                     "targetCountry":"美国"}
            before=retrieve(db,profile)
            self.assertEqual(before["candidates"][0]["patternKey"],"P1")
            self.assertGreater(before["candidates"][0]["match"]["structuredMechanism"],0)
            conn.execute("UPDATE gene_bundles SET use_count=999 WHERE bundle_key='B1'")
            conn.execute("INSERT INTO generation_feedback VALUES(?,?,?,?)",("P1","render-review","{}",0))
            conn.commit()
            after=retrieve(db,profile)
            self.assertEqual(after["candidates"][0]["recallScore"],before["candidates"][0]["recallScore"])
            self.assertFalse(after["candidates"][0]["feedback"]["rankingEligible"])
            conn.close()

    def test_restricted_asset_cannot_enter_retrieval(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"v3.db"
            conn=make_db(db)
            conn.execute("UPDATE viral_assets SET contract_json=? WHERE asset_key='A1'",
                         ('{"generationReadiness":"needs_review","readinessReasons":["声音未核实"]}',))
            conn.commit()
            self.assertEqual(retrieve(db,{"category":"hair-care"})["status"],"no_usable_knowledge")
            conn.close()

    def test_limited_pattern_requires_explicit_handling(self):
        candidate={"patternKey":"P1","pattern":PATTERN,"knowledgeClass":"COMMERCE_CORE",
                   "generationReadiness":"limited","readinessReasons":["音频未核实"],"assets":[]}
        bp=blue(1)
        with self.assertRaisesRegex(ValueError,"有限可用"):
            validate_blueprints([bp],[candidate],1,FACTS)
        bp["limitationChecks"]=[{"limitation":"音频未核实","handling":"使用当前产品原创实测口播，不迁移来源语气"}]
        validate_blueprints([bp],[candidate],1,FACTS)

    def test_four_blueprints_need_four_hypotheses_and_preserve_relationships(self):
        candidates=[{"patternKey":"P1","pattern":PATTERN,"knowledgeClass":"COMMERCE_CORE"}]
        plans=[blue(i) for i in range(1,5)]
        self.assertEqual(len(validate_blueprints(plans,candidates,4,FACTS)),4)
        duplicate=dict(plans[3],blueprintId="CB-4b",creativeHypothesis=plans[0]["creativeHypothesis"])
        with self.assertRaisesRegex(ValueError,"不同创意假设"):
            validate_blueprints(plans[:3]+[duplicate],candidates,4,FACTS)
        broken=blue(5)
        broken["relationshipMappings"]=[]
        with self.assertRaisesRegex(ValueError,"requiredRelationships"):
            validate_blueprints([broken],candidates,1,FACTS)

    def test_execution_spec_and_prompt_cannot_reselect_story(self):
        bp=blue(1,hook="开场失败",scene="浴室")
        source={"patternKey":"P1","pattern":PATTERN,"executionPattern":EXECUTION}
        authored={"blueprintId":"CB-1","format":"demonstration","duration":4,
                  "hookChannel":"speech","buyReason":"可见颜色","endingIntent":"自然结束",
                  "voiceDescription":"成年女性美式英语轻快","productContinuity":"粉色唇彩一致",
                  "creatorContinuity":"同一位成年女性",
                  "beats":[{"beatRef":"1","start":0,"end":4,"visual":"开场失败后展示粉色唇彩",
                            "action":"真实动作1","camera":"手持近景","audio":"环境声",
                            "initialState":{"product":"手中"},"endState":{"product":"嘴边"},
                            "speech":{"role":"主角","text":"开场失败，这颜色看着真亮。"}}]}
        spec=build_execution_spec(bp,source,4,authored)
        request={"productBrief":{"productName":"唇彩","targetCountry":"美国","productImages":[]},
                 "userConfig":{"videoModel":"seedance-2-fast","duration":4,"videoStyle":"storyDrivenAd"}}
        rendered=build_prompt(request["productBrief"],request["userConfig"],execution_spec=spec)
        self.assertIn("Execution Spec",rendered)
        self.assertIn("demonstration",rendered)
        self.assertNotIn("UGC模式要求",rendered)
        self.assertNotIn("剧情模式要求",rendered)
        authored["beats"][0]["action"]="别的动作"
        with self.assertRaisesRegex(ValueError,"产品动作未落实"):
            build_execution_spec(bp,source,4,authored)

    def test_submission_gate_rejects_dropped_execution_beat(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"v3.db"
            conn=make_db(db)
            bp=blue(1,hook="开场失败")
            source=retrieve(db,{"problemMechanisms":["任务失败"]})["candidates"][0]
            authored={"blueprintId":"CB-1","format":"demonstration","duration":4,
                      "hookChannel":"speech","buyReason":"可见颜色","endingIntent":"自然结束",
                      "voiceDescription":"成年女性美式英语轻快","productContinuity":"产品保持一致",
                      "creatorContinuity":"同一位达人",
                      "beats":[{"beatRef":"1","start":0,"end":4,"visual":"开场失败后展示产品",
                                "action":"真实动作1","camera":"近景","audio":"环境声",
                                "initialState":{"product":"手中"},"endState":{"product":"嘴边"},
                                "speech":{"role":"主角","text":"开场失败，看看颜色。"}}]}
            spec=build_execution_spec(bp,source,4,authored)
            prompt="成年女性美式英语轻快。\n[0s-4s] 开场失败后展示产品；真实动作1；口播（主角）：“开场失败，看看颜色。”；可见颜色；自然结束。"
            job={"knowledgeDb":str(db),"creativeBlueprint":bp,"executionSpec":spec,
                 "productProfile":{"confirmedFacts":FACTS},"qualityReview":{"mechanismChecked":True}}
            validate_execution_translation(job,[{"segmentId":1,"duration":4,"prompt":prompt}])
            with self.assertRaisesRegex(ValueError,"action 未进入"):
                validate_execution_translation(job,[{"segmentId":1,"duration":4,
                     "prompt":prompt.replace("真实动作1","摆拍") }])
            conn.close()


if __name__ == "__main__":
    unittest.main()
