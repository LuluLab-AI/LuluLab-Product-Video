"""Exact model names and segment limits for the attachment's four-model flow."""
from __future__ import annotations

MODEL_CATALOG = {
    "seedance-2-fast": {"name": "Seedance 2.0 Fast", "duration_spec": (4, 15)},
    "seedance-2-mini": {"name": "Seedance 2.0 Mini", "duration_spec": (4, 15)},
    "seedance-2": {"name": "Seedance 2.0", "duration_spec": (4, 15)},
    "seedance-2-5": {"name": "Seedance 2.5", "duration_spec": (4, 30)},
}
DEFAULT_MODEL = "seedance-2-fast"


def display_name(model_id: str) -> str:
    try:
        return MODEL_CATALOG[model_id]["name"]
    except KeyError:
        raise ValueError(f"Unsupported video model: {model_id}") from None


def model_id_for(value: str) -> str:
    if value in MODEL_CATALOG:
        return value
    for model_id, data in MODEL_CATALOG.items():
        if data["name"] == value:
            return model_id
    raise ValueError(f"Unsupported video model: {value}")


def validate_durations(model_id: str, durations: list[int], target: int,
                       runtime_supported_durations: list[int] | None = None) -> None:
    if model_id not in MODEL_CATALOG:
        raise ValueError(f"Unsupported video model: {model_id}")
    if not durations or any(isinstance(d, bool) or not isinstance(d, int) for d in durations):
        raise ValueError("Every segment must use an integer duration")
    minimum, maximum = MODEL_CATALOG[model_id]["duration_spec"]
    if any(not minimum <= d <= maximum for d in durations):
        raise ValueError(f"Segment duration out of bounds for {model_id}")
    if runtime_supported_durations is not None and any(d not in runtime_supported_durations for d in durations):
        raise ValueError("Duration not supported by runtime provider schema")
    if sum(durations) != target:
        raise ValueError("Segment total duration mismatch")
