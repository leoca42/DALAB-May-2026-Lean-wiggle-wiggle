"""
Quantifier-level perturbations.

These do Python-side text substitution on the Lean type string, then use
``compile_lean`` as a validity oracle (same pattern as
``src/typeclass_mutate.py``). No new Lean tactic is required.
"""

from __future__ import annotations

import re

from wiggle.lean_runner import compile_lean

__all__ = ["quantifier_swap"]


# ── Bracket-aware comma scanner ───────────────────────────────────────────────
def _find_top_level_comma(s: str, start: int = 0) -> int:
    """Index of the first comma in ``s`` (from ``start``) that is not nested
    inside ``()``, ``[]``, ``{}``. Returns -1 if none.
    """
    depth = 0
    i = start
    while i < len(s):
        c = s[i]
        if c in "({[":
            depth += 1
        elif c in ")}]":
            depth = max(0, depth - 1)
        elif c == "," and depth == 0:
            return i
        i += 1
    return -1


# ── ∀ then ∃ detector ─────────────────────────────────────────────────────────
# Match a leading ∀, then the binders up to (but not including) the next
# top-level comma. We then check that the next non-whitespace token after the
# comma is ∃.
_FORALL_RE = re.compile(r"^\s*∀\s+", re.UNICODE)
_EXISTS_RE = re.compile(r"^\s*∃\s+", re.UNICODE)


def quantifier_swap(sig: str, type_str: str) -> tuple[str, str] | None:
    """Rewrite ``∀ x_…, ∃ y_…, body`` as ``∃ y_…, ∀ x_…, body``.

    Strictly stronger than the original (∃∀ → ∀∃ is the valid direction), so
    the variant is usually false. Returns ``None`` if:

      * the statement does not start with a ∀ … , ∃ … alternation,
      * the swapped form fails to type-check against Mathlib (the validity
        oracle, identical to the one used by ``typeclass_mutate``).
    """
    fa = _FORALL_RE.match(type_str)
    if fa is None:
        return None

    # Find the comma terminating the ∀ binder block.
    fa_end = _find_top_level_comma(type_str, start=fa.end())
    if fa_end == -1:
        return None
    fa_binders = type_str[fa.end() : fa_end].strip()
    if not fa_binders:
        return None

    after_fa = type_str[fa_end + 1 :]
    ex = _EXISTS_RE.match(after_fa)
    if ex is None:
        return None

    # Find the comma terminating the ∃ binder block.
    ex_end_in_after = _find_top_level_comma(after_fa, start=ex.end())
    if ex_end_in_after == -1:
        return None
    ex_binders = after_fa[ex.end() : ex_end_in_after].strip()
    body = after_fa[ex_end_in_after + 1 :].strip()
    if not ex_binders or not body:
        return None

    swapped = f"∃ {ex_binders}, ∀ {fa_binders}, {body}"

    # Reject no-ops (binders alpha-equivalent already, etc.)
    if swapped.strip() == type_str.strip():
        return None

    # Validity oracle.
    if not compile_lean(sig, swapped):
        return None

    return sig, swapped
