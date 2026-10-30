# ComfyUI-LoRAStackAutoTriggers

**English** | [中文](README.zh.md)

Stack LoRAs, pick their trigger words visually, and apply them — including automatic
block remapping so LoRAs trained on **Anima** still work on **Anima 2.9B / 3.8B**.

---

## What you get

| Node | What it does | Outputs |
|---|---|---|
| **LoRA Stack Auto Triggers** | Pick up to 4 LoRAs and choose their trigger words in a visual picker. Trigger words are fetched automatically from Civitai **and** from the training metadata inside the model file. | `LORA_STACK`, `LORA_PROMPT`, `LORA_MetaData` |
| **LoRA Stack Apply** | Plain applier: takes any `LORA_STACK` and applies it to a model. | `MODEL`, `CLIP`, `INFO` |
| **LoRA Stack Apply (Anima Remap)** | Same applier, plus cross-generation block remapping for Anima models. | `MODEL`, `CLIP`, `REMAP_INFO` |

Why two appliers? So you don't need a third-party "apply LoRA stack" node to use this pack,
and so Anima users can swap in the remapping version only when they need it.

---

## Install

**Via ComfyUI Manager / Registry** — search for `LoRA Stack Auto Triggers`.

**Manual**

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/opaiopaio/ComfyUI-LoRAStackAutoTriggers.git
```

Restart ComfyUI. No extra Python packages are required (`requests` ships with ComfyUI).

---

## Quick start (5 steps)

1. Add **LoRA Stack Auto Triggers**.
2. Turn on `lora_1` and pick a LoRA from `lora_name_1`.
   The summary line updates to something like `28 layers · 4 variants / 1749 training tags`.
3. Click **⚙ Triggers 1**. In the dialog:
   - **Variants** – Civitai usually publishes *whole trigger sentences* (one per costume).
     Click one to load it.
   - **Segment chips** – after loading a variant it is split on commas. Click a chip to
     drop that part (e.g. `see-through mouth mask`), click again to bring it back.
   - **Training tags** – the raw training-set tag dump, searchable. Click to append.
   - **Free edit** – edit the text directly, or select part of it with the mouse and press
     **Apply selection** to keep only that part.
4. Press **Apply all** (or **Apply selection**).
5. Feed `LORA_PROMPT` into your text encoder, and the stack into an applier
   (**LoRA Stack Apply** / **(Anima Remap)**, or any other node that accepts `LORA_STACK`).

---

## The trigger picker

| Tab | Use it for |
|---|---|
| **Variants** | Pick one of the Civitai trigger sentences |
| **Segment chips** | Remove optional parts of a variant without retyping anything |
| **Training tags** | Pull single tags out of the training set (searchable) |
| **Free edit** | Hand-edit the final text, or keep only a mouse-selected portion |

**What ends up in `LORA_PROMPT`**

- If trigger words are available: just the trigger words (no `<lora:...>` tag).
- If nothing is found and `fallback_to_filename` is on: `<lora:name:weight>`.
- `fallback_to_filename` off: that LoRA is simply left out of the prompt
  (it is still applied to the model).

Nothing is hidden from your workflows: the selected text lives in a `trigger_selector_*`
field that the UI keeps out of the way, so existing workflows and the legacy slice syntax
(`0, 3, 5:8`, `:`) keep working.

---

## Node reference

### LoRA Stack Auto Triggers

Four identical slots. Per slot:

| Field | Meaning |
|---|---|
| `lora_N` | Enable this slot |
| `lora_name_N` | Which LoRA |
| `model_weight_N` | LoRA strength on the model; `0` = no model effect |
| `clip_weight_N` | LoRA strength on the text encoder; `0` = no CLIP effect (model still applies) |
| **`⚙ Triggers N`** | Opens the picker |
| `trigger_weight_N` | Wraps every selected segment as `(segment:weight)`; `1.0` = no wrapping |
| `trigger_preview_N` | Read-only one-line summary |

A slot is active when it is enabled **and** a LoRA is selected **and** at least one of the
two weights is non-zero. Model and CLIP weights are independent — setting CLIP to `0`
gives you "model only" instead of disabling the LoRA.

Bottom settings:

| Setting | Meaning |
|---|---|
| `save_hash` | Add the file's SHA256 (first 12 chars) to `LORA_MetaData` |
| `force_fetch` | Ignore the local cache and re-fetch from Civitai (refreshes all slots) |
| `fallback_to_filename` | Emit `<lora:name:weight>` when no trigger words exist |
| `lora_prompt` / `lora_metadata` | Prefix incoming text, for chaining nodes |

Optional inputs `lora_stack` / `lora_prompt` / `lora_metadata` let you chain several
stack nodes together.

### LoRA Stack Apply

| Input | Notes |
|---|---|
| `model` | Where the stack is applied |
| `clip` (optional) | Without it, CLIP weights are ignored |
| `lora_stack` (optional) | From this pack or any node that outputs `LORA_STACK` |
| `bypass` | Pass model/CLIP through untouched |
| `weight_multiplier` | Scale every weight in the stack at once |
| `apply_clip` | Off = never touch the text encoder |

Outputs `MODEL`, `CLIP`, `INFO` (a per-LoRA log of what was applied or skipped).

### LoRA Stack Apply (Anima Remap)

Everything above, plus:

| Input | Notes |
|---|---|
| `enable_remap` | Off = plain applier (no remapping) |
| `target_model` | `Auto (detect)` / `Anima (28 layers)` / `Anima 2.9B (40 layers)` / `Anima 3.8B (52 layers)` |
| `source_model` | Which generation the LoRA itself was trained on |
| `remap_mode` | `Keys only (recommended)` / `Extend to new layers (experimental)` |
| `extend_strength` | Only used by Extend mode; `1.0` copies the source delta as-is |

Outputs `MODEL`, `CLIP`, `REMAP_INFO`, for example:

```
target: Anima 2.9B (40 layers)
applied: 1 lora(s)
zzz_remielle_anima_v2-rift1000: 28->40 remapped (840 moved, 0 dropped)  [w=0.85, clip=0]
```

---

## Anima cross-generation compatibility

Anima generations are **depth expansions**, not retrains: 12 new blocks are spliced into
the middle of the previous layout.

```
28 layers (Anima base):  0  1  2  3  4  5 ...
40 layers (Anima 2.9B):  0  1 [2] 3  4 [5] 6  7 [8] ...   [n] = newly inserted
                         ^  ^     ^  ^     ^  ^
                         0  1     2  3     4  5            <- old blocks shifted
```

A LoRA key says `blocks.2`. On a 40-layer model `blocks.2` **does exist** (it is an inserted
block), so nothing errors — the deltas just land on the wrong layers. This node rewrites the
LoRA's block indices before applying it.

**Two dropdowns, on purpose.** `target_model` is usually detected correctly from the
connected model, but `source_model` is inferred from the LoRA's highest block index — which
mis-reads adapters that only touch early layers. When in doubt, set it by hand.

**Two remap modes**

| Mode | Effect |
|---|---|
| `Keys only` | Indices are moved; the 12 newly inserted layers get no delta from this LoRA, so its effect is weaker than on the original model |
| `Extend` | Additionally copies each source block's delta onto the layers inserted from it (scaled). Best effort — those layers did not exist when the LoRA was trained |

**Direction is one-way.** Older to newer only (`28→40`, `28→52`, `40→52`). A LoRA that needs
*more* layers than the model has raises an error instead of silently applying half of itself.

**Coexistence.** Two community plugins (`ComfyUI-Anima-2.9B-loraPatch`,
`ComfyUI-Anima-LoRA-ControlNet-Patch`) patch `comfy.lora.load_lora` globally. This node does
not patch anything — it rewrites its own copy of the state dict, so both can be installed
side by side without double-remapping. You only need one of them anyway.

---

## Language

Node titles, categories, descriptions and tooltips follow the **system language**
(Chinese or English). The picker dialog follows the **browser language**.

Force a language with an environment variable before starting ComfyUI:

```bash
OPNODES_LANG=zh    # or en
```

Dropdown *values* (`Auto (detect)`, `Anima 2.9B (40 layers)`, …) are intentionally **not**
translated: ComfyUI stores the selected value inside the workflow, so translating them would
make a workflow saved under one language unreadable under another.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Picker button missing, raw `trigger_selector_*` fields visible | The frontend extension did not load. Hard-refresh (Ctrl+Shift+R); if it persists, check the browser console for `[LoRAStackAutoTriggers]` lines |
| Trigger words are empty | The LoRA has no Civitai entry and no `ss_tag_frequency` metadata. Tick `force_fetch` once, or type words by hand in the picker |
| Wrong words after replacing a LoRA file | The cache is keyed by LoRA name. Toggle `force_fetch` to refresh, or delete `loras_tags.json` |
| Grey / black image with no error | A NaN weight reached the applier. Current versions treat NaN as 0 and skip that entry — update if you are on an older build |
| Anima LoRA looks weak on 2.9B / 3.8B | Expected in `Keys only` mode (the 12 new layers get nothing). Try `Extend` with strength `0.3`–`0.8` |

---

## Credits

- Trigger-word extraction is ported from
  [idrirap/ComfyUI-Lora-Auto-Trigger-Words](https://github.com/idrirap/ComfyUI-Lora-Auto-Trigger-Words)
  (MIT, © konohana) — itself a fork of
  [Extraltodeus/LoadLoraWithTags](https://github.com/Extraltodeus/LoadLoraWithTags).
- The stacked-loader layout follows
  [jakechai/ComfyUI-JakeUpgrade](https://github.com/jakechai/ComfyUI-JakeUpgrade).
- The Anima block-mapping tables are the ones community-verified by
  [sparklingcoffee777/ComfyUI-Anima-2.9B-loraPatch](https://github.com/sparklingcoffee777/ComfyUI-Anima-2.9B-loraPatch)
  and [INuBq8/ComfyUI-Anima-LoRA-ControlNet-Patch](https://github.com/INuBq8/ComfyUI-Anima-LoRA-ControlNet-Patch)
  (exhaustive `torch.equal` verification). No code from those GPL projects is used here.

## License

This pack is MIT. Note that **Anima models themselves are non-commercial**, and remapped
LoRA files produced from them count as derivatives under the CircleStone Labs license.
Images you generate can still be used commercially.
