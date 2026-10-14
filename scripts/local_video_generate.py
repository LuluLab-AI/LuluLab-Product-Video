#!/usr/bin/env python3
"""Run approved segments through one locked CLI provider without fallback."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent))
import video_cli  # noqa: E402
from core.user_errors import failure


class LocalGenerationError(RuntimeError):
    pass


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_job(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("segments"), list) or not value["segments"]:
        raise LocalGenerationError("任务 JSON 必须包含非空 segments 数组。")
    return value


def load_state(path: Path, provider: str) -> dict[str, Any]:
    if not path.is_file():
        return {"schemaVersion": "1.0", "provider": provider, "segments": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LocalGenerationError("视频生成状态文件必须是 JSON 对象。")
    previous = str(value.get("provider", "")).strip()
    if previous == "lingzhi_cli":
        previous = "lululab_cli"  # Brand rename: resume the original task without resubmission.
    if previous and previous != provider:
        raise LocalGenerationError(f"任务已锁定 provider={previous}，禁止切换到 {provider}。")
    value.setdefault("segments", {})
    return value


def _http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def media_url(value: Any) -> str:
    # The API task includes input reference URLs; download only its output.
    queue = [value["output"] if isinstance(value, dict) and "output" in value else value]
    url_keys = {"url", "downloadUrl", "outputUrl", "video_url", "media_url", "result_url"}
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            for key, item in current.items():
                if key in url_keys and _http_url(item):
                    return str(item).strip()
                if isinstance(item, (dict, list)):
                    queue.append(item)
        elif isinstance(current, list):
            queue.extend(item for item in current if isinstance(item, (dict, list)))
    raise LocalGenerationError("任务成功响应缺少有效视频 URL。")


def download(url: str, output: Path, *, timeout: float = 600.0) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    request = Request(url, headers={"User-Agent": "ugc-product-video/1.0", "Accept": "*/*"})
    try:
        with urlopen(request, timeout=timeout) as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        if temporary.stat().st_size <= 0:
            raise LocalGenerationError("下载的视频文件为空。")
        temporary.replace(output)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, LocalGenerationError):
            raise
        raise LocalGenerationError(f"下载视频失败：{exc}") from None
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--provider", choices=sorted(video_cli.LOCAL_PROVIDERS), required=True)
    parser.add_argument("--generation-approved", action="store_true")
    args = parser.parse_args()
    try:
        if not args.generation_approved:
            raise LocalGenerationError("首次视频生成必须处于用户确认授权内；请传入 --generation-approved。")
        job_path = Path(args.job).expanduser().resolve()
        root = job_path.parent
        data = load_job(job_path)
        from quality_gate import validate_job
        validate_job(data)  # Before provider checks, uploads or billable submission.
        model = str(data.get("videoModel", video_cli.DEFAULT_MODEL))
        if not video_cli.local_cli_supports_model(args.provider, model):
            raise LocalGenerationError(f"{args.provider} 未通过当前模型的精确 CLI 能力检查。")
        state_path = root / "local-video-generation.json"
        state = load_state(state_path, args.provider)
        state.update({"provider": args.provider, "model": video_cli.normalize_model(model)})
        segments = state["segments"]
        output_dir = root / "segments"
        needs_submission = any(
            not str((segments.get(str(int(segment["segmentId"]))) or {}).get("taskId", "")).strip()
            and (segments.get(str(int(segment["segmentId"]))) or {}).get("status") != "succeeded"
            for segment in data["segments"]
        )
        for segment in data["segments"]:
            segment_id = int(segment["segmentId"])
            key = str(segment_id)
            record = segments.get(key) if isinstance(segments.get(key), dict) else {}
            if record.get("status") == "succeeded" and Path(str(record.get("localFile", ""))).is_file():
                continue
            if record.get("status") == "submit_started_uncertain":
                raise LocalGenerationError(f"Segment {segment_id} 提交状态不确定；为避免重复计费，禁止自动重提。")
            task_id = str(record.get("taskId", "")).strip()
            if not task_id:
                if args.provider == 'lululab_cli':
                    balance = video_cli.get_lululab_credit_balance()
                    if balance <= 0:
                        record['status'] = 'credits_required'
                        segments[key] = record
                        atomic_write_json(state_path, state)
                        raise video_cli.CreditsInsufficient(video_cli.CREDITS_MESSAGE)
                references = [str(Path(str(item)).expanduser().resolve()) for item in segment.get("referenceFiles", [])]
                record.update({"status": "submit_started_uncertain", "referenceFiles": references})
                segments[key] = record
                atomic_write_json(state_path, state)
                try:
                    task_id = video_cli.submit_local_video(
                        args.provider, model, str(segment['prompt']), segment['duration'],
                        reference_files=references,
                        aspect_ratio=str(data.get('aspectRatio', '9:16')),
                        resolution=str(data.get('resolution', '720p')),
                    )
                except video_cli.CreditsInsufficient:
                    record['status'] = 'credits_required'
                    atomic_write_json(state_path, state)
                    raise
                record.update({"taskId": task_id, "status": "submitted"})
                atomic_write_json(state_path, state)
            record["status"] = "querying"
            atomic_write_json(state_path, state)
            def on_status(remote_status: str, response: Any) -> None:
                source = video_cli._unwrap(response)
                started_at = source.get("startedAt") if isinstance(source, dict) else None
                if remote_status != record.get("remoteStatus") or started_at != record.get("startedAt"):
                    record.update(remoteStatus=remote_status, startedAt=started_at,
                                  lastCheckedAt=datetime.now(timezone.utc).isoformat())
                    atomic_write_json(state_path, state)
                    print(json.dumps({"segmentId": segment_id, "taskId": task_id,
                                      "remoteStatus": remote_status, "startedAt": started_at},
                                     ensure_ascii=False), flush=True)
            try:
                result = video_cli.poll_local_video(args.provider, task_id, on_status=on_status)
            except video_cli.VideoCliError as exc:
                if record.get("remoteStatus") in video_cli.FAILED_STATES:
                    record.update(status="terminal_failed", error=str(exc)[:300])
                    atomic_write_json(state_path, state)
                raise
            url = media_url(result)
            local_file = download(url, output_dir / f"segment_{segment_id:02d}.mp4")
            record.update({"status": "succeeded", "remoteUrl": url, "localFile": str(local_file)})
            atomic_write_json(state_path, state)
        final_video = root / "final_video.mp4"
        files = [Path(segments[str(int(item["segmentId"]))]["localFile"]) for item in data["segments"]]
        if len(files) == 1:
            shutil.copy2(files[0], final_video)
        else:
            command = [sys.executable, str(SCRIPT_DIR / "merge_video.py"), "--inputs",
                       *map(str, files), "--output", str(final_video)]
            merged = subprocess.run(command, capture_output=True, text=True, check=False)
            if merged.returncode != 0 or not final_video.is_file():
                raise LocalGenerationError(f"视频拼接失败：{merged.stderr[-500:]}")
        state["finalVideo"] = str(final_video)
        state["status"] = "segments_completed"
        state["qualityStatus"] = "needs_review"
        state["qualityNote"] = "RENDER_REVIEW_REQUIRED"
        if args.provider == "lululab_cli":
            try:
                state["creditsAfter"] = video_cli.get_lululab_credit_balance()
            except video_cli.VideoCliError as exc:
                state["creditsAfterError"] = str(exc)[:300]
        atomic_write_json(state_path, state)
        print(json.dumps({
            "ok": True,
            "provider": args.provider,
            "creditsBefore": state.get("creditsBefore"),
            "creditsAfter": state.get("creditsAfter"),
            "segments": [segments[key] for key in sorted(segments, key=int)],
            "finalVideo": str(final_video),
            "state": str(state_path),
        }, ensure_ascii=False))
        return 0
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, LocalGenerationError, video_cli.VideoCliError) as exc:
        failure(exc, "VIDEO_GENERATION_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
