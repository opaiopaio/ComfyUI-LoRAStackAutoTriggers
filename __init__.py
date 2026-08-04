# ComfyUI-LoRAStackAutoTriggers
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

from oplorast_node import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("[LoRAStackAutoTriggers] LoRA Stack Auto Triggers loaded.")