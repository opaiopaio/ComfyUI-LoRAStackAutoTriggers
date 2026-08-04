# OP node - LoRA Stack Auto Triggers OP
# A JK-style LoRA stacker with integrated auto trigger-word extraction.
#
# Model & CLIP weights are independent (v3): clip_weight = 0 means "no CLIP
# effect" (model still applies); a lora is active when switch ON + name
# selected + (model_weight != 0 OR clip_weight != 0).
#
# Trigger words: fetched per lora via civitai API (by SHA256) + safetensors
# training metadata (ss_tag_frequency), merged and deduped. A slice selector
# + weight + live preview widget are provided per slot (preview filled by JS).
#
# Prompt output: triggers-only when available, else <lora:name:weight> fallback.
from pathlib import Path

import folder_paths

from oplorast_utils import (
    get_combined_tag_strings,
    parse_selector,
    calculate_sha256,
)


class LoRAStackAutoTriggersOP:
    """Stack up to 4 LoRAs with auto trigger-word extraction and preview."""

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

        # 4 LoRA slots, each with original fields + trigger fields + preview
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
                    "default": 1.0,
                    "min": -10.0,
                    "max": 10.0,
                    "step": 0.01,
                    "tooltip": f"Model (U-Net) weight for LoRA {i}; 0 = no model effect",
                },
            )
            inputs["required"][f"clip_weight_{i}"] = (
                "FLOAT",
                {
                    "default": 1.0,
                    "min": -10.0,
                    "max": 10.0,
                    "step": 0.01,
                    "tooltip": (
                        f"CLIP (text encoder) weight for LoRA {i}; "
                        "0 = no CLIP effect (model still applies)"
                    ),
                },
            )
            inputs["required"][f"trigger_selector_{i}"] = (
                "STRING",
                {
                    "default": ":",
                    "tooltip": (
                        f"Trigger selector {i}. ATW slice syntax: "
                        "0, 3, 5:8, -8:, : (empty part = open end, : = all)"
                    ),
                },
            )
            inputs["required"][f"trigger_weight_{i}"] = (
                "FLOAT",
                {
                    "default": 1.0,
                    "min": -10.0,
                    "max": 10.0,
                    "step": 0.01,
                    "tooltip": f"Trigger word weight {i} (1.0 = no wrapping)",
                },
            )
            inputs["required"][f"trigger_preview_{i}"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": True,
                    "tooltip": f"Trigger preview {i} (auto-filled by UI)",
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
    CATEGORY = "OP"
    DESCRIPTION = "LoRA stack with auto trigger-word extraction and live preview."

    def lora_stacker(
        self,
        save_hash,
        force_fetch,
        fallback_to_filename,
        lora_stack=None,
        lora_prompt=None,
        lora_metadata=None,
        **kwargs,
    ):
        lora_list = []
        prompt_segments = []
        meta_segments = []

        # Extend with an existing stack (drop "None" entries)
        if lora_stack is not None:
            lora_list.extend([l for l in lora_stack if l[0] != "None"])

        for i in range(1, 5):
            name = kwargs.get(f"lora_name_{i}")
            on = kwargs.get(f"lora_{i}") is True
            mw = kwargs.get(f"model_weight_{i}")
            cw = kwargs.get(f"clip_weight_{i}")

            # model & CLIP weights are independent: active if either is non-zero.
            # clip_weight = 0 just means "no CLIP effect" (model still applies).
            name_ok = name is not None and name != "None"
            enabled = on and name_ok and (mw != 0 or cw != 0)
            if not enabled:
                continue

            # ---- stack tuple (uses real clip_weight, may be 0) ----
            lora_list.append((name, mw, cw))

            stem = Path(name).stem

            # ---- prompt segment: triggers only, or <lora:..> fallback ----
            sel = kwargs.get(f"trigger_selector_{i}", ":")
            tw = kwargs.get(f"trigger_weight_{i}", 1.0)
            tags, _cc, _mc = get_combined_tag_strings(name, force_fetch)
            selected = parse_selector(sel, tags)

            if selected:
                parts = [p.strip() for p in selected.split(",") if p.strip()]
                if tw != 1.0 and parts:
                    parts = [f"({p}:{tw})" for p in parts]
                segment = ", ".join(parts)
            elif fallback_to_filename:
                # no trigger words -> fall back to the lora prompt content
                segment = f"<lora:{stem}:{mw:.3f}>"
            else:
                segment = ""  # skip this lora from the prompt

            if segment:
                prompt_segments.append(segment)

            # ---- metadata segment ----
            hash_part = ""
            if save_hash:
                p = folder_paths.get_full_path("loras", name)
                sha = calculate_sha256(p) if p else None
                hash_part = f": [{sha[:12]}]" if sha else ""
            meta_segments.append(f"{stem}{hash_part}")

        # ---- assemble outputs ----
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
    "LoRA Stack Auto Triggers OP": LoRAStackAutoTriggersOP,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoRA Stack Auto Triggers OP": "LoRA Stack Auto Triggers OP",
}