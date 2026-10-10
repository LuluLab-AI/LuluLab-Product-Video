from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import local_creator_image_generate as creator  # noqa: E402
import video_cli  # noqa: E402


class CreatorImageTests(unittest.TestCase):
    def test_submission_uses_all_product_references_and_exact_image_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / "a.png", Path(directory) / "b.jpg"]
            for path in paths:
                path.write_bytes(b"reference")
            uploads = iter([{"url": "https://example.test/a", "mimeType": "image/png", "expiresAt": "short"},
                            {"url": "https://example.test/b", "mimeType": "image/jpeg", "expiresAt": "short"}])
            def response(executable, args, **kwargs):
                if args[0] == "upload":
                    return next(uploads)
                return {"id": "task-1"}
            with patch.object(video_cli, "resolve_lululab_cli", return_value=Path("/tmp/lululab.mjs")), \
                    patch.object(video_cli, "_run_process") as proc, \
                    patch.object(video_cli, "_run_json", side_effect=response) as run:
                proc.side_effect = [type("P", (), {"returncode": 0, "stdout": "--workflow-id --input", "stderr": ""})(),
                                    type("P", (), {"returncode": 0, "stdout": "--id", "stderr": ""})()]
                task = video_cli.submit_lululab_image("  creator prompt  ", reference_files=[*paths, paths[0]])
            self.assertEqual(task, "task-1")
            self.assertEqual([call.args[1][1] for call in run.call_args_list[:2]], [str(path.resolve()) for path in paths])
            command = run.call_args_list[2].args[1]
            self.assertEqual(command[:4], ["task", "submit", "--workflow-id", "ImageGenV2"])
            payload = json.loads(command[5])
            self.assertEqual(payload["model"], "gpt-image-2-5-sunburst")
            self.assertEqual(payload["resolution"], "1K")
            self.assertEqual(payload["aspectRatio"], "9:16")
            self.assertEqual(payload["prompt"], "creator prompt")
            self.assertEqual(payload["referenceImages"], [
                {"url": "https://example.test/a", "mimeType": "image/png"},
                {"url": "https://example.test/b", "mimeType": "image/jpeg"},
            ])

    def test_success_media_must_come_from_output_not_input(self):
        self.assertEqual(creator.output_image_url({"input": {"referenceImages": [{"url": "https://example.test/input"}]},
                                                   "output": {"image": {"url": "https://example.test/output"}}}),
                         "https://example.test/output")
        with self.assertRaises(creator.CreatorImageError):
            creator.output_image_url({"input": {"referenceImages": [{"url": "https://example.test/input"}]}})

    def test_explicit_supported_model_reaches_paid_payload(self):
        with patch.object(video_cli, "resolve_lululab_cli", return_value=Path("/tmp/lululab.mjs")), \
                patch.object(video_cli, "_run_process") as proc, \
                patch.object(video_cli, "_run_json", return_value={"id": "task-2"}) as run:
            proc.side_effect = [type("P", (), {"returncode": 0, "stdout": "--workflow-id --input", "stderr": ""})(),
                                type("P", (), {"returncode": 0, "stdout": "--id", "stderr": ""})()]
            video_cli.submit_lululab_image("creator prompt", uploaded_references=[
                {"url": "https://example.test/a", "mimeType": "image/png"}], model="gpt-image-2-5-flare")
        command = run.call_args.args[1]
        self.assertEqual(command[3], "ImageGenV2")
        self.assertEqual(json.loads(command[5])["model"], "gpt-image-2-5-flare")
        with self.assertRaises(video_cli.VideoCliError):
            video_cli.submit_lululab_image("creator prompt", model="unsupported")

    def test_upload_failure_leaves_no_uncertain_paid_task(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt.txt"; prompt.write_text("creator prompt")
            product = root / "product.png"; product.write_bytes(b"product")
            report = root / "creator-task.json"
            args = ["script", "--prompt-file", str(prompt), "--reference-image", str(product),
                    "--output", str(root / "creator.png"), "--report", str(report)]
            with patch.object(sys, "argv", args), patch.object(video_cli, "get_lululab_credit_balance", return_value=10), \
                    patch.object(video_cli, "upload_lululab_image_references", side_effect=video_cli.VideoCliError("upload failed")), \
                    patch.object(video_cli, "submit_lululab_image") as submit:
                self.assertEqual(creator.main(), 1)
            self.assertFalse(report.exists())
            submit.assert_not_called()

    def test_uncertain_submission_does_not_repeat_billing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt.txt"; prompt.write_text("creator prompt")
            product = root / "product.png"; product.write_bytes(b"product")
            output = root / "creator.png"; report = root / "creator-task.json"
            args = ["script", "--prompt-file", str(prompt), "--reference-image", str(product),
                    "--output", str(output), "--report", str(report)]
            with patch.object(sys, "argv", args), patch.object(video_cli, "get_lululab_credit_balance", return_value=10), \
                    patch.object(video_cli, "upload_lululab_image_references", return_value=[{"url":"https://example.test/product","mimeType":"image/png"}]), \
                    patch.object(video_cli, "submit_lululab_image", side_effect=video_cli.VideoCliError("network")) as submit:
                self.assertEqual(creator.main(), 1)
                self.assertEqual(creator.main(), 1)
            self.assertEqual(submit.call_count, 1)
            self.assertEqual(json.loads(report.read_text())["status"], "submit_started_uncertain")

    def test_entrypoint_default_model_matches_state_and_submit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt.txt"; prompt.write_text("creator prompt")
            product = root / "product.png"; product.write_bytes(b"product")
            report = root / "creator-task.json"
            args = ["script", "--prompt-file", str(prompt), "--reference-image", str(product),
                    "--output", str(root / "creator.png"), "--report", str(report)]
            with patch.object(sys, "argv", args), \
                    patch.object(video_cli, "get_lululab_credit_balance", return_value=10), \
                    patch.object(video_cli, "upload_lululab_image_references", return_value=[
                        {"url": "https://example.test/product", "mimeType": "image/png"}]), \
                    patch.object(video_cli, "submit_lululab_image", return_value="task-1") as submit, \
                    patch.object(video_cli, "poll_local_video", side_effect=video_cli.VideoCliError("timeout")), \
                    patch.object(video_cli, "fetch_lululab_image", return_value={"status": "running"}):
                self.assertEqual(creator.main(), 1)
            self.assertEqual(submit.call_args.kwargs["model"], "gpt-image-2-5-sunburst")
            self.assertEqual(json.loads(report.read_text())["model"], "gpt-image-2-5-sunburst")
            self.assertEqual(json.loads(report.read_text())["taskId"], "task-1")


if __name__ == "__main__":
    unittest.main()
