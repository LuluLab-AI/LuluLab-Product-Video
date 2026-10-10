from __future__ import annotations

import os
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import video_cli  # noqa: E402


class VideoCliTests(unittest.TestCase):
    def _fake_cli(self, root: Path, name: str, model_id: str) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        path = root / name
        path.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"multimodal2video\" ] && [ \"$2\" = \"--help\" ]; then\n"
            f"  echo '--image --prompt --duration --ratio --video_resolution --model_version {model_id}'\n"
            "  exit 0\n"
            "fi\n"
            "if [ \"$1\" = \"query_result\" ] && [ \"$2\" = \"--help\" ]; then\n"
            "  echo '--submit_id'\n"
            "  exit 0\n"
            "fi\n"
            "echo '{\"id\":\"task-1\"}'\n",
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_missing_task_parameters_cannot_submit_video(self):
        general = "Commands: task upload user --api-key"
        fetch = "--id --api-key"
        with patch.object(video_cli, "_local_executable", return_value=Path("/tmp/lululab")), patch.object(
            video_cli, "_run_process", side_effect=[
                subprocess.CompletedProcess([], 0, general, ""),
                subprocess.CompletedProcess([], 0, fetch, ""),
            ]
        ), patch.object(video_cli, "_run_json") as run:
            with self.assertRaisesRegex(video_cli.VideoCliError, "能力检查"):
                video_cli.submit_local_video("lululab_cli", "seedance-2-fast", "prompt", 15)
        run.assert_not_called()

    def test_lululab_credits_use_user_command(self):
        with patch.object(video_cli, "resolve_lululab_cli", return_value=Path("/tmp/lululab")), patch.object(
            video_cli, "resolve_lululab_api_key", return_value="test-key"
        ), patch.object(video_cli, "_run_json", return_value={"data": {"balance": 123}}) as run:
            self.assertEqual(video_cli.get_lululab_credit_balance(), 123)
        self.assertEqual(run.call_args.args[1], ["user", "--credits"])

    def test_lululab_key_precedence_and_legacy_compatibility(self):
        with patch.dict(os.environ, {"LULULAB_API_KEY": "new-test", "LINGZHI_API_KEY": "old-test"}, clear=True):
            self.assertEqual(video_cli.resolve_lululab_api_key(), "new-test")
        with patch.dict(os.environ, {"LINGZHI_API_KEY": "old-test"}, clear=True):
            self.assertEqual(video_cli.resolve_lululab_api_key(), "old-test")

    def test_lululab_upload_and_task_submission_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            product, creator = Path(directory) / "product.png", Path(directory) / "creator.jpg"
            product.write_bytes(b"product")
            creator.write_bytes(b"creator")
            for model in sorted(video_cli.LULULAB_MODEL_IDS):
                with self.subTest(model=model), patch.object(video_cli, "local_cli_supports_model", return_value=True), patch.object(
                    video_cli, "_local_executable", return_value=Path("/tmp/lululab")
                ), patch.object(video_cli, "resolve_lululab_api_key", return_value="test-key"), patch.dict(
                    os.environ, {"LULULAB_VIDEO_WORKFLOW_ID": ""}
                ), patch.object(video_cli, "_run_json", side_effect=[
                    {"url": "https://example.test/product", "mimeType": "image/png", "expiredAt": "later"},
                    {"data": {"url": "https://example.test/creator", "expiresAt": "later"}},
                    {"data": {"result": {"id": "task-1"}}},
                ]) as run:
                    task = video_cli.submit_local_video("lululab_cli", model, "prompt", 15,
                                                      reference_files=[product, creator, product])
                    self.assertEqual(task, "task-1")
                    self.assertEqual(run.call_count, 3)
                    self.assertEqual(run.call_args_list[0].args[1][:2], ["upload", str(product.resolve())])
                    self.assertEqual(run.call_args_list[1].args[1][:2], ["upload", str(creator.resolve())])
                    args = run.call_args.args[1]
                    self.assertEqual(args[:4], ["task", "submit", "--workflow-id", "VideoGenV2"])
                    payload = json.loads(args[args.index("--input") + 1])
                    self.assertEqual(payload, {"model": model, "prompt": "prompt", "duration": 15,
                        "aspectRatio": "9:16", "resolution": "720p", "referenceImages": [
                            {"url": "https://example.test/product", "mimeType": "image/png", "expiredAt": "later"},
                            {"url": "https://example.test/creator", "mimeType": "image/jpeg", "expiredAt": "later"}]})
                    self.assertNotIn("test-key", json.dumps(payload))

    def test_lululab_preflight_accepts_generic_task_interface(self):
        with patch.object(video_cli, "_local_executable", return_value=Path("/tmp/lululab")), patch.object(
            video_cli, "_run_process", side_effect=[
                subprocess.CompletedProcess([], 0, "--workflow-id --input --api-key", ""),
                subprocess.CompletedProcess([], 0, "--id --api-key", ""),
            ]
        ) as run:
            self.assertTrue(video_cli.local_cli_supports_model("lululab_cli", "seedance-2-fast"))
        self.assertEqual(run.call_args_list[0].args[1], ["task", "submit", "--help"])

    def test_invalid_upload_result_prevents_task_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            product = Path(directory) / "product.png"
            product.write_bytes(b"product")
            with patch.object(video_cli, "local_cli_supports_model", return_value=True), patch.object(
                video_cli, "_local_executable", return_value=Path("/tmp/lululab")
            ), patch.object(video_cli, "resolve_lululab_api_key", return_value="test-key"), patch.object(
                video_cli, "_run_json", return_value={"error": "upload failed"}
            ) as run:
                with self.assertRaises(video_cli.VideoCliError):
                    video_cli.submit_local_video("lululab_cli", "seedance-2-fast", "prompt", 15, reference_files=[product])
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[1][0], "upload")

    def test_provider_order(self):
        self.assertEqual(video_cli.PROVIDER_ORDER, ("lululab_cli",))

    def test_preflight_defaults_to_lululab_without_other_provider_probe(self):
        with patch.object(video_cli, "libtv_cli_available") as libtv, patch.object(
            video_cli, "_local_executable", return_value=Path("/tmp/lululab")
        ), patch.object(video_cli, "local_cli_supports_model", return_value=True) as selected:
            result = video_cli.preflight("Seedance 2 Fast")
        self.assertEqual(result["selected"], "lululab_cli")
        self.assertIsNone(result["availability"]["xiaoyunque_cli"])
        libtv.assert_not_called()
        selected.assert_called_once()

    def test_explicit_xiaoyunque_is_checked_alone(self):
        with patch.object(video_cli, "libtv_cli_available") as libtv, patch.object(
            video_cli, "local_cli_supports_model", side_effect=lambda provider, model: provider == "xiaoyunque_cli"
        ), patch.object(video_cli, "_local_executable", return_value=Path("/tmp/xiaoyunque")):
            result = video_cli.preflight("seedance-2-fast", "xiaoyunque_cli")
        self.assertEqual(result["selected"], "xiaoyunque_cli")
        self.assertIsNone(result["availability"]["dreamina_cli"])
        libtv.assert_not_called()

    def test_unavailable_lululab_never_falls_back(self):
        with patch.object(video_cli, "libtv_cli_available") as libtv, patch.object(
            video_cli, "local_cli_supports_model", return_value=False
        ) as selected:
            result = video_cli.preflight("seedance-2-fast")
        self.assertIsNone(result["selected"])
        self.assertIsNone(result["availability"]["xiaoyunque_cli"])
        libtv.assert_not_called()
        selected.assert_called_once_with("lululab_cli", "seedance-2-fast")

    def test_libtv_default_install_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = self._fake_cli(root / ".libtv", "libtv", "unused")
            with patch.object(video_cli.Path, "home", return_value=root), patch.object(
                video_cli.shutil, "which", return_value=None
            ), patch.dict(os.environ, {"LIBTV_CLI": ""}):
                self.assertEqual(video_cli.resolve_libtv_cli(), executable.resolve())

    def test_exact_model_id_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            cli = self._fake_cli(Path(directory), "dreamina", "seedance2.0fast_vip")
            with patch.dict(os.environ, {"DREAMINA_CLI": str(cli)}):
                self.assertTrue(video_cli.local_cli_supports_model("dreamina_cli", "Seedance 2 Fast"))
                self.assertFalse(video_cli.local_cli_supports_model("dreamina_cli", "Seedance 2 Mini"))

    def test_submit_repeats_all_reference_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            product, creator = root / "product.png", root / "creator.png"
            product.write_bytes(b"product")
            creator.write_bytes(b"creator")
            with patch.object(video_cli, "_local_executable", return_value=Path("/tmp/dreamina")), patch.object(
                video_cli, "_run_json", return_value={"submit_id": "task-1"}
            ) as run:
                task = video_cli.submit_local_video(
                    "dreamina_cli", "seedance-2-fast", "prompt", 10,
                    reference_files=[product, creator],
                )
        self.assertEqual(task, "task-1")
        arguments = run.call_args.args[1]
        images = [arguments[index + 1] for index, value in enumerate(arguments) if value == "--image"]
        self.assertEqual(images, [str(product.resolve()), str(creator.resolve())])


if __name__ == "__main__":
    unittest.main()
