"""
Corpus-level pipeline.

``run_pipeline`` iterates over a collection of anchor theorems and applies
random permutations of perturbations to each, emitting one record per
*successful intermediate* — i.e. a chain of length 4 yields up to 4 records,
one per prefix length, exactly like the original notebook prototype.

Inputs:

    anchors: iterable of dicts with keys ``signature`` and ``type`` (the
             HuggingFace dataset's column names). Extra keys pass through
             into the output record.

Outputs:

    Iterator of dicts shaped as JSONL records (see ``write_jsonl`` for the
    file-writing helper).
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path
from typing import Any, Iterable, Iterator

from wiggle.lean_runner import compile_lean
from wiggle.propagation import is_true
from wiggle.registry import TRANSFORMS

__all__ = ["run_pipeline", "write_jsonl"]


def run_pipeline(
    anchors: Iterable[dict[str, Any]],
    *,
    transforms: dict[str, Any] | None = None,
    n_permutations: int = 6,
    max_chain_depth: int | None = None,
    random_seed: int = 42,
    verify_compile: bool = True,
    verbose: bool = False,
) -> Iterator[dict[str, Any]]:
    """Yield one JSONL-shaped record per successfully-applied perturbation.

    For each anchor we sample ``n_permutations`` random orderings of the
    available perturbations. Each ordering is walked step-by-step; we stop
    as soon as a step returns ``None``, the output equals the input
    (no-op), or ``compile_lean`` rejects the variant.

    Truth is propagated via ``wiggle.propagation.is_true`` over the list of
    perturbation names applied so far — single source of truth with the
    registry, no parallel composition table here.

    Args:
        anchors: iterable of dicts with at least ``signature`` and ``type``.
        transforms: dict of name->callable. Defaults to the full registry.
        n_permutations: how many random orderings to try per anchor.
        max_chain_depth: chain length cap. ``None`` means "all transforms".
        random_seed: seed for the permutation sampler.
        verify_compile: run ``compile_lean`` on every produced variant. Off
            by default would be unsafe for the corpus — left on intentionally.
        verbose: print one line per anchor.
    """
    transforms = transforms or TRANSFORMS
    transform_names = list(transforms.keys())
    all_permutations = list(permutations(transform_names))
    rng = random.Random(random_seed)

    for anchor_idx, anchor in enumerate(anchors):
        anchor_sig = anchor.get("signature") or anchor.get("id", "")
        anchor_type = anchor["type"]
        k = min(n_permutations, len(all_permutations))
        sampled = rng.sample(all_permutations, k)

        if verbose:
            print(f"  [{anchor_idx}] {anchor_sig}: {k} permutations", flush=True)

        passthrough = {
            key: val for key, val in anchor.items() if key not in {"signature", "type"}
        }

        for perm in sampled:
            depth = len(perm) if max_chain_depth is None else min(max_chain_depth, len(perm))
            current_sig = anchor_sig
            current_type = anchor_type
            applied_so_far: list[str] = []

            for transform_name in perm[:depth]:
                fn = transforms[transform_name]
                result = fn(current_sig, current_type)
                if result is None:
                    break

                variant_sig, variant_type = result
                if (
                    variant_sig.strip() == current_sig.strip()
                    and variant_type.strip() == current_type.strip()
                ):
                    break

                if verify_compile and not compile_lean(variant_sig, variant_type):
                    break

                applied_so_far = applied_so_far + [transform_name]
                yield {
                    **passthrough,
                    "anchor_signature": anchor_sig,
                    "anchor_type": anchor_type,
                    "variant_signature": variant_sig,
                    "variant_type": variant_type,
                    "perturbations_applied": list(applied_so_far),
                    "chain_depth": len(applied_so_far),
                    "is_true": is_true(applied_so_far),
                    "perturbation_description": " -> ".join(applied_so_far),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                current_sig = variant_sig
                current_type = variant_type


def write_jsonl(records: Iterable[dict[str, Any]], path: str | Path) -> int:
    """Write ``records`` to ``path``, one JSON object per line. Returns count."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n
