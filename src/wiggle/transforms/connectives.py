"""
Connective rewriting — equivalence-preserving transforms based on De Morgan
and curry/uncurry style identities.

The current set of contrastive-training positives is just ``contrapose``.
``de_morgan_rewrite`` is the first non-trivial second source: a single Lean
``simp only`` invocation across a fixed set of named identities. We treat the
whole bundle as one perturbation because the individual rewrites are usually
chained together by Lean automatically — splitting them at the Python layer
would just create artificial step boundaries.
"""

from __future__ import annotations

from wiggle.lean_runner import extract_goal

__all__ = ["de_morgan_rewrite"]


def de_morgan_rewrite(sig: str, type_str: str) -> tuple[str, str] | None:
    """Apply De Morgan / connective rewrites to the statement.

    Logically equivalent to the original (truth-preserving). Returns ``None``
    if no rewrite makes progress, in which case the variant equals the input
    and would just clutter the dataset.

    Lean tactic ``de_morgan_rewrite`` lives in ``Wiggle.lean``; see it for the
    exact lemma set.
    """
    result = extract_goal("de_morgan_rewrite", type_str)
    if result is None:
        return None
    variant_sig, variant_type = result
    # No-op detection: ``simp only [...]`` can leave the goal untouched. We
    # only emit a record when the statement actually changed.
    if variant_sig.strip() == sig.strip() and variant_type.strip() == type_str.strip():
        return None
    if variant_type.strip() == type_str.strip():
        return None
    return variant_sig, variant_type
