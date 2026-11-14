# Changelog

All notable changes to **ComfyUI-LoRAStackAutoTriggers** (OPNodes · LoRAStackAutoTriggers).
SemVer: new node = minor, bug fix = patch, node-key change = major.

> Node **keys** are a permanent contract (`LoRA Stack Auto Triggers`, `LoRAStackApplyBasic`,
> `LoRAStackApply`) — they live inside users' workflow JSON and are never renamed.

## [1.2.6] — 2026-11-15

### Changed
- Language override is now a `lang.txt` file in the package folder instead of an environment
  variable, and the Windows UI-language probe no longer uses FFI. Removes the
  `python_environment_manipulation` finding from the registry scanner.

## [1.2.5] — 2026-11-14

### Fixed
- `target_model` / `source_model` mismatch no longer silently disables remapping. The LoRA file is now
  the ground truth for its own generation, so manually setting `source_model` to the *model's*
  generation (the natural but wrong choice) is ignored with a note in `REMAP_INFO` instead of
  applying 28-layer weights onto 40-layer blocks. This looked exactly like "remap broke".
- `REMAP_INFO` now says "no remap needed (the file already matches …)" when the counts match, and
  reports when `source_model` was overridden by detection.
## [1.2.4] — unreleased

### Security
- `/lorastack/trigger_words` rejects any `lora_name` that is not in the installed LoRA list:
  no cache write, no hashing of an arbitrary path, no outbound request. Only real LoRA names
  can reach the cache/metadata code.
- The published package excludes `tests/` via `.comfyignore` (smaller zip, smaller scan surface).

### Changed
- version → `1.2.4`

## [1.2.3] — 2026-11-14

Same content as 1.2.2 — re-cut because that upload left the version record pending without a
package file.

## [1.2.2] — 2026-11-14

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
