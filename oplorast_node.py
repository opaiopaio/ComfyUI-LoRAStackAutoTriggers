# ComfyUI-LoRAStackAutoTriggers — base node
#
# A LoRA stacker that pulls trigger words automatically (civitai + safetensors
# metadata) and lets you pick them with a visual dialog, then hands the stack
# to any Apply node.
#
# Model & CLIP weights are independent: clip_weight = 0 means "no CLIP effect"
# (model still applies); a slot is active when ON + name selected +
# (model_weight != 0 OR clip_weight != 0).
#
# `trigger_selector_i` accepts, in priority order:
#   ""        -> the first civitai variant (safe default, not "everything")
#   free text -> injected verbatim (what the picker dialog writes)
#   [a, b]    -> JSON list
#   0, 3, 5:8 -> legacy slice syntax over variants+meta (old workflows)
#
# Slot definitions and trigger resolution live in oplorast_slots.py so this
# node and the (Anima Remap) variant share exactly one implementation.
from oplorast_slots import (
    add_slot_inputs,
    build_metadata,
    build_prompt,
    iter_enabled_slots,
    metadata_segment,
    trigger_segment,
)


class LoRAStackAutoTriggers:
    """Stack up to 4 LoRAs with auto trigger-word extraction and picker UI."""

    @classmethod
    def INPUT_TYPES(cls):
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

        add_slot_inputs(inputs)

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

        if lora_stack is not None:
            lora_list.extend([entry for entry in lora_stack if entry[0] != "None"])

        for i, name, mw, cw in iter_enabled_slots(kwargs):
            lora_list.append((name, mw, cw))

            segment = trigger_segment(
                name, kwargs, i, force_fetch, fallback_to_filename, mw
            )
            if segment:
                prompt_segments.append(segment)

            meta_segments.append(metadata_segment(name, save_hash))

        return (
            lora_list,
            build_prompt(prompt_segments, lora_prompt),
            build_metadata(meta_segments, lora_metadata),
        )


NODE_CLASS_MAPPINGS = {
    "LoRA Stack Auto Triggers": LoRAStackAutoTriggers,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoRA Stack Auto Triggers": "LoRA Stack Auto Triggers",
}
