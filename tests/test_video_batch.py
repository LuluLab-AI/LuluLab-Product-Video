from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import local_video_generate as generator


class AtomicVideoBatchTests(unittest.TestCase):
    def test_insufficient_credits_stop_every_segment_without_single_submit_or_poll(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = root / "job.json"
            job.write_text(json.dumps({"videoModel": "seedance-2-mini", "segments": [
                {"segmentId": 1, "duration": 12, "prompt": "first"},
                {"segmentId": 2, "duration": 10, "prompt": "second"}]}))
            with patch.object(sys, "argv", ["run", "--job", str(job), "--provider", "lululab_cli", "--generation-approved"]), \
                    patch("quality_gate.validate_job"), \
                    patch.object(generator.video_cli, "local_cli_supports_model", return_value=True), \
                    patch.object(generator.video_cli, "submit_lululab_video_batch", side_effect=generator.video_cli.CreditsInsufficient("insufficient")) as batch, \
                    patch.object(generator.video_cli, "submit_local_video") as single, \
                    patch.object(generator.video_cli, "poll_local_video") as poll:
                self.assertEqual(generator.main(), 1)
            self.assertEqual(len(batch.call_args.args[0]), 2)
            single.assert_not_called()
            poll.assert_not_called()
            state = json.loads((root / "local-video-generation.json").read_text())
            self.assertTrue(all(record["status"] == "credits_required" for record in state["segments"].values()))

    def test_exact_balance_batch_returns_all_ids_before_polling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = root / "job.json"
            job.write_text(json.dumps({"videoModel": "seedance-2-mini", "segments": [
                {"segmentId": 1, "duration": 12, "prompt": "first"},
                {"segmentId": 2, "duration": 10, "prompt": "second"}]}))
            def poll(provider, task_id, *, on_status):
                state = json.loads((root / "local-video-generation.json").read_text())
                self.assertEqual([state["segments"][str(i)]["taskId"] for i in [1, 2]], ["task-1", "task-2"])
                return {"output": {"video": {"url": "https://example.test/video.mp4"}}}
            def download(url, path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"video")
                return path
            def merge(*args, **kwargs):
                (root / "final_video.mp4").write_bytes(b"merged")
                return SimpleNamespace(returncode=0)
            with patch.object(sys, "argv", ["run", "--job", str(job), "--provider", "lululab_cli", "--generation-approved"]), \
                    patch("quality_gate.validate_job"), \
                    patch.object(generator.video_cli, "local_cli_supports_model", return_value=True), \
                    patch.object(generator.video_cli, "submit_lululab_video_batch", return_value=["task-1", "task-2"]) as batch, \
                    patch.object(generator.video_cli, "submit_local_video") as single, \
                    patch.object(generator.video_cli, "poll_local_video", side_effect=poll), \
                    patch.object(generator.video_cli, "get_lululab_credit_balance", return_value=0), \
                    patch.object(generator, "download", side_effect=download), \
                    patch.object(generator.subprocess, "run", side_effect=merge):
                self.assertEqual(generator.main(), 0)
            batch.assert_called_once()
            single.assert_not_called()


if __name__ == "__main__":
    unittest.main()
