# ComfyUI-LoRAStackAutoTriggers
# A JK-style LoRA stacker with integrated auto trigger-word extraction.
#
# Model & CLIP weights are independent: clip_weight = 0 means "no CLIP
# effect" (model still applies); a lora is active when switch ON + name
# selected + (model_weight != 0 OR clip_weight != 0).
#
# Trigger words (v1.1.0): civitai usually returns WHOLE variant sentences
# ("Default", "costume A", ...), not single tags. `trigger_selector_i` now
# accepts, in priority order:
#   ""        -> the first civitai variant (safe default, not "everything")
#   free text -> injected verbatim (what the picker dialog writes: a
#                hand-picked substring / a variant with optional parts removed)
#   [a, b]    -> JSON list
#   0, 3, 5:8 -> legacy slice syntax over variants+meta (old workflows)
#
# Prompt output: triggers-only when available, else <lora:name:weight> fallback.
from pathlib import Path

import folder_paths

from oplorast_utils import (
    get_structured_tags,
    resolve_selection,
    split_segments,
    calculate_sha256,
)


class LoRAStackAutoTriggers:
    """Stack up to 4 LoRAs with auto trigger-word extraction and picker UI."""

    @classmethod
    def INPUT_TYPES(cls):
        loras = ["None"] + folder_paths.get_filename_list("loras")
        inputs = {"required": {}, "optional": {}}

        inputs["optional"]["lora_stack"] = (
            "LORA_STACK",
            {"tooltip": "Existing LoRA stack to extend (chain more nodes here)"},
        )
        inputs["optional"]["lora_prompt"] = (
            "STRING",
            {"default": "", "tooltip": "Existing LoRA prompt to extend"},
        )
        inputs["optional"]["lora_metadata"] = (
            "STRING",
            {"default": "", "tooltip": "Existing LoRA metadata to extend"},
        )

        for i in range(1, 5):
            inputs["required"][f"lora_{i}"] = (
                "BOOLEAN",
                {"default": False, "tooltip": f"Enable/disable LoRA {i}"},
            )
            inputs["required"][f"lora_name_{i}"] = (
                loras,
                {"tooltip": f"Select LoRA model {i}"},
            )
            inputs["required"][f"model_weight_{i}"] = (
                "FLOAT",
                {
                    "default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01,
                    "tooltip": f"Model (U-Net) weight for LoRA {i}; 0 = no model effect",
                },
            )
            inputs["required"][f"clip_weight_{i}"] = (
                "FLOAT",
                {
                    "default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01,
                    "tooltip": (
                        f"CLIP (text encoder) weight for LoRA {i}; "
                        "0 = no CLIP effect (model still applies)"
                    ),
                },
            )
            inputs["required"][f"trigger_selector_{i}"] = (
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
            inputs["required"][f"trigger_weight_{i}"] = (
                "FLOAT",
                {
                    "default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01,
                    "tooltip": (
                        f"Wraps every selected segment as (seg:weight) for LoRA {i}; "
                        "1.0 = no wrapping"
                    ),
                },
            )
            inputs["required"][f"trigger_preview_{i}"] = (
                "STRING",
                {
                    "default": "",
                    "tooltip": f"One-line summary for LoRA {i} (filled by the UI)",
                },
            )

        inputs["required"]["save_hash"] = (
            "BOOLEAN",
            {"default": False, "tooltip": "Include SHA256[:12] in metadata"},
        )
        inputs["required"]["force_fetch"] = (
            "BOOLEAN",
            {"default": False, "tooltip": "Force re-fetch from civitai"},
        )
        inputs["required"]["fallback_to_filename"] = (
            "BOOLEAN",
            {
                "default": True,
                "tooltip": (
                    "No trigger words found -> output <lora:name:weight> as fallback; "
                    "OFF -> skip that lora from the prompt"
                ),
            },
        )
        return inputs

    RETURN_TYPES = ("LORA_STACK", "STRING", "STRING")
    RETURN_NAMES = ("LORA_STACK", "LORA_PROMPT", "LORA_MetaData")
    FUNCTION = "lora_stacker"
    CATEGORY = "LoRA Stack"
    DESCRIPTION = "LoRA stack with auto trigger-word extraction and picker UI."

    def lora_stacker(self, save_hash, force_fetch, fallback_to_filename,
                     lora_stack=None, lora_prompt=None, lora_metadata=None, **kwargs):
        lora_list = []
        prompt_segments = []
        meta_segments = []

        if lora_stack is not None:
            lora_list.extend([l for l in lora_stack if l[0] != "None"])

        for i in range(1, 5):
            name = kwargs.get(f"lora_name_{i}")
            on = kwargs.get(f"lora_{i}") is True
            mw = kwargs.get(f"model_weight_{i}")
            cw = kwargs.get(f"clip_weight_{i}")

            name_ok = name is not None and name != "None"
            enabled = on and name_ok and (mw != 0 or cw != 0)
            if not enabled:
                continue

            lora_list.append((name, mw, cw))
            stem = Path(name).stem

            sel = kwargs.get(f"trigger_selector_{i}", "")
            tw = kwargs.get(f"trigger_weight_{i}", 1.0)
            st = get_structured_tags(name, force_fetch)
            resolved = resolve_selection(sel, st["variants"], st["meta"])

            if resolved:
                if tw != 1.0:
                    parts = split_segments(resolved)
                    segment = ", ".join(f"({p}:{tw})" for p in parts)
                else:
                    segment = resolved.strip()
            elif fallback_to_filename:
                segment = f"<lora:{stem}:{mw:.3f}>"
            else:
                segment = ""

            if segment:
                prompt_segments.append(segment)

            hash_part = ""
            if save_hash:
                p = folder_paths.get_full_path("loras", name)
                sha = calculate_sha256(p) if p else None
                hash_part = f": [{sha[:12]}]" if sha else ""
            meta_segments.append(f"{stem}{hash_part}")

        if lora_prompt and prompt_segments:
            lorapromptout = f"{lora_prompt}," + ",".join(prompt_segments)
        elif prompt_segments:
            lorapromptout = ",".join(prompt_segments)
        else:
            lorapromptout = lora_prompt or ""

        if lora_metadata and meta_segments:
            lorametaout = f"{lora_metadata}, " + ", ".join(meta_segments)
        elif meta_segments:
            lorametaout = ", ".join(meta_segments)
        else:
            lorametaout = lora_metadata or ""

        return (lora_list, lorapromptout, lorametaout)


NODE_CLASS_MAPPINGS = {
    "LoRA Stack Auto Triggers": LoRAStackAutoTriggers,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoRA Stack Auto Triggers": "LoRA Stack Auto Triggers",
}
