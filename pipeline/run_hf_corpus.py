#!/usr/bin/env python3
"""
run_hf_corpus.py — apply perturbation chains to a slice of a HuggingFace dataset.

Replaces the archived ``hackathon-demo/perturb.ipynb`` notebook with a plain
Python CLI that:

    1. pulls anchors from a HuggingFace dataset (``FrenzyMath/mathlib_informal_v4.19.0``
       by default),
    2. samples N random permutations of the registered perturbations per anchor,
    3. walks each permutation, emitting one record per successful intermediate,
    4. writes the result as JSONL.

This is the same loop as the seed notebook, refactored to use
``wiggle.pipeline.run_pipeline``.

Usage:
    python pipeline/run_hf_corpus.py --limit 10
    python pipeline/run_hf_corpus.py --indices 5145,181597,196429
    python pipeline/run_hf_corpus.py --indices 5145 --n-permutations 12 --max-chain-depth 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "Wiggle.lean").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wiggle.pipeline import run_pipeline, write_jsonl  # noqa: E402


DEFAULT_DATASET = "hf://datasets/FrenzyMath/mathlib_informal_v4.19.0/data.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "corpus_perturbations.jsonl"


def _parse_indices(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help=f"HF dataset URI (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSONL path. Default: {DEFAULT_OUTPUT.relative_to(PROJECT_ROOT)}",
    )
    src_grp = parser.add_mutually_exclusive_group()
    src_grp.add_argument(
        "--indices",
        type=_parse_indices,
        help="Comma-separated row indices to pull from the dataset.",
    )
    src_grp.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Take the first N rows of the dataset.",
    )
    parser.add_argument(
        "--n-permutations",
        type=int,
        default=6,
        help="Random orderings per anchor (default 6).",
    )
    parser.add_argument(
        "--max-chain-depth",
        type=int,
        default=4,
        help="Max chain length (default 4).",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Seed for the permutation sampler (default 42).",
    )
    parser.add_argument(
        "--no-verify-compile",
        action="store_true",
        help="Skip the per-variant Lean compile check (faster but unsafe).",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress per-anchor progress.")
    args = parser.parse_args(argv)

    # Lazy imports: keep startup fast for --help.
    try:
        import pandas as pd
    except ImportError:
        print(
            "error: pandas is required. Install with `pip install pandas`.",
            file=sys.stderr,
        )
        return 1

    print(f"Project root : {PROJECT_ROOT}")
    print(f"Dataset      : {args.dataset}")
    print(f"Output       : {args.output}")
    print(f"Permutations : {args.n_permutations}    Max chain depth: {args.max_chain_depth}")
    print(f"Verify compile: {not args.no_verify_compile}")
    print()

    # ── Pull anchors ─────────────────────────────────────────────────────────-
    print(f"Loading dataset... ", end="", flush=True)
    df = pd.read_json(args.dataset, lines=True)
    print(f"{len(df):,} rows")

    if args.indices:
        df = df.iloc[args.indices]
    elif args.limit is not None:
        df = df.iloc[: args.limit]

    if "signature" not in df.columns or "type" not in df.columns:
        print(
            "error: dataset must have 'signature' and 'type' columns; got "
            + ", ".join(df.columns),
            file=sys.stderr,
        )
        return 1

    df = df[["signature", "type"]].reset_index(drop=True)
    anchors = df.to_dict(orient="records")
    print(f"Running on {len(anchors)} anchors\n")

    # ── Run the pipeline ─────────────────────────────────────────────────────-
    args.output.parent.mkdir(parents=True, exist_ok=True)

    records = run_pipeline(
        anchors,
        n_permutations=args.n_permutations,
        max_chain_depth=args.max_chain_depth,
        random_seed=args.random_seed,
        verify_compile=not args.no_verify_compile,
        verbose=not args.quiet,
    )

    n_written = write_jsonl(records, args.output)
    print(f"\n{'═' * 70}")
    print(f"Wrote {n_written} records to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
