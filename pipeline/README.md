# Pipeline (in-progress)

This is where the scaling work lives: turning the 10-theorem hackathon demo
into a real pipeline that can perturb 200k Mathlib theorem statements (see
`../docs/Final Design Doc.md`).

## Current state

| File | Status |
|---|---|
| `perturb.ipynb` | **Seed.** Has plumbing for loading Mathlib statements from HuggingFace, a `TRANSFORMS` registry, truth-propagation rules, and an `apply_perturbation_chains` function. Does **not** yet run end-to-end, parallelise, deduplicate, or push results back to HuggingFace. |

## Planned work

1. **Parallel runner** — `multiprocessing.Pool` (or persistent Lean server) over batched anchors, each batch with its own temp Lean file to avoid race conditions.
2. **Deduplication** — on `(anchor_type, variant_type)` before writing.
3. **Checkpointing** — periodic flush to JSONL / HuggingFace push (default every 50 batches per the Final Design Doc).
4. **CLI entry point** — `python -m pipeline.run --batch-size 32 --max-chain-depth 4` style, so it can be invoked outside a notebook.
5. **Evaluation hooks** — per-pair embedding cosine similarity, distinctness verification (`decide` / `aesop`), dataset-level diversity metrics.
