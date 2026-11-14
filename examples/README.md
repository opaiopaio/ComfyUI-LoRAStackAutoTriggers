# Example workflows

`quickstart_stack.json` — the minimal shape of this package:

```
CheckpointLoaderSimple → LoRA Stack Auto Triggers → LoRA Stack Apply (Anima Remap)
```

Notes:

- `LoRA Stack Auto Triggers` exposes `LORA_STACK` / `LORA_PROMPT` / `LORA_MetaData`; feed
  `LORA_PROMPT` into your positive prompt node.
- `LoRA Stack Apply` needs no other custom node; its remap targets Anima 28/40/52-layer layouts.
- The trigger-word lookup is optional: it only runs when you click the button on a stack entry, and
  it falls back to the local cache when offline.
