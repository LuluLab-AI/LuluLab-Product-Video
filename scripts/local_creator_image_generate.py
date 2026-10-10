#!/usr/bin/env python3
"""Generate one grounded 9:16 creator reference through LuluLab ImageGenV2."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import video_cli
from local_video_generate import download
from core.user_errors import failure


class CreatorImageError(RuntimeError):
    pass


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def output_image_url(task: Any) -> str:
    source = video_cli._unwrap(task)
    output = source.get("output") if isinstance(source, dict) else None
    image = output.get("image") if isinstance(output, dict) else None
    url = image.get("url") if isinstance(image, dict) else None
    if not video_cli._http_url(url):
        raise CreatorImageError("图片任务成功响应缺少 output.image.url。")
    return str(url)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--reference-image", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--resume-task-id")
    parser.add_argument("--image-model", choices=sorted(video_cli.LULULAB_IMAGE_MODEL_IDS),
                        default=video_cli.LULULAB_IMAGE_MODEL_ID)
    args = parser.parse_args()
    try:
        prompt = args.prompt_file.expanduser().resolve().read_text(encoding="utf-8").strip()
        if not prompt:
            raise CreatorImageError("达人图 Prompt 不能为空。")
        references = video_cli._reference_files(args.reference_image, 9)
        if not references:
            raise CreatorImageError("必须传入产品参考图。")
        output = args.output.expanduser().resolve()
        if output.suffix.lower() != ".png":
            raise CreatorImageError("达人图输出路径必须为 .png。")
        report = args.report.expanduser().resolve()
        digest = hashlib.sha256(prompt.encode()).hexdigest()
        state = json.loads(report.read_text()) if report.is_file() else {}
        if state and (state.get("promptSha256") != digest or state.get("referenceFiles") != list(map(str, references))
                      or state.get("output") != str(output) or state.get("model") != args.image_model):
            raise CreatorImageError("已有图片任务与当前 Prompt、参考图或输出路径不一致。")
        task_id = str(state.get("taskId") or "")
        if args.resume_task_id and not state:
            raise CreatorImageError("恢复图片任务需要已有 report 文件以核对原任务。")
        if args.resume_task_id and task_id and args.resume_task_id != task_id:
            raise CreatorImageError("恢复 task ID 与记录不一致。")
        task_id = task_id or str(args.resume_task_id or "")
        if task_id and state.get("taskId") != task_id:
            state.update(status="submitted", taskId=task_id)
            atomic_write(report, state)
        if state.get("status") == "succeeded" and output.is_file():
            print(json.dumps(state, ensure_ascii=False))
            return 0
        if not task_id and state.get("status") in {"submit_started_uncertain", "submitted", "succeeded"}:
            raise CreatorImageError("提交结果不确定且无 task ID，禁止自动重提。")
        if not task_id:
            balance = video_cli.get_lululab_credit_balance()
            if balance <= 0:
                raise CreatorImageError("LuluLab 积分不足，未提交图片任务。")
            uploaded = video_cli.upload_lululab_image_references(references)
            state = {"status": "submit_started_uncertain", "taskId": "", "provider": "lululab_cli",
                     "model": args.image_model, "promptSha256": digest,
                     "referenceFiles": list(map(str, references)), "output": str(output)}
            atomic_write(report, state)
            task_id = video_cli.submit_lululab_image(prompt, uploaded_references=uploaded,
                                                     model=args.image_model)
            state.update(status="submitted", taskId=task_id)
            atomic_write(report, state)
        try:
            result = video_cli.poll_local_video("lululab_cli", task_id)
        except video_cli.VideoCliError as exc:
            try:
                final_task = video_cli.fetch_lululab_image(task_id)
            except video_cli.VideoCliError:
                raise
            if video_cli._walk_status(final_task) not in video_cli.FAILED_STATES:
                raise exc
            try:
                source = video_cli._unwrap(final_task)
                detail = source.get("errorMessage") if isinstance(source, dict) else None
                if isinstance(detail, str) and detail.strip():
                    raise CreatorImageError(f"{exc}：{detail.strip()[:300]}") from None
            except video_cli.VideoCliError:
                pass
            raise
        image_url = output_image_url(result)
        download(image_url, output)
        with output.open("rb") as stream:
            png_signature = stream.read(8)
        if png_signature != b"\x89PNG\r\n\x1a\n":
            output.unlink(missing_ok=True)
            raise CreatorImageError("图片任务返回的文件不是 PNG。")
        state.update(status="succeeded")
        atomic_write(report, state)
        print(json.dumps(state, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError, video_cli.VideoCliError, CreatorImageError) as exc:
        failure(exc, "IMAGE_GENERATION_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
