#!/usr/bin/env python3
"""Preflight and drive the selected video CLI without provider fallback."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import time
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.user_errors import failure


PROVIDER_ORDER = ("lululab_cli",)
SUPPORTED_PROVIDERS = ("lululab_cli", "dreamina_cli", "libtv_cli", "xiaoyunque_cli")
LOCAL_PROVIDERS = {"lululab_cli", "xiaoyunque_cli", "dreamina_cli"}
LOGICAL_MODELS = {
    "seedance 2 fast": "seedance-2-fast",
    "seedance 2 mini": "seedance-2-mini",
    "seedance 2": "seedance-2",
    "seedance 2 5": "seedance-2-5",
}
PROVIDER_MODEL_IDS = {
    "seedance-2-fast": "seedance2.0fast_vip",
    "seedance-2-mini": "seedance2.0mini_vip",
    "seedance-2": "seedance2.0_vip",
    "seedance-2-5": "seedance2.5",
}
LULULAB_VIDEO_WORKFLOW_ID = "VideoGenV2"
LULULAB_IMAGE_WORKFLOW_ID = "ImageGenV2"
LULULAB_IMAGE_MODEL_ID = "gpt-image-2-5-sunburst"
LULULAB_IMAGE_MODEL_IDS = {LULULAB_IMAGE_MODEL_ID, "gpt-image-2-5-flare"}
LULULAB_MODEL_IDS = {"seedance-2-fast", "seedance-2-mini", "seedance-2", "seedance-2-5"}
LIBTV_MODEL_NAMES = {
    "seedance-2-fast": "Seedance 2.0 Fast VIP",
    "seedance-2-mini": "Seedance 2.0 Mini",
    "seedance-2": "Seedance 2.0 VIP",
    "seedance-2-5": "Seedance 2.5",
}
PENDING_STATES = {
    "created", "pending", "processing", "running", "queued", "querying", "submitted", "generating",
}
SUCCESS_STATES = {"succeeded", "success", "completed", "complete"}
FAILED_STATES = {"failed", "failure", "fail", "error", "cancelled", "canceled"}


class VideoCliError(RuntimeError):
    pass


def normalize_model(model: str) -> str:
    normalized = " ".join(
        str(model).lower().replace("_", " ").replace("-", " ").replace(".", " ").split()
    )
    value = LOGICAL_MODELS.get(normalized, str(model).strip().lower())
    if value not in PROVIDER_MODEL_IDS:
        raise VideoCliError(f"不支持的视频模型：{model}")
    return value


def provider_model_id(model: str) -> str:
    return PROVIDER_MODEL_IDS[normalize_model(model)]


def libtv_model_name(model: str) -> str:
    return LIBTV_MODEL_NAMES[normalize_model(model)]


def validate_duration(model: str, duration: int | float | str) -> int:
    model_id = normalize_model(model)
    try:
        value = int(float(str(duration)))
    except (TypeError, ValueError):
        raise VideoCliError("视频时长必须是整数。") from None
    maximum = 30 if model_id == "seedance-2-5" else 15
    if value < 4 or value > maximum:
        raise VideoCliError(f"模型 {model_id} 的单段时长必须是 4-{maximum} 秒。")
    return value


def _resolve_executable(
    names: Sequence[str], *, configured: str = "", cli_path: str | os.PathLike[str] | None = None
) -> Path:
    if cli_path is not None:
        candidate = Path(cli_path).expanduser().resolve()
    else:
        discovered = configured or next((path for name in names if (path := shutil.which(name))), "")
        candidate = Path(discovered).expanduser().resolve() if discovered else Path.home() / ".local" / "bin" / names[0]
    if not candidate.is_file() or candidate.stat().st_size <= 0:
        raise VideoCliError(f"未发现可执行 CLI：{names[0]}")
    if platform.system() != "Windows" and not os.access(candidate, os.X_OK):
        raise VideoCliError(f"CLI 不可执行：{candidate}")
    return candidate.resolve()


def resolve_libtv_cli(*, cli_path: str | os.PathLike[str] | None = None) -> Path:
    names = ("libtv.exe", "libtv") if platform.system() == "Windows" else ("libtv",)
    configured = os.environ.get("LIBTV_CLI", "").strip()
    discovered = configured or next((path for name in names if (path := shutil.which(name))), "")
    if cli_path is None and not discovered:
        official = Path.home() / ".libtv" / ("libtv.exe" if platform.system() == "Windows" else "libtv")
        if official.is_file():
            cli_path = official
    return _resolve_executable(names, configured=configured, cli_path=cli_path)


def resolve_xiaoyunque_cli(*, cli_path: str | os.PathLike[str] | None = None) -> Path:
    names = (
        ("xiaoyunque.exe", "xiao-yunque.exe", "xiaoyunque-cli.exe")
        if platform.system() == "Windows"
        else ("xiaoyunque", "xiao-yunque", "xiaoyunque-cli")
    )
    return _resolve_executable(
        names, configured=os.environ.get("XIAOYUNQUE_CLI", "").strip(), cli_path=cli_path
    )


def resolve_dreamina_cli(*, cli_path: str | os.PathLike[str] | None = None) -> Path:
    names = ("dreamina.exe", "dreamina") if platform.system() == "Windows" else ("dreamina",)
    return _resolve_executable(
        names, configured=os.environ.get("DREAMINA_CLI", "").strip(), cli_path=cli_path
    )


def resolve_lululab_cli(*, cli_path: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the portable Node.js entrypoint, never the retired native CLI."""
    candidate = Path(cli_path or os.environ.get("LULULAB_CLI", "").strip() or
                     Path(__file__).with_name("lululab_cli.mjs")).expanduser().resolve()
    if not candidate.is_file() or candidate.suffix != ".mjs":
        raise VideoCliError("LuluLab CLI 必须是 Node.js .mjs 入口；请更新 LULULAB_CLI 或取消旧路径覆盖。")
    resolve_node()
    return candidate


def resolve_node() -> Path:
    names = ("node.exe", "node") if platform.system() == "Windows" else ("node",)
    return _resolve_executable(names, configured=os.environ.get("LULULAB_NODE", "").strip())


def resolve_lululab_api_key() -> str:
    for name in ("LULULAB_API_KEY", "LINGZHI_API_KEY", "LZSTUDIO_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    config = Path.home() / ".ugc-product-video" / "config.json"
    if config.is_file():
        try:
            value = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VideoCliError(f"无法读取LuluLab凭证配置：{exc}") from None
        key = value.get("apiKey") if isinstance(value, dict) else None
        if isinstance(key, str) and key.strip():
            return key.strip()
    raise VideoCliError(
        "缺少LuluLab API Key；请设置 LULULAB_API_KEY，"
        "或使用现有 ~/.ugc-product-video/config.json 凭证配置。"
    )


def _run_process(executable: Path, arguments: Sequence[str], *, timeout: float = 600.0) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ([str(resolve_node()), str(executable)] if executable.suffix == ".mjs" else [str(executable)]) + list(map(str, arguments)),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        raise VideoCliError(f"CLI 调用超时（{timeout:g} 秒）。") from None
    except OSError as exc:
        raise VideoCliError(f"无法启动 CLI：{exc}") from None


def _parse_json(raw: str, provider: str) -> Any:
    text = raw.strip()
    if not text:
        raise VideoCliError(f"{provider} CLI 返回空响应。")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            try:
                return json.loads(line.strip())
            except json.JSONDecodeError:
                continue
    raise VideoCliError(f"{provider} CLI 返回内容不是有效 JSON。")


def _run_json(executable: Path, arguments: Sequence[str], *, provider: str, timeout: float = 600.0) -> Any:
    completed = _run_process(executable, arguments, timeout=timeout)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "未知错误"
        if "login" in detail.lower() or "unauthor" in detail.lower():
            raise VideoCliError(f"{provider} CLI 尚未登录：{detail[:1000]}")
        raise VideoCliError(f"{provider} CLI 退出码 {completed.returncode}：{detail[:1000]}")
    return _parse_json(completed.stdout, provider)


def libtv_cli_available(*, cli_path: str | os.PathLike[str] | None = None) -> bool:
    try:
        executable = resolve_libtv_cli(cli_path=cli_path)
        return _run_process(executable, ["--help"], timeout=30).returncode == 0
    except (VideoCliError, OSError, subprocess.SubprocessError):
        return False


def _local_executable(provider: str) -> Path:
    if provider == "lululab_cli":
        return resolve_lululab_cli()
    if provider == "xiaoyunque_cli":
        return resolve_xiaoyunque_cli()
    if provider == "dreamina_cli":
        return resolve_dreamina_cli()
    raise VideoCliError(f"未知本地视频渠道：{provider}")


def local_cli_supports_model(provider: str, model: str) -> bool:
    if provider == "lululab_cli":
        try:
            executable = _local_executable(provider)
            submit_help = _run_process(executable, ["task", "submit", "--help"], timeout=30)
            fetch_help = _run_process(executable, ["task", "fetch", "--help"], timeout=30)
        except (VideoCliError, OSError, subprocess.SubprocessError):
            return False
        submit_text = f"{submit_help.stdout}\n{submit_help.stderr}"
        fetch_text = f"{fetch_help.stdout}\n{fetch_help.stderr}"
        required = ("--workflow-id", "--input")
        return (
            normalize_model(model) in LULULAB_MODEL_IDS
            and submit_help.returncode == 0
            and fetch_help.returncode == 0
            and all(token in submit_text for token in required)
            and "--id" in fetch_text
        )
    try:
        executable = _local_executable(provider)
        submit_help = _run_process(executable, ["multimodal2video", "--help"], timeout=30)
        query_help = _run_process(executable, ["query_result", "--help"], timeout=30)
    except (VideoCliError, OSError, subprocess.SubprocessError):
        return False
    submit_text = f"{submit_help.stdout}\n{submit_help.stderr}"
    query_text = f"{query_help.stdout}\n{query_help.stderr}"
    required = ("--image", "--prompt", "--duration", "--ratio", "--video_resolution", "--model_version")
    return (
        submit_help.returncode == 0
        and query_help.returncode == 0
        and provider_model_id(model) in submit_text
        and all(token in submit_text for token in required)
        and "--submit_id" in query_text
    )


def preflight(model: str, provider: str = "lululab_cli") -> dict[str, Any]:
    """Check only the authorized provider; never switch channels implicitly."""
    normalized = normalize_model(model)
    if provider not in SUPPORTED_PROVIDERS:
        raise VideoCliError(f"不支持的视频渠道：{provider}")
    available = libtv_cli_available() if provider == "libtv_cli" else local_cli_supports_model(provider, normalized)
    executable = (resolve_libtv_cli() if provider == "libtv_cli" else _local_executable(provider)) if available else None
    return {
        "priority": [provider],
        "selected": provider if available else None,
        "availability": {name: available if name == provider else None for name in SUPPORTED_PROVIDERS},
        "executable": str(executable) if executable else "",
        "model": normalized,
        "lowerPriorityChecksSkipped": True,
    }


def _reference_files(values: Iterable[str | os.PathLike[str]] | None, maximum: int) -> list[Path]:
    result: list[Path] = []
    for value in values or []:
        path = Path(value).expanduser().resolve()
        if not path.is_file() or path.stat().st_size <= 0:
            raise VideoCliError(f"参考文件不存在或为空：{path}")
        if path not in result:
            result.append(path)
    if len(result) > maximum:
        raise VideoCliError(f"参考图数量超过模型上限 {maximum}。")
    return result


def _unwrap(value: Any) -> Any:
    while isinstance(value, dict):
        nested = next((value[key] for key in ("data", "result") if isinstance(value.get(key), dict)), None)
        if nested is None:
            break
        value = nested
    return value

def _output(value: Any) -> Any:
    source = _unwrap(value)
    if isinstance(source, dict) and isinstance(source.get("output"), dict):
        return source["output"]
    return source

def _http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

def media(value: Any, default_mime: str = "video/mp4") -> dict[str, Any]:
    source = _output(value)
    if isinstance(source, dict):
        for key in ("video", "image", "media"):
            if isinstance(source.get(key), (dict, str)):
                source = source[key]
                break
    if isinstance(source, str):
        source = {"url": source}
    if not isinstance(source, dict):
        raise VideoCliError("fetch 响应缺少媒体结果。")
    url = (
        source.get("url") or source.get("downloadUrl") or source.get("outputUrl")
        or source.get("video_url") or source.get("media_url") or source.get("result_url")
    )
    if not url:
        urls = source.get("urls") or source.get("resultUrls")
        if isinstance(urls, list) and urls:
            url = urls[0]
    if not _http_url(url):
        queue = [_output(value)]
        while queue and not _http_url(url):
            current = queue.pop(0)
            if isinstance(current, dict):
                for key, item in current.items():
                    if key in {"url", "downloadUrl", "outputUrl", "video_url", "media_url", "result_url"} and _http_url(item):
                        source, url = current, item
                        break
                    if isinstance(item, (dict, list)):
                        queue.append(item)
            elif isinstance(current, list):
                queue.extend(item for item in current if isinstance(item, (dict, list)))
    if not _http_url(url):
        raise VideoCliError("fetch 响应缺少有效媒体 URL。")
    return {"url": str(url).strip(), "mimeType": source.get("mimeType") or default_mime, "expiredAt": source.get("expiredAt") or source.get("expiresAt") or ""}

def _task_id(value: Any) -> str:
    source = _unwrap(value)
    if not isinstance(source, dict):
        raise VideoCliError("submit 响应必须是 JSON 对象。")
    identifier = source.get("id", source.get("taskId", source.get("submit_id")))
    if isinstance(identifier, bool) or not isinstance(identifier, (str, int)) or not str(identifier).strip():
        raise VideoCliError("submit 响应缺少 id。")
    return str(identifier).strip()


def submit_local_video(
    provider: str,
    model: str,
    prompt: str,
    duration: int | float | str,
    *,
    reference_files: Iterable[str | os.PathLike[str]] | None = None,
    aspect_ratio: str = "9:16",
    resolution: str = "720p",
) -> str:
    if provider not in LOCAL_PROVIDERS:
        raise VideoCliError(f"本函数不支持渠道：{provider}")
    if not isinstance(prompt, str) or not prompt.strip():
        raise VideoCliError("视频 Prompt 不能为空。")
    model_id = normalize_model(model)
    duration_value = validate_duration(model_id, duration)
    maximum = 30 if model_id == "seedance-2-5" else 9
    files = _reference_files(reference_files, maximum)
    if provider == "lululab_cli":
        if not local_cli_supports_model(provider, model_id):
            raise VideoCliError("LuluLab CLI 未通过 task submit/fetch 能力检查，未提交计费任务。")
        executable = _local_executable(provider)
        references = [media(_run_json(executable, ["upload", str(path)], provider=provider),
                            "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png")
                      for path in files]
        payload = {"model": model_id, "prompt": prompt.strip(), "duration": duration_value,
                   "aspectRatio": aspect_ratio, "resolution": resolution, "referenceImages": references}
        workflow = os.environ.get("LULULAB_VIDEO_WORKFLOW_ID", "").strip() or LULULAB_VIDEO_WORKFLOW_ID
        arguments = ["task", "submit", "--workflow-id", workflow,
                     "--input", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))]
        return _task_id(_run_json(executable, arguments, provider=provider))
    command = "multimodal2video" if files else "text2video"
    arguments = [
        command,
        "--prompt", prompt.strip(),
        "--duration", str(duration_value),
        "--ratio", aspect_ratio,
        "--video_resolution", resolution,
        "--model_version", provider_model_id(model_id),
    ]
    for path in files:
        arguments.extend(("--image", str(path)))
    value = _run_json(_local_executable(provider), arguments, provider=provider)
    return _task_id(value)


def upload_lululab_image_references(
    reference_files: Iterable[str | os.PathLike[str]],
) -> list[dict[str, str]]:
    """Upload product images before recording an uncertain billable submission."""
    files = _reference_files(reference_files, 9)
    if not files:
        raise VideoCliError("达人图生成需要至少一张产品参考图。")
    executable = resolve_lululab_cli()
    references = [media(_run_json(executable, ["upload", str(path)], provider="lululab_cli"),
                        "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png")
                  for path in files]
    return [{"url": item["url"], "mimeType": item["mimeType"]} for item in references]


def submit_lululab_image(
    prompt: str,
    *,
    reference_files: Iterable[str | os.PathLike[str]] | None = None,
    uploaded_references: list[dict[str, str]] | None = None,
    aspect_ratio: str = "9:16",
    model: str = LULULAB_IMAGE_MODEL_ID,
) -> str:
    """Submit a single ImageGenV2 task with product references."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise VideoCliError("图片 Prompt 不能为空。")
    if aspect_ratio != "9:16":
        raise VideoCliError("达人参考图必须使用 9:16。")
    if model not in LULULAB_IMAGE_MODEL_IDS:
        raise VideoCliError(f"不支持的图片模型：{model}")
    executable = resolve_lululab_cli()
    submit_help = _run_process(executable, ["task", "submit", "--help"], timeout=30)
    fetch_help = _run_process(executable, ["task", "fetch", "--help"], timeout=30)
    if (submit_help.returncode != 0 or fetch_help.returncode != 0
        or not all(flag in submit_help.stdout + submit_help.stderr for flag in ("--workflow-id", "--input"))
        or "--id" not in fetch_help.stdout + fetch_help.stderr):
        raise VideoCliError("LuluLab CLI 未通过图片 task submit/fetch 能力检查。")
    if uploaded_references is None:
        references = upload_lululab_image_references(reference_files or [])
    else:
        references = uploaded_references
    if not references or any(not video_ref.get("url") or not video_ref.get("mimeType") for video_ref in references):
        raise VideoCliError("图片任务需要有效产品参考媒体。")
    payload = {"model": model, "prompt": prompt.strip(),
               "resolution": "1K", "aspectRatio": aspect_ratio, "referenceImages": references}
    workflow = os.environ.get("LULULAB_IMAGE_WORKFLOW_ID", "").strip() or LULULAB_IMAGE_WORKFLOW_ID
    arguments = ["task", "submit", "--workflow-id", workflow,
                 "--input", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))]
    return _task_id(_run_json(executable, arguments, provider="lululab_cli"))


def fetch_lululab_image(task_id: str) -> Any:
    return fetch_local_video("lululab_cli", task_id)


def fetch_local_video(provider: str, task_id: str) -> Any:
    if provider not in LOCAL_PROVIDERS:
        raise VideoCliError(f"未知本地视频渠道：{provider}")
    if not str(task_id).strip():
        raise VideoCliError("任务 ID 不能为空。")
    if provider == "lululab_cli":
        return _run_json(
            _local_executable(provider),
            ["task", "fetch", "--id", str(task_id).strip()],
            provider=provider,
            timeout=300,
        )
    return _run_json(
        _local_executable(provider),
        ["query_result", "--submit_id", str(task_id).strip()],
        provider=provider,
        timeout=300,
    )


def get_lululab_credit_balance() -> int | float:
    value = _run_json(
        resolve_lululab_cli(),
        ["user", "--credits"],
        provider="lululab_cli",
        timeout=300,
    )
    queue = [value]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            balance = current.get("balance")
            if isinstance(balance, (int, float)) and not isinstance(balance, bool):
                return balance
            queue.extend(item for item in current.values() if isinstance(item, (dict, list)))
        elif isinstance(current, list):
            queue.extend(item for item in current if isinstance(item, (dict, list)))
    raise VideoCliError("LuluLab积分响应缺少有效 balance。")


def _walk_status(value: Any) -> str:
    queue = [value]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            state = current.get("gen_status") or current.get("status") or current.get("state") or current.get("task_status")
            if isinstance(state, str) and state.strip():
                return state.strip().lower()
            queue.extend(item for item in current.values() if isinstance(item, (dict, list)))
        elif isinstance(current, list):
            queue.extend(item for item in current if isinstance(item, (dict, list)))
    return ""


def poll_local_video(
    provider: str,
    task_id: str,
    *,
    interval: float = 5.0,
    timeout: float = 3600.0,
    sleep: Callable[[float], None] = time.sleep,
    on_status: Callable[[str, Any], None] | None = None,
) -> Any:
    deadline = time.monotonic() + timeout
    while True:
        value = fetch_local_video(provider, task_id)
        state = _walk_status(value)
        if on_status is not None:
            on_status(state, value)
        if state in SUCCESS_STATES:
            return value
        if state in FAILED_STATES:
            raise VideoCliError(f"任务 {task_id} 失败：{state}")
        if state not in PENDING_STATES:
            raise VideoCliError(f"任务 {task_id} 返回未知状态：{state or '缺失'}")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise VideoCliError(f"任务 {task_id} 轮询超时。")
        sleep(min(interval, remaining))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("preflight")
    command.add_argument("--model", required=True)
    command.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="lululab_cli")
    args = parser.parse_args()
    if args.command == "preflight":
        try:
            print(json.dumps(preflight(args.model, args.provider), ensure_ascii=False))
        except VideoCliError as exc:
            failure(exc, "PREFLIGHT_FAILED")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
