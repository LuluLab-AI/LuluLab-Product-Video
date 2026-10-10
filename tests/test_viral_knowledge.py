import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys
import copy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from viral_knowledge import build_prompt_context, search_candidates


SCHEMA = '''
CREATE TABLE sources (
 id INTEGER PRIMARY KEY, views_per_hour REAL, hot_score REAL, knowledge_score REAL,
 final_candidate_score REAL, trend_label TEXT, published_at TEXT
);
CREATE TABLE gene_bundles (
 id INTEGER PRIMARY KEY, source_id INTEGER, bundle_key TEXT, title TEXT, industry TEXT, category TEXT, video_type TEXT,
 country TEXT, product_problem TEXT, selling_point_types_json TEXT, summary TEXT,
 suitable_industries_json TEXT, suitable_products_json TEXT, suitable_scenarios_json TEXT,
 avoid_json TEXT, search_text TEXT, quality_score REAL, reusability_score REAL,
 ai_generatable_score REAL, commercial_clarity_score REAL, viral_score REAL, approved INTEGER,
 use_count INTEGER DEFAULT 0, last_used_at TEXT
);
CREATE TABLE viral_assets (
 id INTEGER PRIMARY KEY, asset_key TEXT, asset_type TEXT, name TEXT, pattern TEXT, abstract_pattern TEXT,
 function TEXT, timing TEXT, applicable_categories_json TEXT, applicable_products_json TEXT,
 applicable_video_types_json TEXT, applicable_countries_json TEXT, applicable_selling_points_json TEXT,
 constraints_json TEXT, search_keywords_json TEXT, search_text TEXT, quality_score REAL, reusability_score REAL,
 ai_generatable_score REAL, source_count INTEGER DEFAULT 1, use_count INTEGER DEFAULT 0, last_used_at TEXT
);
CREATE TABLE bundle_assets (bundle_id INTEGER, asset_id INTEGER, role TEXT, sort_order INTEGER);
'''


def insert_bundle(conn, bid, source_id, key, category, selling, search, viral=80):
    conn.execute(
        "INSERT INTO gene_bundles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (bid, source_id, key, key, 'beauty' if category == 'hair-care' else 'tools', category, '剧情类',
         'US', '任务困难', f'["{selling}"]', '任务失败后产品介入并做Proof', '[]', '[]', '[]', '[]',
         search, 90, 95, 90, 90, viral, 1, 0, None)
    )


def insert_asset(conn, aid, key, typ, pattern, selling_points='[]', cats='[]', search=''):
    conn.execute(
        "INSERT INTO viral_assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (aid, key, typ, key, pattern, pattern, '', '', cats, '[]', '[]', '[]', selling_points,
         '[]', '[]', search or pattern, 90, 90, 90, 1, 0, None)
    )


def candidate_fixture(bp):
    assets = []
    for field, kind in [('structure','STRUCTURE'),('hook','HOOK'),('scene','SCENE'),('conflict','CONFLICT'),('proof','PROOF'),('cta','CTA')]:
        if bp.get(field):
            assets.append({**bp[field], 'assetType': kind})
    assets.extend({**a, 'assetType':'ACTION'} for a in bp['actions'])
    for a in assets:
        a.update({'requiresReview':False, 'sourceClass':'COMMERCE_CORE', 'evidence':[{'id':'E1','startSeconds':0,'endSeconds':2,'source':'fixture://video'}],
                  'constraints':['不新增功效'], 'sourceConstraints':['不得迁移原片功效'],
                  'promptSpec':{'physicalPrerequisites':['支持此用法'], 'fallback':'简化动作'}})
        if a['assetType']=='PROOF': a.update({'proofKind':'demonstration','claimLimit':'仅示意'})
    for a in bp['actions'] + ([bp['proof']] if bp.get('proof') else []):
        a['adaptation']={'initialState':'待操作','action':'操作','endState':'完成','riskMitigation':'简化', 'productFactRefs':['P1'],
                        'conditionChecks':[{'condition':'支持此用法','productFactRefs':['P1'],'rationale':'用户说明支持'}], 'presentation':'illustration'}
    return {'status':'ready','productProfile':{'confirmedFacts':[{'id':'P1','fact':'支持此用法','source':'用户提供说明'}]},
            'bundles':[{'bundleKey':'VB-1','knowledgeClass':'COMMERCE_CORE','requiresReview':False,'assets':assets,'transferConditions':['保留接触点']}], 'assetPools':{}}


class ViralKnowledgeTests(unittest.TestCase):
    def test_search_returns_bundle_and_seven_asset_pools(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'viral.db'
            conn = sqlite3.connect(db)
            conn.executescript(SCHEMA)
            conn.execute("INSERT INTO sources VALUES (1,12000,91,88,90,'RISING_FAST','2026-09-24T00:00:00Z')")
            insert_bundle(conn, 1, 1, 'VB-1', 'hair-care', '顺滑', 'hair hair-care 顺滑 打结 出门前')
            types = ['STRUCTURE','HOOK','SCENE','CONFLICT','ACTION','PROOF','CTA']
            for i,t in enumerate(types,1):
                sp='["顺滑"]' if t=='PROOF' else '[]'
                insert_asset(conn, i, f'{t}-1', t, f'{t}抽象', sp, '["hair-care"]', f'hair 顺滑 {t}')
                conn.execute("INSERT INTO bundle_assets VALUES (1,?,?,?)", (i,'primary' if t=='STRUCTURE' else 'support',i))
            conn.commit(); conn.close()
            request={'productBrief':{'productName':'护发精油','targetCountry':'US','targetAudience':'女性'},'userConfig':{'videoStyle':'storyDrivenAd'}}
            profile={'industry':'beauty','category':'hair-care','productType':'护发产品','painPoints':['打结'],'sellingPointTypes':['顺滑'],'sellingPointMechanisms':['SMOOTH'],'targetCountry':'US','videoStyle':'storyDrivenAd'}
            out=search_candidates(db,request,profile,30,30)
            self.assertEqual(out['status'],'ready')
            self.assertEqual(out['bundles'][0]['bundleKey'],'VB-1')
            self.assertEqual(out['bundles'][0]['trend']['label'],'RISING_FAST')
            self.assertEqual(set(out['assetPools']), set(types))
            self.assertEqual(out['assetPools']['PROOF'][0]['assetKey'],'PROOF-1')
            self.assertTrue(out['assetPools']['PROOF'][0]['compatibility']['requiresPhysicalValidation'])

    def test_cross_category_proof_prefers_mechanism_over_source_category(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'viral.db'
            conn = sqlite3.connect(db); conn.executescript(SCHEMA)
            conn.execute("INSERT INTO sources VALUES (1,10000,90,90,90,'RISING_FAST',NULL)")
            conn.execute("INSERT INTO sources VALUES (2,9000,88,88,88,'RISING',NULL)")
            insert_bundle(conn, 1, 1, 'VB-hair', 'hair-care', '顺滑', 'hair smooth')
            insert_bundle(conn, 2, 2, 'VB-tools', 'power-tools', '强力', 'impact wrench torque strong')
            # Higher-quality but wrong-mechanism proof from hair care.
            insert_asset(conn, 1, 'PROOF-smooth', 'PROOF', '重复梳头动作证明顺滑', '["顺滑"]', '["hair-care"]', 'smooth hair repeat action')
            conn.execute("UPDATE viral_assets SET quality_score=99 WHERE id=1")
            # Slightly lower quality but correct STRONG/torque mechanism.
            insert_asset(conn, 2, 'PROOF-torque', 'PROOF', '重新执行高阻力任务并成功完成', '["强力","高扭矩"]', '["power-tools"]', 'torque strong task completion')
            conn.execute("UPDATE viral_assets SET quality_score=82 WHERE id=2")
            conn.execute("INSERT INTO bundle_assets VALUES (1,1,'support',1)")
            conn.execute("INSERT INTO bundle_assets VALUES (2,2,'support',1)")
            conn.commit(); conn.close()
            request={'productBrief':{'productName':'冲击扳手','targetCountry':'US'},'userConfig':{'videoStyle':'ugcProductDemo'}}
            profile={'industry':'tools','category':'power-tools','productType':'impact wrench','sellingPointTypes':['强力','快速'],'sellingPointMechanisms':['STRONG','FAST'],'desiredProofTypes':['任务完成'],'useScenarios':['garage','car repair'],'targetCountry':'US','videoStyle':'ugcProductDemo'}
            out=search_candidates(db,request,profile,30,30)
            proofs=out['assetPools']['PROOF']
            self.assertEqual(proofs[0]['assetKey'],'PROOF-torque')
            smooth=next(x for x in proofs if x['assetKey']=='PROOF-smooth')
            self.assertTrue(smooth['compatibility']['lowMechanismMatchWarning'])

    def test_trend_is_small_positive_signal_for_otherwise_equal_bundles(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'viral.db'
            conn=sqlite3.connect(db); conn.executescript(SCHEMA)
            conn.execute("INSERT INTO sources VALUES (1,18000,95,85,91,'RISING_FAST',NULL)")
            conn.execute("INSERT INTO sources VALUES (2,1000,45,85,60,'NORMAL',NULL)")
            insert_bundle(conn,1,1,'VB-fast','hair-care','顺滑','hair smooth')
            insert_bundle(conn,2,2,'VB-normal','hair-care','顺滑','hair smooth')
            conn.commit(); conn.close()
            request={'productBrief':{'productName':'护发精油','targetCountry':'US'},'userConfig':{'videoStyle':'storyDrivenAd'}}
            profile={'industry':'beauty','category':'hair-care','productType':'护发产品','sellingPointTypes':['顺滑'],'sellingPointMechanisms':['SMOOTH'],'targetCountry':'US','videoStyle':'storyDrivenAd'}
            out=search_candidates(db,request,profile,30,30)
            self.assertEqual(out['bundles'][0]['bundleKey'],'VB-fast')
            self.assertGreater(out['bundles'][0]['match']['trend'], out['bundles'][1]['match']['trend'])
            # The scoring gap stays small: trend is a tie-breaker, not the primary relevance driver.
            self.assertLess(out['bundles'][0]['score'] - out['bundles'][1]['score'], 0.08)

    def test_blueprint_builds_single_required_context_with_transfer_notes(self):
        bp={
            'blueprintId':'CB-001','primaryBundleKey':'VB-1','title':'测试',
            'structure':{'assetKey':'STRUCTURE-1','pattern':'失败→解决→验证'},
            'hook':{'assetKey':'HOOK-1','pattern':'痛点动作开场'},
            'scene':{'assetKey':'SCENE-1','pattern':'车库'},
            'conflict':{'assetKey':'CONFLICT-1','pattern':'任务失败'},
            'actions':[{'assetKey':'ACTION-1','pattern':'失败→产品→重试'}],
            'proof':{'assetKey':'PROOF-1','pattern':'重复动作成功'},
            'cta':{'assetKey':'CTA-1','pattern':'反应型软CTA'},
            'sellingPointMapping':'强力卖点通过重新完成高阻力任务证明',
            'transferNotes':'Structure来自跨品类抽象，只迁移因果结构，不迁移原产品动作。'
        }
        ctx=build_prompt_context(bp,candidate_fixture(bp))
        self.assertEqual(len(ctx['matches']),1)
        self.assertEqual(ctx['matches'][0]['templateId'],'CB-001')
        self.assertIn('Primary Gene Bundle：VB-1',ctx['matches'][0]['prompt'])
        self.assertIn('跨品类迁移约束',ctx['matches'][0]['prompt'])
        self.assertIn('重复动作成功',ctx['matches'][0]['conversionPattern'])
        self.assertIn('不新增功效',ctx['matches'][0]['prompt'])
        self.assertIn('startSeconds',ctx['matches'][0]['prompt'])
        self.assertIn('fallback',ctx['matches'][0]['prompt'])

    def test_blueprint_contract_rejects_missing_and_forged_data(self):
        base={'blueprintId':'CB','primaryBundleKey':'VB-1', 'structure':{'assetKey':'S','pattern':'结构'}, 'hook':{'assetKey':'H','pattern':'开场'},
              'actions':[{'assetKey':'A','pattern':'使用'}], 'proof':None, 'proofOmissionReason':'无效果证据'}
        pack=candidate_fixture(base)
        ctx=build_prompt_context(base,pack)
        self.assertIn('不使用Proof',ctx['matches'][0]['prompt'])
        for mutation in ('primary','key','pattern','facts','conditions','reason','legacy'):
            bp=copy.deepcopy(base); cp=copy.deepcopy(pack)
            if mutation=='primary': bp.pop('primaryBundleKey')
            if mutation=='key': bp['hook']['assetKey']='invented'
            if mutation=='pattern': bp['hook']['pattern']='新编内容'
            if mutation=='facts': bp['actions'][0]['adaptation']['productFactRefs']=['fake']
            if mutation=='conditions': bp['actions'][0]['adaptation']['conditionChecks']=[]
            if mutation=='reason': bp.pop('proofOmissionReason')
            if mutation=='legacy': cp['bundles'][0]['requiresReview']=True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): build_prompt_context(bp,cp)
        with self.assertRaises(ValueError): build_prompt_context(base)

    def test_creator_claim_cannot_be_proof(self):
        bp={'blueprintId':'CB','primaryBundleKey':'VB-1','structure':{'assetKey':'S'},'hook':{'assetKey':'H'},
            'actions':[{'assetKey':'A'}],'proof':{'assetKey':'P'}}
        cp=candidate_fixture(bp)
        next(a for a in cp['bundles'][0]['assets'] if a['assetType']=='PROOF')['proofKind']='creator-claim'
        with self.assertRaisesRegex(ValueError, 'creator-claim'): build_prompt_context(bp,cp)

    def test_prompt_renderer_never_silently_truncates(self):
        from prompt_library import render_context, PromptLibraryError
        context={'schemaVersion':'1.0','status':'ready','matches':[{'templateId':'X','prompt':'x'*2000}]}
        with self.assertRaises(PromptLibraryError): render_context(context,max_chars=1000)


if __name__ == '__main__': unittest.main()
