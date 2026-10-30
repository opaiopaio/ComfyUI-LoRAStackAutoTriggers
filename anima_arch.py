"""Anima block-architecture tables (pure data + pure functions).

Anima ships in several transformer-block-count variants, each a depth
expansion of the previous one: new blocks are spliced into specific
positions of an otherwise byte-identical, relocated copy of every block
from the smaller variant.

    28 layers (Anima base / anima-preview, e.g. anima_aestheticV11)
      -> insert 12 new blocks -> 40 layers (Anima 2.9B)
        -> insert 12 new blocks -> 52 layers (Anima 3.8B / "Pro52")

This module has no ComfyUI / torch dependency so it can be unit-tested
standalone.

Provenance of the two insertion tables (verified with real checkpoints by
three independent community projects; the tables themselves are facts, not
code):
  - 28 -> 40: direct tensor comparison (all 28 original blocks bit-identical,
    max|diff| == 0), re-verified with torch.equal() elsewhere.
  - 40 -> 52: exhaustive all-pairs torch.equal() search over every block
    (zero collisions, zero misses), matching an independent implementation.
  - 28 -> 52 is never hand-written: composed from the two steps above so it
    cannot drift.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Known architectures
# --------------------------------------------------------------------------- #
BLOCK_COUNT_ANIMA = 28
BLOCK_COUNT_29B = 40
BLOCK_COUNT_38B = 52

ANIMA_BLOCK_COUNTS: Tuple[int, ...] = (
    BLOCK_COUNT_ANIMA,
    BLOCK_COUNT_29B,
    BLOCK_COUNT_38B,
)

# User-facing labels for the dropdowns (Auto first, then named models).
AUTO_LABEL = "Auto (detect)"

MODEL_CHOICES = [
    AUTO_LABEL,
    "Anima (28 layers)",
    "Anima 2.9B (40 layers)",
    "Anima 3.8B (52 layers)",
]

_CHOICE_TO_COUNT = {
    "Anima (28 layers)": BLOCK_COUNT_ANIMA,
    "Anima 2.9B (40 layers)": BLOCK_COUNT_29B,
    "Anima 3.8B (52 layers)": BLOCK_COUNT_38B,
}

COUNT_TO_LABEL = {
    BLOCK_COUNT_ANIMA: "Anima",
    BLOCK_COUNT_29B: "Anima 2.9B",
    BLOCK_COUNT_38B: "Anima 3.8B",
}

# Indices of the 12 blocks inserted when expanding 28 -> 40 layers.
INSERTED_28_40: Tuple[int, ...] = (2, 5, 8, 11, 14, 17, 21, 24, 27, 30, 33, 36)

# Indices (in 40-layer numbering) inserted when expanding 40 -> 52 layers.
INSERTED_40_52: Tuple[int, ...] = (3, 7, 11, 15, 19, 23, 27, 31, 35, 39, 43, 47)


# --------------------------------------------------------------------------- #
# Mapping construction
# --------------------------------------------------------------------------- #
def _kept_positions(old_count: int, insertion_positions: Tuple[int, ...]) -> List[int]:
    """Slots of the expanded layout that are NOT newly inserted, ascending.

    These are, in order, the destination slots of source indices 0, 1, 2, ...
    """
    inserted = set(insertion_positions)
    new_count = old_count + len(inserted)
    return [i for i in range(new_count) if i not in inserted]


def _build_expansion_map(old_count: int, insertion_positions: Tuple[int, ...]) -> Dict[int, int]:
    kept = _kept_positions(old_count, insertion_positions)
    assert len(kept) == old_count, (
        f"inconsistent table: expected {old_count} kept slots, got {len(kept)}"
    )
    return {source: dest for source, dest in enumerate(kept)}


MAP_28_40: Dict[int, int] = _build_expansion_map(28, INSERTED_28_40)
MAP_40_52: Dict[int, int] = _build_expansion_map(40, INSERTED_40_52)
# Composed, never hand-written.
MAP_28_52: Dict[int, int] = {s: MAP_40_52[d] for s, d in MAP_28_40.items()}

assert len(MAP_28_40) == 28 and len(set(MAP_28_40.values())) == 28
assert len(MAP_40_52) == 40 and len(set(MAP_40_52.values())) == 40
assert len(MAP_28_52) == 28 and len(set(MAP_28_52.values())) == 28

_FORWARD_MAPS: Dict[Tuple[int, int], Dict[int, int]] = {
    (28, 40): MAP_28_40,
    (28, 52): MAP_28_52,
    (40, 52): MAP_40_52,
}


def get_mapping(source_count: Optional[int], target_count: Optional[int]) -> Optional[Dict[int, int]]:
    """source_idx -> target_idx for this (source, target) pair.

    Returns None when:
      - either count is unknown,
      - source == target (nothing to remap),
      - the pair is not a known expansion step. Downgrades (source > target)
        are deliberately unsupported: the blocks a larger adapter needs
        simply do not exist on a smaller host.
    """
    if not source_count or not target_count:
        return None
    if source_count == target_count:
        return None
    return _FORWARD_MAPS.get((source_count, target_count))


def inserted_sources(mapping: Dict[int, int], new_count: int) -> Dict[int, int]:
    """{inserted_target_idx: source_idx} derived from a mapping table.

    Each newly-inserted block was deep-copied from its immediate predecessor
    slot at initialization, so the source is the nearest kept slot below it.
    Derived rather than hand-listed, so the composed 28->52 case is covered
    without a third table. Used by the "extend" remap mode.
    """
    if not mapping:
        return {}
    kept = sorted(mapping.values())
    base_of = {t: b for b, t in enumerate(kept)}
    out: Dict[int, int] = {}
    for t in range(new_count):
        if t in base_of:
            continue
        prev = [k for k in kept if k < t]
        if prev:
            out[t] = base_of[prev[-1]]
    return out


def source_to_inserted(mapping: Dict[int, int], new_count: int) -> Dict[int, List[int]]:
    """Inverse of inserted_sources(): {source_idx: [inserted_target_idx, ...]}."""
    out: Dict[int, List[int]] = {}
    for target, source in inserted_sources(mapping, new_count).items():
        out.setdefault(source, []).append(target)
    for targets in out.values():
        targets.sort()
    return out


def bucket_block_count(observed_max_index_plus_one: Optional[int]) -> Optional[int]:
    """Smallest known Anima architecture that could structurally contain this
    many layers, or None if it exceeds every known architecture.

    Deliberately permissive about partial coverage: an adapter need not touch
    every layer of its source architecture; only the highest index matters.
    (Known caveat: an adapter from a larger generation that happens to touch
    only early layers cannot be told apart from a smaller generation -- which
    is exactly why the node exposes manual overrides.)
    """
    if not observed_max_index_plus_one or observed_max_index_plus_one <= 0:
        return None
    for count in ANIMA_BLOCK_COUNTS:
        if observed_max_index_plus_one <= count:
            return count
    return None


def resolve_dropdown(choice: str) -> Optional[int]:
    """Dropdown label -> block count, or None for Auto / unknown labels."""
    return _CHOICE_TO_COUNT.get(choice or "")


def describe_count(count: Optional[int]) -> str:
    if not count:
        return "unknown"
    return f"{COUNT_TO_LABEL.get(count, 'unknown')} ({count} layers)"


def describe_conversion(source: Optional[int], target: Optional[int]) -> str:
    if not source or not target:
        return "gen unknown"
    if source == target:
        return f"same gen ({source} layers, no remap)"
    mapping = get_mapping(source, target)
    if mapping is None:
        return f"{source} -> {target} (unsupported)"
    return f"{source} -> {target} remapped"
