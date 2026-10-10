from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import local_video_generate as generator  # noqa: E402


class ResumeVideoTests(unittest.TestCase):
    def test_existing_task_is_queried_and_final_video_created_without_resubmission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = root / "job.json"
            job.write_text(json.dumps({"videoModel": "seedance-2-fast", "segments": [
                {"segmentId": 1, "duration": 5, "prompt": "test", "referenceFiles": ["unused.png"]}]}))
            state = root / "local-video-generation.json"
            state.write_text(json.dumps({"provider": "lululab_cli", "segments": {
                "1": {"status": "submitted", "taskId": "task-existing"}}}))
            def poll(provider, task_id, *, on_status):
                self.assertEqual(task_id, "task-existing")
                on_status("running", {"status": "Running", "startedAt": "2026-10-09T04:00:00Z"})
                on_status("succeeded", {"status": "Succeeded", "startedAt": "2026-10-09T04:00:00Z"})
                return {"status": "Succeeded", "output": {"video": {"url": "https://example.test/video.mp4"}}}
            def save(url, path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"video")
                return path
            with patch.object(sys, "argv", ["run", "--job", str(job), "--provider", "lululab_cli", "--generation-approved"]), \
                    patch("quality_gate.validate_job"), \
                    patch.object(generator.video_cli, "local_cli_supports_model", return_value=True), \
                    patch.object(generator.video_cli, "submit_local_video") as submit, \
                    patch.object(generator.video_cli, "poll_local_video", side_effect=poll), \
                    patch.object(generator.video_cli, "get_lululab_credit_balance", return_value=100), \
                    patch.object(generator, "download", side_effect=save):
                self.assertEqual(generator.main(), 0)
            submit.assert_not_called()
            self.assertEqual((root / "final_video.mp4").read_bytes(), b"video")
            result = json.loads(state.read_text())
            self.assertEqual(result["segments"]["1"]["remoteStatus"], "succeeded")
            self.assertEqual(result["finalVideo"], str((root / "final_video.mp4").resolve()))


if __name__ == "__main__":
    unittest.main()
