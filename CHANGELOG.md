# Changelog

All notable changes to **ComfyUI-LoRAStackAutoTriggers** (OPNodes · LoRAStackAutoTriggers).
SemVer: new node = minor, bug fix = patch, node-key change = major.

> Node **keys** are a permanent contract (`LoRA Stack Auto Triggers`, `LoRAStackApplyBasic`,
> `LoRAStackApply`) — they live inside users' workflow JSON and are never renamed.

## [1.2.2] — unreleased

Packaging and branding only — **no functional changes**, no workflow needs editing.

### Added
- `LICENSE` file (full MIT text + third-party notices; Impact-Pack-independent).

### Changed
- `pyproject.toml`: `license` normalized to `{ file = "LICENSE" }` (the form Comfy Registry
  documents), `DisplayName` gains the brand prefix → `OPNodes · LoRAStackAutoTriggers`,
  version → `1.2.2`.
- i18n category → `OPNodes/LoRA` (category is UI-only and never stored in workflows, so this
  is safe to change).
- `README.md` / `README.zh.md`: OPNodes series banner + sister-package pointer.

## [1.2.1] — 2026-10-30

### Changed
- The published package now ships `LICENSE`; version bump only, no functional changes.

## [1.2.0] — 2026-10-30

### Added
- **LoRA Stack Apply** — plain applier for any `LORA_STACK` (no third-party "apply LoRA stack"
  node needed).
- **LoRA Stack Apply (Anima Remap)** — applies the stack and remaps block indices across Anima
  generations (28 = Anima, 40 = Anima 2.9B, 52 = Anima 3.8B), one-way only, with
  `Keys only` / `Extend to new layers` modes.
- Bilingual UI (system language, `OPNODES_LANG` override).

### Fixed
- NaN weights are treated as 0 and skipped instead of poisoning the model (black/grey output).
- SDXL `input_blocks` / `output_blocks` keys are no longer mistaken for Anima blocks.
- Socket order is `model → clip → lora_stack` (required ports always render before optional ones).

## [1.1.0] — 2026-10-30

### Added
- Visual trigger-word picker: Civitai variants, per-segment toggles, mouse text selection,
  searchable training tags, `28 layers · N variants` summary badge.

## [1.0.0] — 2026-08-04

### Added
- **LoRA Stack Auto Triggers**: 4 slots, model/CLIP weights, trigger words fetched from Civitai
  and from `ss_tag_frequency` metadata, outputs `LORA_STACK` / `LORA_PROMPT` / `LORA_MetaData`.
