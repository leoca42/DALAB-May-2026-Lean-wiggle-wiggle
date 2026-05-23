"""
Perturbation registry — single source of truth.

Every perturbation has a unique ``name`` and exactly one ``Perturbation``
entry. The implementation callable, the truth-propagation rules, the human
description, and the layer tag all travel together. Other modules consume
this list via ``TRANSFORMS`` and ``PROPAGATION_RULES`` (dict views over the
list) — they should never define their own copies.

Adding a new perturbation requires exactly two things:

  1. A function in ``wiggle.transforms.<layer>`` with the standard signature
     ``(sig: str, type_str: str) -> tuple[str, str] | None``.
  2. One ``Perturbation(...)`` entry below.

The module-level assertion guarantees ``TRANSFORMS`` and ``PROPAGATION_RULES``
have identical key sets and that every entry has a complete propagation
table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from wiggle.transforms import bounds, connectives, logical, quantifiers, typeclass

__all__ = [
    "Perturbation",
    "PERTURBATIONS",
    "TRANSFORMS",
    "PROPAGATION_RULES",
    "ANCHOR_TRUTH",
    "TruthValue",
]


# ── Types ─────────────────────────────────────────────────────────────────────

TruthValue = Literal["true", "false", "unknown"]
"""Three-valued truth annotation. Stored as a string for JSONL friendliness."""

ANCHOR_TRUTH: TruthValue = "true"
"""All anchors come from Mathlib (proven theorems) so they start as ``true``."""

TransformFn = Callable[[str, str], "tuple[str, str] | None"]
"""Signature every transform must implement."""


@dataclass(frozen=True)
class Perturbation:
    """One perturbation, with everything anyone needs to use it."""

    name: str
    """Stable identifier — used in JSONL records and as the dict key."""

    fn: TransformFn
    """Transform callable; returns ``None`` to mean "does not apply"."""

    propagation: dict[TruthValue, TruthValue]
    """How ``is_true`` evolves: ``{anchor_truth: variant_truth}``."""

    description: str
    """One-line human description."""

    layer: Literal["logical", "connective", "quantifier", "typeclass", "bounds"]
    """Family of the perturbation, for grouping in reports."""


# ── The canonical list ────────────────────────────────────────────────────────
# Order is meaningful: it determines the order of demo output. Group by layer.

PERTURBATIONS: list[Perturbation] = [
    # ── Layer 1: logical structure (Lean tactics) ────────────────────────────
    Perturbation(
        name="negate",
        fn=logical.negate,
        propagation={"true": "false", "false": "true", "unknown": "unknown"},
        description="Negate the full statement (¬P). Always False from a True anchor.",
        layer="logical",
    ),
    Perturbation(
        name="contrapose",
        fn=logical.contrapose,
        propagation={"true": "true", "false": "false", "unknown": "unknown"},
        description="Contrapositive (¬Q → ¬P). Logically equivalent, True.",
        layer="logical",
    ),
    Perturbation(
        name="converse",
        fn=logical.converse,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Converse (Q → P). Truth unknown.",
        layer="logical",
    ),
    Perturbation(
        name="inverse",
        fn=logical.inverse,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Inverse (¬P → ¬Q). Equivalent to converse, not to original.",
        layer="logical",
    ),
    Perturbation(
        name="drop_unused_hyp",
        fn=logical.drop_unused_hyp,
        propagation={"true": "true", "false": "unknown", "unknown": "unknown"},
        description="Strip Prop-valued hypotheses not used by the goal. True.",
        layer="logical",
    ),
    # ── Layer 2: connective rewriting (Lean tactics) ─────────────────────────
    Perturbation(
        name="de_morgan_rewrite",
        fn=connectives.de_morgan_rewrite,
        propagation={"true": "true", "false": "false", "unknown": "unknown"},
        description=(
            "Equivalence-preserving connective rewriting via simp only "
            "[not_and_or, not_or, not_forall, not_exists, imp_iff_not_or, "
            "and_imp, not_not]."
        ),
        layer="connective",
    ),
    # ── Layer 3: quantifier scope (Python + Lean type-check) ─────────────────
    Perturbation(
        name="quantifier_swap",
        fn=quantifiers.quantifier_swap,
        propagation={"true": "unknown", "false": "false", "unknown": "unknown"},
        description=(
            "Swap ∀x ∃y → ∃y ∀x at the head of the statement. Strictly stronger "
            "claim; usually false."
        ),
        layer="quantifier",
    ),
    # ── Layer 4: typeclass mutations (Python + Lean type-check) ──────────────
    Perturbation(
        name="tc_weaken_hyp",
        fn=typeclass.tc_weaken_hyp,
        propagation={"true": "unknown", "false": "false", "unknown": "unknown"},
        description="Weaken typeclass in hypothesis (parent class). Unknown.",
        layer="typeclass",
    ),
    Perturbation(
        name="tc_strengthen_hyp",
        fn=typeclass.tc_strengthen_hyp,
        propagation={"true": "true", "false": "unknown", "unknown": "unknown"},
        description="Strengthen typeclass in hypothesis (child class). True.",
        layer="typeclass",
    ),
    Perturbation(
        name="tc_strengthen_conc",
        fn=typeclass.tc_strengthen_conc,
        propagation={"true": "unknown", "false": "false", "unknown": "unknown"},
        description="Strengthen typeclass in conclusion (child class). Unknown.",
        layer="typeclass",
    ),
    Perturbation(
        name="tc_weaken_conc",
        fn=typeclass.tc_weaken_conc,
        propagation={"true": "true", "false": "unknown", "unknown": "unknown"},
        description="Weaken typeclass in conclusion (parent class). True.",
        layer="typeclass",
    ),
    # ── Layer 5: bound mutations (regex) ─────────────────────────────────────
    Perturbation(
        name="flip_bound",
        fn=bounds.flip_bound,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Flip inequality direction (< ↔ >, ≤ ↔ ≥). Truth unknown.",
        layer="bounds",
    ),
    Perturbation(
        name="bound_tighter",
        fn=bounds.bound_tighter,
        propagation={"true": "unknown", "false": "false", "unknown": "unknown"},
        description="Tighten numeric bound by ±1 in the tighter direction. Unknown.",
        layer="bounds",
    ),
]


# ── Dict views, derived from the canonical list ───────────────────────────────

TRANSFORMS: dict[str, TransformFn] = {p.name: p.fn for p in PERTURBATIONS}

PROPAGATION_RULES: dict[str, dict[TruthValue, TruthValue]] = {
    p.name: p.propagation for p in PERTURBATIONS
}


# ── Internal consistency (catches typos at import time) ───────────────────────

assert len({p.name for p in PERTURBATIONS}) == len(
    PERTURBATIONS
), "Duplicate perturbation names in PERTURBATIONS"

_TRUTH_KEYS = {"true", "false", "unknown"}
for _p in PERTURBATIONS:
    assert set(_p.propagation.keys()) == _TRUTH_KEYS, (
        f"Perturbation {_p.name!r} propagation must have keys "
        f"{_TRUTH_KEYS}; got {set(_p.propagation)}"
    )
    assert set(_p.propagation.values()) <= _TRUTH_KEYS, (
        f"Perturbation {_p.name!r} propagation has non-truth values: "
        f"{set(_p.propagation.values()) - _TRUTH_KEYS}"
    )

del _p
