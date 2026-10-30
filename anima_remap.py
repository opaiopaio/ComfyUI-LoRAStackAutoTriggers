"""Anima cross-generation LoRA remapping: key handling, detection, rewriting.

Strategy (self-contained, no monkeypatching):
    load the LoRA state dict -> rewrite its OWN block-index keys -> hand the
    rewritten dict to comfy.sd.load_lora_for_models.

This is deliberately different from the "patch" plugins in the wild, which
monkeypatch the global comfy.lora.load_lora and rewrite the model-side key
map. Rewriting our own state dict keeps this node free of global side effects
and immune to plugin ordering; and because the rewritten dict looks like a
native newer-generation LoRA, those plugins simply no-op if they happen to be
installed too.

Only diffusion-block keys are touched. The patterns are anchored so that
text-encoder keys (lora_te*) and the llm_adapter's own independent 6-block
structure are never modified. (Real Anima LoRAs do ship llm_adapter weights,
so this exclusion is a hard requirement, not a theoretical nicety.)
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, Optional, Tuple

from anima_arch import bucket_block_count, get_mapping, source_to_inserted

# --------------------------------------------------------------------------- #
# Key patterns
# --------------------------------------------------------------------------- #
# Anchored patterns, tried in order. Group 1 is the block index.
# Both spellings below were observed in real Anima LoRAs on disk.
_BLOCK_PATTERNS = (
    re.compile(r"^lora_unet_net_blocks_(\d+)_"),       # kohya, net_ spelling
    re.compile(r"^lora_unet_blocks_(\d+)_"),           # kohya (common Anima form)
    re.compile(r"^diffusion_model\.blocks\.(\d+)\."),  # peft / diffusers style
    re.compile(r"^blocks\.(\d+)\."),                   # bare lora key
)

# Fallback for unusual spellings; safe because excluded keys are filtered first.
_FALLBACK_PATTERN = re.compile(r"(_blocks_)(\d+)(_)")

_EXCLUDED_FRAGMENTS = ("llm_adapter",)                  # separate 6-block structure
_EXCLUDED_PREFIXES = ("lora_te", "lora_te1", "lora_te2")  # text encoder side

# "up" halves of a LoRA pair: scaling only these keeps the effective delta
# linear in the strength (delta = up @ down * alpha / rank).
_UP_SUFFIXES = (
    ".lora_up.weight", ".lora_up.bias",
    ".lora_B.weight", ".lora_B.bias",
)


def is_excluded_key(key: str) -> bool:
    if not isinstance(key, str):
        return True
    low = key.lower()
    if any(f in low for f in _EXCLUDED_FRAGMENTS):
        return True
    return any(low.startswith(p) for p in _EXCLUDED_PREFIXES)


def _find_block_match(key: str):
    """Return (match, group_index) for a block key, or (None, None)."""
    if is_excluded_key(key):
        return None, None
    for pat in _BLOCK_PATTERNS:
        m = pat.match(key)
        if m is not None:
            return m, 1
    m = _FALLBACK_PATTERN.search(key)
    if m is not None:
        return m, 2
    return None, None


def block_indices(keys: Iterable[str]) -> set:
    """Set of diffusion block indices referenced by these LoRA keys."""
    out = set()
    for key in keys:
        m, group = _find_block_match(key)
        if m is None:
            continue
        try:
            out.add(int(m.group(group)))
        except (TypeError, ValueError):
            continue
    return out


def block_count_of_keys(keys: Iterable[str]) -> Optional[int]:
    """max(block index) + 1, or None when no block keys are present."""
    idx = block_indices(keys)
    return (max(idx) + 1) if idx else None


def remap_key(key: str, mapping: Dict[int, int]) -> Optional[str]:
    """Rewrite one key's block index according to `mapping`.

    Returns:
        the (possibly unchanged) key -- no block index, excluded key, or the
            index has a mapping entry;
        None -- a block index was found but has no mapping entry, so the
            caller must drop this tensor.
    """
    m, group = _find_block_match(key)
    if m is None:
        return key
    try:
        idx = int(m.group(group))
    except (TypeError, ValueError):
        return key
    target = mapping.get(idx)
    if target is None:
        return None
    start, end = m.span(group)
    return key[:start] + str(target) + key[end:]


def remap_key_to(key: str, target_idx: int) -> Optional[str]:
    """Force a key's block index to `target_idx` (used by the extend mode)."""
    m, group = _find_block_match(key)
    if m is None:
        return None
    start, end = m.span(group)
    return key[:start] + str(target_idx) + key[end:]


# --------------------------------------------------------------------------- #
# fp8 safety
# --------------------------------------------------------------------------- #
def is_float8(t) -> bool:
    try:
        return t.is_floating_point() and t.element_size() == 1
    except Exception:
        return False


def computable(t):
    """Upcast fp8 tensors to float32 before arithmetic (PyTorch implements
    almost no fp8 math on CPU); other dtypes pass through untouched."""
    return t.float() if is_float8(t) else t


# --------------------------------------------------------------------------- #
# State-dict operations
# --------------------------------------------------------------------------- #
def remap_state_dict(sd: dict, mapping: Optional[Dict[int, int]]) -> Tuple[dict, dict]:
    """Rewrite every block key of `sd` (mode: keys only).

    Returns (new_sd, stats) with stats = {remapped, kept, dropped, source_count}.
    For a well-formed smaller-generation LoRA expanded forward, `dropped` is 0:
    every source block has a destination slot.
    """
    stats = {"remapped": 0, "kept": 0, "dropped": 0, "added": 0, "source_count": None}
    if not mapping:
        return sd, stats

    out = {}
    for key, value in sd.items():
        new_key = remap_key(key, mapping)
        if new_key is None:
            stats["dropped"] += 1
            continue
        if new_key != key:
            stats["remapped"] += 1
        else:
            stats["kept"] += 1
        out[new_key] = value

    stats["source_count"] = block_count_of_keys(sd.keys())
    return out, stats


def extend_state_dict(
    sd: dict,
    mapping: Optional[Dict[int, int]],
    target_count: Optional[int],
    strength: float = 0.5,
) -> Tuple[dict, dict]:
    """Remap forward, then also project each source block's delta onto the
    newly-inserted block(s) that were deep-copied from it.

    There is no "correct" answer for what a pre-expansion LoRA should do on
    layers that did not exist when it was trained -- this is a best-effort
    approximation. Only the "up" half of each pair is scaled, so the effective
    delta scales linearly with `strength` (1.0 == copy the source delta as-is).
    """
    stats = {"remapped": 0, "kept": 0, "dropped": 0, "added": 0, "source_count": None}
    if not mapping:
        return sd, stats

    out = {}
    for key, value in sd.items():
        new_key = remap_key(key, mapping)
        if new_key is None:
            stats["dropped"] += 1
            continue
        if new_key != key:
            stats["remapped"] += 1
        else:
            stats["kept"] += 1
        out[new_key] = value

    stats["source_count"] = block_count_of_keys(sd.keys())

    src_to_targets = source_to_inserted(mapping, target_count or 0)
    if not src_to_targets:
        return out, stats

    is_up = {k: k.endswith(_UP_SUFFIXES) for k in list(sd.keys())}
    for key, value in sd.items():
        m, group = _find_block_match(key)
        if m is None:
            continue
        try:
            src_idx = int(m.group(group))
        except (TypeError, ValueError):
            continue
        targets = src_to_targets.get(src_idx)
        if not targets:
            continue
        for t_idx in targets:
            new_key = remap_key_to(key, t_idx)
            if new_key is None:
                continue
            val = value
            if is_up.get(key) and strength != 1.0:
                val = computable(value) * float(strength)
            out[new_key] = val
            stats["added"] += 1

    return out, stats


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
def peek_lora_block_count(path: str) -> Optional[int]:
    """Block count read from the safetensors header only (no tensor data)."""
    if not path or not str(path).lower().endswith(".safetensors"):
        return None
    try:
        from safetensors import safe_open

        with safe_open(path, framework="pt", device="cpu") as f:
            return block_count_of_keys(list(f.keys()))
    except Exception:
        return None


def detect_lora_block_count(sd_keys: Iterable[str]) -> Optional[int]:
    """Observed layer count of a LoRA, bucketed to the smallest Anima
    architecture that could contain it."""
    return bucket_block_count(block_count_of_keys(sd_keys))


def detect_model_block_count(model_patcher) -> Optional[int]:
    """Layer count of the connected MODEL.

    Prefers the cheap route (the diffusion model's block ModuleList length) and
    falls back to scanning the state dict. Returns the raw observed count (not
    bucketed) so an unexpected layout stays visible in the log.
    """
    if model_patcher is None:
        return None

    inner = getattr(model_patcher, "model", None)
    dm = getattr(inner, "diffusion_model", None)
    blocks = getattr(dm, "blocks", None)
    if blocks is not None:
        try:
            n = len(blocks)
            if n > 0:
                return n
        except Exception:
            pass

    for getter in (
        lambda: model_patcher.model_state_dict(),
        lambda: dm.state_dict() if dm is not None else None,
        lambda: inner.state_dict() if inner is not None else None,
    ):
        try:
            sd = getter()
        except Exception:
            continue
        if not sd or not isinstance(sd, dict):
            continue
        count = block_count_of_keys(sd.keys())
        if count:
            return count
    return None
