# OP - LoRA Stack Auto Triggers OP (node package: OP节点)
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Register the backend route (non-fatal if PromptServer is unavailable).
try:
    from oplorast_utils import setup_lora_trigger_routes
    setup_lora_trigger_routes()
except Exception as e:
    print(f"[OP] route setup failed: {e}")

from oplorast_node import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("[OP] LoRA Stack Auto Triggers OP loaded.")