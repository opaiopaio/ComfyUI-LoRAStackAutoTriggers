"""Stack appliers for this node pack.

Why this file exists:

1. This pack used to only BUILD a LORA_STACK, so anyone without a third-party
   "apply LoRA stack" node could not use it at all. `LoRAStackApplyBasic` is the
   plain applier for that.
2. The Anima cross-generation remap has to happen at one specific moment: after
   the LoRA file is loaded, before its deltas are folded into the model by
   comfy.sd.load_lora_for_models. A node placed *after* an applier cannot fix
   anything. `LoRAStackApply` (Anima Remap) is the applier that does the remap.

Socket order note: both nodes declare `model` as required and `clip`/`lora_stack`
as optional in that order, so the canvas shows model -> clip -> lora_stack.
(ComfyUI always draws required inputs before optional ones, so `lora_stack`
cannot sit between them unless it is optional too.)
"""

from __future__ import annotations

import math
from pathlib import Path

import folder_paths
import comfy.sd
import comfy.utils

from anima_arch import (
    AUTO_LABEL,
    MODEL_CHOICES,
    describe_count,
    get_mapping,
    resolve_dropdown,
)
from anima_remap import (
    detect_lora_block_count,
    detect_model_block_count,
    extend_state_dict,
    remap_state_dict,
)
from i18n import t

REMAP_MODE_KEYS = "Keys only (recommended)"
REMAP_MODE_EXTEND = "Extend to new layers (experimental)"
REMAP_MODES = [REMAP_MODE_KEYS, REMAP_MODE_EXTEND]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _num(value, default=0.0):
    """Coerce to a finite float. NaN/Inf (which a widget can hold after a
    paste/clone) become `default` -- a NaN strength silently poisons the model
    and shows up as a grey/black image with no error."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return float(default)
    return float(default) if (math.isnan(f) or math.isinf(f)) else f


def _unpack_entry(entry):
    """LORA_STACK entry -> (name, w_model, w_clip), or None to skip.

    A missing weight means "1.0"; a present-but-NaN/Inf weight means "garbage"
    and becomes 0 so the entry is skipped instead of poisoning the model.
    """
    if not isinstance(entry, (list, tuple)) or not entry:
        return None
    name = entry[0]
    if not isinstance(name, str) or not name or name == "None":
        return None
    w_model = _num(entry[1], 0.0) if len(entry) > 1 else 1.0
    w_clip = _num(entry[2], 0.0) if len(entry) > 2 else w_model
    return name, w_model, w_clip


def _load_and_remap(name, target_count, enable_remap, source_choice, remap_mode, extend_strength):
    """Load one LoRA and (optionally) rewrite its block indices. Returns (sd, log)."""
    stem = Path(name).stem
    path = folder_paths.get_full_path("loras", name)
    if not path:
        raise RuntimeError(f"[LoRA Stack Apply] LoRA file not found: {name}")

    sd = comfy.utils.load_torch_file(path, safe_load=True)

    if not enable_remap:
        return sd, f"{stem}: applied as-is (remap disabled)"
    if not target_count:
        return sd, f"{stem}: applied as-is (target generation unknown)"

    detected = detect_lora_block_count(sd.keys())
    source_count = resolve_dropdown(source_choice) or detected
    if not source_count:
        return sd, f"{stem}: applied as-is (no block keys detected)"

    if source_count > target_count:
        raise ValueError(
            f"[LoRA Stack Apply] '{stem}' references {source_count} layers "
            f"({describe_count(source_count)}) but the connected model has only "
            f"{target_count} ({describe_count(target_count)}). Remapping downwards is "
            "not supported: those layers do not exist on that model. Use a model of "
            "the same or a newer generation, or override 'source_model' if the "
            "detection was wrong."
        )

    mapping = get_mapping(source_count, target_count)
    if mapping is None:
        return sd, f"{stem}: {source_count}->{target_count} no mapping, applied as-is"

    if remap_mode == REMAP_MODE_EXTEND:
        sd, stats = extend_state_dict(sd, mapping, target_count, extend_strength)
        return sd, (
            f"{stem}: {source_count}->{target_count} remapped "
            f"(+{stats['added']} tensors onto new layers x{extend_strength:g}, "
            f"{stats['dropped']} dropped)"
        )

    sd, stats = remap_state_dict(sd, mapping)
    return sd, (
        f"{stem}: {source_count}->{target_count} remapped "
        f"({stats['remapped']} moved, {stats['dropped']} dropped)"
    )


def _apply_stack(
    model,
    clip,
    lora_stack,
    *,
    enable_remap,
    target_model,
    source_model,
    remap_mode,
    extend_strength,
    weight_multiplier,
    apply_clip,
):
    """Shared body for both appliers. Returns (model, clip, info_text)."""
    multiplier = _num(weight_multiplier, 1.0)
    target_count = None
    if enable_remap:
        target_count = resolve_dropdown(target_model) or detect_model_block_count(model)

    info = []
    if enable_remap:
        info.append(f"target: {describe_count(target_count)}")
    else:
        info.append("remap: disabled")

    out_model = model
    out_clip = clip
    applied = 0
    stack = list(lora_stack or [])
    if not stack:
        info.append("applied: 0 lora(s) (empty stack)")

    for entry in stack:
        unpacked = _unpack_entry(entry)
        if unpacked is None:
            continue
        name, w_model, w_clip = unpacked

        w_model = _num(w_model * multiplier, 0.0)
        w_clip = _num(w_clip * multiplier, 0.0)
        if not apply_clip or out_clip is None:
            w_clip = 0.0
        if w_model == 0.0 and w_clip == 0.0:
            info.append(f"{Path(name).stem}: skipped (weights are 0)")
            continue

        sd, line = _load_and_remap(
            name, target_count, enable_remap, source_model, remap_mode, extend_strength
        )
        out_model, out_clip = comfy.sd.load_lora_for_models(
            out_model, out_clip, sd, w_model, w_clip
        )
        applied += 1
        info.append(f"{line}  [w={w_model:g}, clip={w_clip:g}]")

    if stack:
        info.insert(1, f"applied: {applied} lora(s)")
    return out_model, out_clip, "\n".join(info)


# --------------------------------------------------------------------------- #
# Plain applier (no Anima options)
# --------------------------------------------------------------------------- #
class LoRAStackApplyBasic:
    """Apply a LORA_STACK to MODEL/CLIP. No remap, no Anima options."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL", {"tooltip": t("tip.model")}),
                "bypass": ("BOOLEAN", {"default": False, "tooltip": t("tip.bypass")}),
                "weight_multiplier": (
                    "FLOAT",
                    {
                        "default": 1.0, "min": 0.0, "max": 4.0, "step": 0.05,
                        "tooltip": t("tip.weight_multiplier"),
                    },
                ),
                "apply_clip": (
                    "BOOLEAN",
                    {"default": True, "tooltip": t("tip.apply_clip")},
                ),
            },
            "optional": {
                "clip": ("CLIP", {"tooltip": t("tip.clip_optional")}),
                "lora_stack": ("LORA_STACK", {"tooltip": t("tip.lora_stack_apply")}),
            },
        }

    RETURN_TYPES = ("MODEL", "CLIP", "STRING")
    RETURN_NAMES = ("MODEL", "CLIP", "INFO")
    FUNCTION = "apply"
    CATEGORY = t("category")
    DESCRIPTION = t("desc.apply")

    def apply(self, model, bypass, weight_multiplier, apply_clip, clip=None, lora_stack=None):
        if bypass:
            return (model, clip, "bypassed (MODEL/CLIP passed through untouched)")
        return _apply_stack(
            model, clip, lora_stack,
            enable_remap=False,
            target_model=AUTO_LABEL,
            source_model=AUTO_LABEL,
            remap_mode=REMAP_MODE_KEYS,
            extend_strength=0.0,
            weight_multiplier=weight_multiplier,
            apply_clip=apply_clip,
        )


# --------------------------------------------------------------------------- #
# Anima remap applier
# --------------------------------------------------------------------------- #
class LoRAStackApply:
    """Apply a LORA_STACK to MODEL/CLIP, remapping Anima block indices."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL", {"tooltip": t("tip.model")}),
                "bypass": ("BOOLEAN", {"default": False, "tooltip": t("tip.bypass")}),
                "enable_remap": (
                    "BOOLEAN",
                    {"default": True, "tooltip": t("tip.enable_remap")},
                ),
                "target_model": (
                    MODEL_CHOICES,
                    {"default": AUTO_LABEL, "tooltip": t("tip.target_model")},
                ),
                "source_model": (
                    MODEL_CHOICES,
                    {"default": AUTO_LABEL, "tooltip": t("tip.source_model")},
                ),
                "remap_mode": (
                    REMAP_MODES,
                    {"default": REMAP_MODE_KEYS, "tooltip": t("tip.remap_mode")},
                ),
                "extend_strength": (
                    "FLOAT",
                    {
                        "default": 0.5, "min": 0.0, "max": 2.0, "step": 0.05,
                        "tooltip": t("tip.extend_strength"),
                    },
                ),
                "weight_multiplier": (
                    "FLOAT",
                    {
                        "default": 1.0, "min": 0.0, "max": 4.0, "step": 0.05,
                        "tooltip": t("tip.weight_multiplier"),
                    },
                ),
                "apply_clip": (
                    "BOOLEAN",
                    {"default": True, "tooltip": t("tip.apply_clip")},
                ),
            },
            "optional": {
                "clip": ("CLIP", {"tooltip": t("tip.clip_optional")}),
                "lora_stack": ("LORA_STACK", {"tooltip": t("tip.lora_stack_apply")}),
            },
        }

    RETURN_TYPES = ("MODEL", "CLIP", "STRING")
    RETURN_NAMES = ("MODEL", "CLIP", "REMAP_INFO")
    FUNCTION = "apply"
    CATEGORY = t("category")
    DESCRIPTION = t("desc.apply_anima")

    def apply(
        self,
        model,
        bypass,
        enable_remap,
        target_model,
        source_model,
        remap_mode,
        extend_strength,
        weight_multiplier,
        apply_clip,
        clip=None,
        lora_stack=None,
    ):
        if bypass:
            return (model, clip, "bypassed (MODEL/CLIP passed through untouched)")
        return _apply_stack(
            model, clip, lora_stack,
            enable_remap=enable_remap,
            target_model=target_model,
            source_model=source_model,
            remap_mode=remap_mode,
            extend_strength=extend_strength,
            weight_multiplier=weight_multiplier,
            apply_clip=apply_clip,
        )


NODE_CLASS_MAPPINGS = {
    "LoRAStackApplyBasic": LoRAStackApplyBasic,
    "LoRAStackApply": LoRAStackApply,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoRAStackApplyBasic": t("node.apply"),
    "LoRAStackApply": t("node.apply_anima"),
}
