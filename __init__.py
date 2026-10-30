# ComfyUI-LoRAStackAutoTriggers — node package
#
#   LoRA Stack Auto Triggers          stack builder: pick LoRAs + pick trigger words
#                                     -> LORA_STACK / LORA_PROMPT / LORA_MetaData
#   LoRA Stack Apply (Anima Remap)    applier: LORA_STACK + MODEL (+CLIP)
#                                     -> MODEL / CLIP / REMAP_INFO
#                                     (also covers non-Anima use; the remap part
#                                      simply no-ops when the generations match)
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from oplorast_utils import setup_lora_trigger_routes

    setup_lora_trigger_routes()
except Exception as e:
    print(f"[LoRAStackAutoTriggers] route setup failed: {e}")

from oplorast_node import (
    NODE_CLASS_MAPPINGS as _BASE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as _BASE_DISPLAY_NAMES,
)

NODE_CLASS_MAPPINGS = dict(_BASE_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS = dict(_BASE_DISPLAY_NAMES)

# The applier (and with it the Anima remap) is optional: if it fails to import
# on an unusual ComfyUI build, the stack builder must still load.
_apply_ok = True
try:
    from oplorast_apply import (
        NODE_CLASS_MAPPINGS as _APPLY_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS as _APPLY_DISPLAY_NAMES,
    )

    NODE_CLASS_MAPPINGS.update(_APPLY_CLASS_MAPPINGS)
    NODE_DISPLAY_NAME_MAPPINGS.update(_APPLY_DISPLAY_NAMES)
except Exception as e:  # pragma: no cover
    _apply_ok = False
    print(f"[LoRAStackAutoTriggers] apply node unavailable: {e}")

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print(
    "[LoRAStackAutoTriggers] loaded nodes: "
    + ", ".join(sorted(NODE_CLASS_MAPPINGS))
    + ("" if _apply_ok else "  (apply node failed to load)")
)
