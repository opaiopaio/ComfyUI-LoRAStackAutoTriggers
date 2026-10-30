# ComfyUI-LoRAStackAutoTriggers — Anima Remap node
#
# Same slot/trigger-word system as the base node, but this one also APPLIES the
# stack to a MODEL, translating LoRA block indices between Anima generations:
#
#     28 layers = Anima (base / anima-preview, e.g. anima_aestheticV11)
#     40 layers = Anima 2.9B
#     52 layers = Anima 3.8B
#
# Anima generations are depth expansions: 12 new blocks are spliced into the
# middle of the previous layout, so a LoRA trained on 28 layers addresses the
# wrong layers from block 2 onward on a 40-layer model -- silently, because
# those indices do still exist. This node rewrites the LoRA's own block keys
# before applying it, so the deltas land on the layers that hold the original
# weights.
#
# Remapping here is self-contained (no monkeypatching of comfy.lora.load_lora),
# forward-only, and never writes files: remapping is a key rewrite, which is
# essentially free, so a disk cache would only add staleness problems.
#
# Two remap modes:
#   Keys only  - rewrite the block indices; the 12 newly-inserted layers get
#                no delta from this LoRA, so its effect is somewhat weaker
#                than on the model it was trained for.
#   Extend     - additionally copy each source block's delta onto the layer(s)
#                inserted from it, scaled by extend_strength. Best effort:
#                there is no "correct" answer for layers that did not exist
#                when the LoRA was trained.
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
from oplorast_slots import (
    add_slot_inputs,
    build_metadata,
    build_prompt,
    iter_enabled_slots,
    metadata_segment,
    trigger_segment,
)

REMAP_MODE_KEYS = "Keys only (recommended)"
REMAP_MODE_EXTEND = "Extend to new layers (experimental)"
REMAP_MODES = [REMAP_MODE_KEYS, REMAP_MODE_EXTEND]


class LoRAStackAutoTriggersAnimaRemap:
    """LoRA stack + auto trigger words + Anima cross-generation remapping."""

    @classmethod
    def INPUT_TYPES(cls):
        inputs = {"required": {}, "optional": {}}
        required = inputs["required"]

        required["model"] = (
            "MODEL",
            {
                "tooltip": (
                    "Anima model to apply the stack to. Its layer count decides "
                    "the target generation (28 / 40 / 52)."
                )
            },
        )

        inputs["optional"]["clip"] = (
            "CLIP",
            {"tooltip": "Optional CLIP. Without it, CLIP weights are ignored."},
        )
        inputs["optional"]["lora_stack"] = (
            "LORA_STACK",
            {
                "tooltip": (
                    "Extra LoRAs to apply (e.g. from a LoRA Stack Auto Triggers "
                    "node). These are remapped too. Connect either a stack here or "
                    "an already-applied MODEL, not both."
                )
            },
        )
        inputs["optional"]["lora_prompt"] = (
            "STRING",
            {"default": "", "tooltip": "Existing LoRA prompt to extend"},
        )
        inputs["optional"]["lora_metadata"] = (
            "STRING",
            {"default": "", "tooltip": "Existing LoRA metadata to extend"},
        )

        add_slot_inputs(inputs)

        required["enable_remap"] = (
            "BOOLEAN",
            {
                "default": True,
                "tooltip": "Turn off to apply LoRAs untouched (A/B comparison)",
            },
        )
        required["target_model"] = (
            MODEL_CHOICES,
            {
                "default": AUTO_LABEL,
                "tooltip": (
                    "Generation of the connected MODEL. Auto detects it from the "
                    "layer count; set it by hand if Auto gets it wrong."
                ),
            },
        )
        required["source_model"] = (
            MODEL_CHOICES,
            {
                "default": AUTO_LABEL,
                "tooltip": (
                    "Generation the LoRA was trained on. Auto infers it from the "
                    "LoRA's own highest block index -- which mis-reads adapters "
                    "that only touch early layers, so override it when in doubt."
                ),
            },
        )
        required["remap_mode"] = (
            REMAP_MODES,
            {
                "default": REMAP_MODE_KEYS,
                "tooltip": (
                    "Keys only: rewrite indices (new layers get no delta). "
                    "Extend: also project each source delta onto the layers "
                    "inserted from it (experimental)."
                ),
            },
        )
        required["extend_strength"] = (
            "FLOAT",
            {
                "default": 0.5, "min": 0.0, "max": 2.0, "step": 0.05,
                "tooltip": (
                    "Only used by the Extend mode. 1.0 copies the source delta "
                    "as-is; scales linearly."
                ),
            },
        )

        required["save_hash"] = (
            "BOOLEAN",
            {"default": False, "tooltip": "Include SHA256[:12] in metadata"},
        )
        required["force_fetch"] = (
            "BOOLEAN",
            {"default": False, "tooltip": "Force re-fetch from civitai"},
        )
        required["fallback_to_filename"] = (
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

    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING", "LORA_STACK", "STRING")
    RETURN_NAMES = (
        "MODEL",
        "CLIP",
        "LORA_PROMPT",
        "LORA_MetaData",
        "LORA_STACK",
        "REMAP_INFO",
    )
    FUNCTION = "stack"
    CATEGORY = "LoRA Stack"
    DESCRIPTION = (
        "LoRA stack with auto trigger words, applying Anima LoRAs across "
        "generations (28 / 40 / 52 layers) with automatic block remapping."
    )

    # ------------------------------------------------------------------ #
    def _apply_one(
        self,
        name,
        model_weight,
        clip_weight,
        model,
        clip,
        target_count,
        enable_remap,
        source_choice,
        remap_mode,
        extend_strength,
    ):
        """Load one LoRA, remap it if needed, apply it. Returns (model, clip, log)."""
        stem = Path(name).stem
        path = folder_paths.get_full_path("loras", name)
        if not path:
            raise RuntimeError(f"[Anima Remap] LoRA file not found: {name}")

        sd = comfy.utils.load_torch_file(path, safe_load=True)
        detected = detect_lora_block_count(sd.keys())
        source_count = resolve_dropdown(source_choice) or detected

        line = f"{stem}: "

        if enable_remap and target_count and source_count:
            if source_count > target_count:
                raise ValueError(
                    f"[Anima Remap] '{stem}' is a {source_count}-layer "
                    f"({describe_count(source_count)}) LoRA but the connected model has "
                    f"only {target_count} layers ({describe_count(target_count)}). "
                    "Remapping downwards is not supported: the layers this LoRA needs "
                    "do not exist on that model. Use a model of the same or newer "
                    "generation, or set 'source_model' if the detection was wrong."
                )

            mapping = get_mapping(source_count, target_count)
            if mapping is None:
                line += f"{source_count}->{target_count} no mapping, applied as-is"
            elif remap_mode == REMAP_MODE_EXTEND:
                sd, stats = extend_state_dict(
                    sd, mapping, target_count, extend_strength
                )
                line += (
                    f"{source_count}->{target_count} remapped"
                    f" (+{stats['added']} tensors onto new layers"
                    f" x{extend_strength:g}, {stats['dropped']} dropped)"
                )
            else:
                sd, stats = remap_state_dict(sd, mapping)
                line += (
                    f"{source_count}->{target_count} remapped"
                    f" ({stats['remapped']} moved, {stats['dropped']} dropped)"
                )
        elif not target_count:
            line += "target generation unknown, applied as-is"
        elif not enable_remap:
            line += "remap disabled, applied as-is"
        else:
            line += (
                f"applied as-is (source {source_count or '?'}, "
                f"target {target_count or '?'})"
            )

        strength_clip = clip_weight if clip is not None else 0.0
        model, clip = comfy.sd.load_lora_for_models(
            model, clip, sd, model_weight, strength_clip
        )
        return model, clip, line

    # ------------------------------------------------------------------ #
    def stack(
        self,
        model,
        enable_remap,
        target_model,
        source_model,
        remap_mode,
        extend_strength,
        save_hash,
        force_fetch,
        fallback_to_filename,
        clip=None,
        lora_stack=None,
        lora_prompt=None,
        lora_metadata=None,
        **kwargs,
    ):
        target_count = resolve_dropdown(target_model) or detect_model_block_count(model)

        out_model = model
        out_clip = clip
        lora_list = []
        prompt_segments = []
        meta_segments = []
        info = [f"target: {describe_count(target_count)}"]

        # LoRAs handed in from another node: applied here (so the MODEL output is
        # complete) but they carry no per-slot trigger selection, so nothing is
        # added to the prompt for them.
        if lora_stack:
            for entry in lora_stack:
                name, mw, cw = entry[0], entry[1], entry[2]
                if name == "None":
                    continue
                lora_list.append((name, mw, cw))
                out_model, out_clip, line = self._apply_one(
                    name, mw, cw, out_model, out_clip, target_count,
                    enable_remap, source_model, remap_mode, extend_strength,
                )
                info.append(line)

        for i, name, mw, cw in iter_enabled_slots(kwargs):
            lora_list.append((name, mw, cw))
            out_model, out_clip, line = self._apply_one(
                name, mw, cw, out_model, out_clip, target_count,
                enable_remap, source_model, remap_mode, extend_strength,
            )
            info.append(line)

            segment = trigger_segment(
                name, kwargs, i, force_fetch, fallback_to_filename, mw
            )
            if segment:
                prompt_segments.append(segment)

            meta_segments.append(metadata_segment(name, save_hash))

        return (
            out_model,
            out_clip,
            build_prompt(prompt_segments, lora_prompt),
            build_metadata(meta_segments, lora_metadata),
            lora_list,
            "\n".join(info),
        )


NODE_CLASS_MAPPINGS = {
    "LoRA Stack Auto Triggers (Anima Remap)": LoRAStackAutoTriggersAnimaRemap,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoRA Stack Auto Triggers (Anima Remap)": "LoRA Stack Auto Triggers (Anima Remap)",
}
