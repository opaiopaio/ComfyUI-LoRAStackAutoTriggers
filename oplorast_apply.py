"""Stack applier for this node pack.

Two reasons this exists:

1. This pack used to only BUILD a LORA_STACK, so anyone without a third-party
   "apply LoRA stack" node could not use it at all.
2. The Anima cross-generation remap has to happen at one specific moment:
   after the LoRA file is loaded, and before its deltas are folded into the
   model by comfy.sd.load_lora_for_models. A node placed *after* an applier
   cannot fix anything -- the weights are already applied at that point with
   the wrong block indices.

So this node sits where the applier sits: LORA_STACK + MODEL (+CLIP) in,
MODEL/CLIP out.
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

REMAP_MODE_KEYS = "Keys only (recommended)"
REMAP_MODE_EXTEND = "Extend to new layers (experimental)"
REMAP_MODES = [REMAP_MODE_KEYS, REMAP_MODE_EXTEND]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _num(value, default=0.0):
    """Coerce to a finite float. NaN/Inf (which a widget can end up holding
    after a paste/clone) become `default` -- a NaN strength silently poisons
    the model and shows up as a grey/black image with no error."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return float(default)
    return float(default) if (math.isnan(f) or math.isinf(f)) else f


def _unpack_entry(entry):
    """LORA_STACK entry -> (name, w_model, w_clip), or None to skip."""
    if not isinstance(entry, (list, tuple)) or not entry:
        return None
    name = entry[0]
    if not isinstance(name, str) or not name or name == "None":
        return None
    # A missing weight means "1.0"; a present-but-NaN/Inf weight means
    # "garbage" and becomes 0 so the entry is skipped instead of poisoning
    # the model with NaN strengths.
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
    detected = detect_lora_block_count(sd.keys())
    source_count = resolve_dropdown(source_choice) or detected

    if not enable_remap:
        return sd, f"{stem}: applied as-is (remap disabled)"
    if not target_count:
        return sd, f"{stem}: applied as-is (target generation unknown)"
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


# --------------------------------------------------------------------------- #
# node
# --------------------------------------------------------------------------- #
class LoRAStackApply:
    """Apply a LORA_STACK to MODEL/CLIP, with optional Anima block remapping."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": (
                    "MODEL",
                    {
                        "tooltip": (
                            "Model to apply the stack to. Its layer count is used to "
                            "detect the target Anima generation."
                        )
                    },
                ),
                "lora_stack": (
                    "LORA_STACK",
                    {
                        "tooltip": (
                            "Stack to apply (from LoRA Stack Auto Triggers or any other "
                            "node that produces LORA_STACK)."
                        )
                    },
                ),
                "bypass": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Pass MODEL/CLIP through untouched (quick A/B toggle)",
                    },
                ),
                "enable_remap": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": (
                            "Anima only. Turn off to apply LoRAs untouched. For models "
                            "that are not Anima this is a no-op either way."
                        ),
                    },
                ),
                "target_model": (
                    MODEL_CHOICES,
                    {
                        "default": AUTO_LABEL,
                        "tooltip": (
                            "Generation of the connected model. Auto detects it from the "
                            "layer count; override if Auto gets it wrong."
                        ),
                    },
                ),
                "source_model": (
                    MODEL_CHOICES,
                    {
                        "default": AUTO_LABEL,
                        "tooltip": (
                            "Generation the LoRA was trained on. Auto infers it from the "
                            "LoRA's highest block index -- which mis-reads adapters that "
                            "only touch early layers, so override when in doubt."
                        ),
                    },
                ),
                "remap_mode": (
                    REMAP_MODES,
                    {
                        "default": REMAP_MODE_KEYS,
                        "tooltip": (
                            "Keys only: rewrite indices (new layers get no delta). "
                            "Extend: also project each source delta onto the layers "
                            "inserted from it (experimental)."
                        ),
                    },
                ),
                "extend_strength": (
                    "FLOAT",
                    {
                        "default": 0.5, "min": 0.0, "max": 2.0, "step": 0.05,
                        "tooltip": (
                            "Only used by Extend mode. 1.0 copies the source delta "
                            "as-is; scales linearly."
                        ),
                    },
                ),
                "weight_multiplier": (
                    "FLOAT",
                    {
                        "default": 1.0, "min": 0.0, "max": 4.0, "step": 0.05,
                        "tooltip": (
                            "Multiplies every weight in the stack. 1.0 = unchanged; "
                            "use it to dial the whole stack up or down at once."
                        ),
                    },
                ),
                "apply_clip": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": (
                            "OFF = never touch the text encoder: all CLIP weights are "
                            "forced to 0 (model-only application)."
                        ),
                    },
                ),
            },
            "optional": {
                "clip": (
                    "CLIP",
                    {"tooltip": "Optional. Without it, CLIP weights are ignored."},
                ),
            },
        }

    RETURN_TYPES = ("MODEL", "CLIP", "STRING")
    RETURN_NAMES = ("MODEL", "CLIP", "REMAP_INFO")
    FUNCTION = "apply"
    CATEGORY = "LoRA Stack"
    DESCRIPTION = (
        "Apply a LORA_STACK to MODEL/CLIP. Includes Anima cross-generation block "
        "remapping (28 / 40 / 52 layers), so LoRAs trained on Anima base work on "
        "Anima 2.9B / 3.8B."
    )

    def apply(
        self,
        model,
        lora_stack,
        bypass,
        enable_remap,
        target_model,
        source_model,
        remap_mode,
        extend_strength,
        weight_multiplier,
        apply_clip,
        clip=None,
    ):
        if bypass:
            return (model, clip, "bypassed (MODEL/CLIP passed through untouched)")

        multiplier = _num(weight_multiplier, 1.0)
        target_count = (
            resolve_dropdown(target_model) or detect_model_block_count(model)
        ) if enable_remap else None

        info = [f"target: {describe_count(target_count)}" if enable_remap else "remap: disabled"]
        out_model = model
        out_clip = clip
        applied = 0

        for entry in (lora_stack or []):
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

        info.insert(1 if len(info) > 1 else 1, f"applied: {applied} lora(s)")
        return (out_model, out_clip, "\n".join(info))


NODE_CLASS_MAPPINGS = {
    "LoRAStackApply": LoRAStackApply,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoRAStackApply": "LoRA Stack Apply (Anima Remap)",
}
