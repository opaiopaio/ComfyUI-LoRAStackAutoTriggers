# ComfyUI-LoRAStackAutoTriggers — node package
#
# Two nodes sharing one slot/trigger-word implementation:
#   LoRA Stack Auto Triggers                 (stack builder)
#   LoRA Stack Auto Triggers (Anima Remap)   (stack builder + applier with
#                                             Anima cross-generation remapping)
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

# The Anima node is optional: if it fails to import (e.g. an unusual ComfyUI
# build), the base node must still load.
try:
    from oplorast_anima_node import (
        NODE_CLASS_MAPPINGS as _ANIMA_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS as _ANIMA_DISPLAY_NAMES,
    )

    NODE_CLASS_MAPPINGS.update(_ANIMA_CLASS_MAPPINGS)
    NODE_DISPLAY_NAME_MAPPINGS.update(_ANIMA_DISPLAY_NAMES)
    _anima_ok = True
except Exception as e:  # pragma: no cover
    _anima_ok = False
    print(f"[LoRAStackAutoTriggers] Anima Remap node unavailable: {e}")

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print(
    "[LoRAStackAutoTriggers] loaded nodes: "
    + ", ".join(sorted(NODE_CLASS_MAPPINGS))
    + ("" if _anima_ok else "  (Anima Remap node failed to load)")
)
