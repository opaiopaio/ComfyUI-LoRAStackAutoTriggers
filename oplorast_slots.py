"""Shared LoRA-slot logic for the nodes in this package.

`LoRA Stack Auto Triggers` declares four slots and resolves trigger text here;
keeping it in one place means future changes cannot drift between nodes.

Slot widgets, in display order:
    lora_i            BOOLEAN   enable
    lora_name_i       combo
    model_weight_i    FLOAT
    clip_weight_i     FLOAT
    trigger_selector_i STRING   (hidden in the UI; written by the picker dialog)
    trigger_weight_i  FLOAT
    trigger_preview_i STRING    (one-line summary, written by the UI)
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import folder_paths

from oplorast_utils import (
    get_structured_tags,
    resolve_selection,
    split_segments,
    calculate_sha256,
)

SLOT_COUNT = 4


def _num(value, default=0.0):
    """Finite float, or `default`.

    A NaN weight would otherwise pass the "!= 0" enabled test (NaN != 0 is
    True) and poison the model with NaN strengths, which shows up as a grey or
    black image with no error at all.
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return float(default)
    return float(default) if (math.isnan(f) or math.isinf(f)) else f


# --------------------------------------------------------------------------- #
# INPUT_TYPES
# --------------------------------------------------------------------------- #
def add_slot_inputs(inputs: dict, slot_count: int = SLOT_COUNT) -> None:
    """Add the per-slot input definitions to `inputs["required"]` in place."""
    loras = ["None"] + folder_paths.get_filename_list("loras")
    required = inputs["required"]

    for i in range(1, slot_count + 1):
        required[f"lora_{i}"] = (
            "BOOLEAN",
            {"default": False, "tooltip": f"Enable/disable LoRA {i}"},
        )
        required[f"lora_name_{i}"] = (
            loras,
            {"tooltip": f"Select LoRA model {i}"},
        )
        required[f"model_weight_{i}"] = (
            "FLOAT",
            {
                "default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01,
                "tooltip": f"Model (U-Net) weight for LoRA {i}; 0 = no model effect",
            },
        )
        required[f"clip_weight_{i}"] = (
            "FLOAT",
            {
                "default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01,
                "tooltip": (
                    f"CLIP (text encoder) weight for LoRA {i}; "
                    "0 = no CLIP effect (model still applies)"
                ),
            },
        )
        required[f"trigger_selector_{i}"] = (
            "STRING",
            {
                "default": "",
                "tooltip": (
                    f"Trigger text for LoRA {i}. Leave empty to use the first "
                    "civitai variant. Use the \u2699 picker to choose/modify. "
                    "Free text is injected verbatim; legacy slice syntax "
                    "(0, 3, 5:8, :) still works."
                ),
            },
        )
        required[f"trigger_weight_{i}"] = (
            "FLOAT",
            {
                "default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01,
                "tooltip": (
                    f"Wraps every selected segment as (seg:weight) for LoRA {i}; "
                    "1.0 = no wrapping"
                ),
            },
        )
        required[f"trigger_preview_{i}"] = (
            "STRING",
            {
                "default": "",
                "tooltip": f"One-line summary for LoRA {i} (filled by the UI)",
            },
        )


# --------------------------------------------------------------------------- #
# Runtime helpers
# --------------------------------------------------------------------------- #
def iter_enabled_slots(kwargs: dict, slot_count: int = SLOT_COUNT) -> Iterator[Tuple[int, str, float, float]]:
    """Yield (index, name, model_weight, clip_weight) for every active slot.

    Model and CLIP weights are independent: a slot is active when the switch is
    on, a LoRA is selected, and at least one of the two weights is non-zero.
    NaN/Inf weights are treated as 0, i.e. the slot stays inactive.
    """
    for i in range(1, slot_count + 1):
        name = kwargs.get(f"lora_name_{i}")
        on = kwargs.get(f"lora_{i}") is True
        mw = _num(kwargs.get(f"model_weight_{i}"), 0.0)
        cw = _num(kwargs.get(f"clip_weight_{i}"), 0.0)

        name_ok = name is not None and name != "None"
        if on and name_ok and (mw != 0 or cw != 0):
            yield i, name, mw, cw


def trigger_segment(
    name: str,
    kwargs: dict,
    i: int,
    force_fetch: bool,
    fallback_to_filename: bool,
    model_weight: float,
) -> str:
    """Resolve what this slot contributes to LORA_PROMPT.

    Returns trigger text when available; otherwise `<lora:name:weight>` when
    fallback is enabled; otherwise an empty string (slot skipped from prompt).
    """
    stem = Path(name).stem
    sel = kwargs.get(f"trigger_selector_{i}", "")
    tw = _num(kwargs.get(f"trigger_weight_{i}"), 1.0)

    st = get_structured_tags(name, force_fetch)
    resolved = resolve_selection(sel, st["variants"], st["meta"])

    if resolved:
        if tw != 1.0:
            parts = split_segments(resolved)
            return ", ".join(f"({p}:{tw})" for p in parts)
        return resolved.strip()
    if fallback_to_filename:
        return f"<lora:{stem}:{model_weight:.3f}>"
    return ""


def metadata_segment(name: str, save_hash: bool) -> str:
    stem = Path(name).stem
    if not save_hash:
        return stem
    path = folder_paths.get_full_path("loras", name)
    sha = calculate_sha256(path) if path else None
    return f"{stem}: [{sha[:12]}]" if sha else stem


def build_prompt(segments: List[str], lora_prompt: Optional[str]) -> str:
    if lora_prompt and segments:
        return f"{lora_prompt}," + ",".join(segments)
    if segments:
        return ",".join(segments)
    return lora_prompt or ""


def build_metadata(segments: List[str], lora_metadata: Optional[str]) -> str:
    if lora_metadata and segments:
        return f"{lora_metadata}, " + ", ".join(segments)
    if segments:
        return ", ".join(segments)
    return lora_metadata or ""
