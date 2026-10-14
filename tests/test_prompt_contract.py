import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from model_catalog import DEFAULT_MODEL, MODEL_CATALOG
from prompt_workflow import unwrap


def sample(duration=4, timeline="[0s-4s]"):
    return {
        "output": {
            "videoPrompts": {"summary": "demo", "segments": [{
                "segmentId": 1, "title": "第1段", "duration": duration,
                "prompt": f"产品图锁定外观，达人图锁定人物。人物、产品、场景、光线、机位齐全。本段无人物口播。{timeline} 达人展示产品，环境声。",
            }]},
            "creatorPrompts": {"summary": "creator", "creators": []},
        }
    }


class PromptContractTests(unittest.TestCase):
    def test_attachment_model_scope_and_default(self):
        self.assertEqual(DEFAULT_MODEL, "seedance-2-fast")
        self.assertEqual(set(MODEL_CATALOG), {"seedance-2-fast", "seedance-2-mini", "seedance-2", "seedance-2-5"})

    def test_valid_remote_output(self):
        self.assertEqual(unwrap(sample(), "seedance-2-fast", 4)["videoPrompts"]["segments"][0]["duration"], 4)

    def test_broken_timeline_blocks_video(self):
        with self.assertRaisesRegex(Exception, "时间轴"):
            unwrap(sample(timeline="[1s-4s]"), "seedance-2-fast", 4)

    def test_overlong_segment_blocks_video(self):
        with self.assertRaisesRegex(Exception, "duration"):
            unwrap(sample(duration=16, timeline="[0s-4s][4s-8s][8s-12s][12s-16s]"), "seedance-2-fast", 16)


if __name__ == "__main__":
    unittest.main()
