# DALAB-May-2026-Lean-wiggle-wiggle

## Repository layout

```
.                                        # Lake project root
├── Wiggle.lean                          # Lean tactics (negate, contrapose, converse, inverse, de_morgan_rewrite, ...)
├── lakefile.toml, lean-toolchain, ...   # Lake build config (must stay at root)
│
├── docs/                                # Design documents
│   └── Final Design Doc.md              # End-to-end project design and goals
│
├── src/                                 # Python library — the importable core
│   ├── bounds.py                        # Inequality / numeric bound perturbations
│   ├── typeclass_mutate.py              # Typeclass hierarchy perturbations
│   ├── instance_graph/                  # Mathlib instance dump + dependency builder
│   └── wiggle/                          # Phase 2: clean perturbation package
│       ├── lean_runner.py               # Single home for `lake env lean` invocations
│       ├── registry.py                  # Canonical PERTURBATIONS list (single source of truth)
│       ├── propagation.py               # Symbolic is_true / compose_truth
│       ├── chains.py                    # apply_chain — per-anchor chain runner
│       ├── pipeline.py                  # run_pipeline — corpus-level runner
│       └── transforms/                  # Per-layer transform implementations
│           ├── logical.py               #   negate, contrapose, converse, inverse, drop_unused_hyp
│           ├── connectives.py           #   de_morgan_rewrite
│           ├── quantifiers.py           #   quantifier_swap
│           ├── typeclass.py             #   tc_weaken_hyp, tc_strengthen_hyp, tc_*_conc
│           └── bounds.py                #   flip_bound, bound_tighter
│
├── pipeline/                            # CLI runners on top of src/wiggle/
│   ├── run_demo.py                      # 10 curated theorems → JSONL (replaces demo.ipynb)
│   └── run_hf_corpus.py                 # HuggingFace dataset slice → JSONL (replaces perturb.ipynb)
│
├── scripts/                             # Per-tactic CLI demos and one-off utilities
├── tests/                               # Unit tests (registry, propagation, new perturbations)
├── hackathon-demo/                      # Frozen artifacts from the hackathon presentation
└── data/                                # Generated dumps (gitignored)
```

See each subdirectory's `README.md` for details. The hackathon demo lives in
[`hackathon-demo/`](hackathon-demo/); the scaling roadmap is in
[`docs/Final Design Doc.md`](docs/Final%20Design%20Doc.md).

## Running

```bash
# Apply every registered perturbation to 10 curated theorems and write JSONL:
python pipeline/run_demo.py

# Apply perturbation chains to a slice of the HuggingFace Mathlib dataset:
python pipeline/run_hf_corpus.py --limit 10

# Run the Python unit tests (no Lean required):
python tests/test_registry.py
python tests/test_propagation.py
python tests/test_inverse.py
python tests/test_de_morgan.py
python tests/test_quantifier_swap.py
```

## What this project does

We perturb Lean theorem statements to create similar but distinct statements,
using a mix of Lean tactics and Python text manipulation. The current registry
exposes **13 perturbations** across 5 layers:

| Layer | Perturbations |
|---|---|
| Logical (Lean tactic) | `negate`, `contrapose`, `converse`, `inverse`, `drop_unused_hyp` |
| Connective rewriting (Lean tactic) | `de_morgan_rewrite` |
| Quantifier scope (Python + Lean validity oracle) | `quantifier_swap` |
| Typeclass mutation (Python + Lean validity oracle) | `tc_weaken_hyp`, `tc_strengthen_hyp`, `tc_strengthen_conc`, `tc_weaken_conc` |
| Bound mutation (regex) | `flip_bound`, `bound_tighter` |

All peturbed Lean statements are checked by the Lean compiler to be valid Lean statements. However, many of them are mathematically incorrect. This project does not care whether a statement is true or not, just whether or not it is a valid Lean statement.

# Examples:

Original Statement:

∀ {α : Type*} [inst : CommRing α] (a b : α), a * b = b * a

Weakening the Hypothesis:

∀ {α : Type*} [inst : Field α] (a b : α), a * b = b * a


# Similar Existing Work
- LeanDojo
    - This contained a way to perturb Lean proof states
- Lean Error Correction (from the UW Math AI Lab)
    - This also contained a way to perturb Lean proof states
- Synthetic Theorem Generation in Lean
    - This used LLMs to generate theorem statements, then used a proof checker to ensure validity

We found that existing work on synthetic Lean generation perturbed Lean proof states instead of the full theorem statements. Also, existing work uses LLMs to perturb statements, instead of using Lean’s tactics and typechecker to ensure validity.

# Uses

This project was inspired by two projects in the UW Math AI Lab, 
- [TheoremSearch](https://github.com/uw-math-ai/TheoremSearch)
- [Math2Vec](https://github.com/uw-math-ai/math2vec)

Theorem Search does retrieval of mathematically similar theorems from ArXiv and The Stacks Project by embedding all theorems/lemmas/corollaries with a text embedder then finding the closest theorems to a query in the embedding space.

Math2Vec is attempting to improve the text embedding capability over both natural language math statements and Lean math statements, looking towards improving the Theorem Search project with a better text embedder for mathematical theorems. To better fine-tune a text embedder over Lean, this project could use a synthetic dataset of perturbed Lean statements to run constrastive loss -esque training 

Examples of Lean Theorem Search
- LeanFinder
    - Theorem Search for Lean theorems & proof states

# Bottlenecks, Downsides, and Next Steps

Running our code on a laptop, it takes about 5-30s per perturbation, primarily because using the Lean tactic itself is slow. This seems to be slower than asking frontier LLMs to perturb Lean statements.
- However, our statements seem to be more accurate or be of a deeper perturbation than the LLM version. For example, our negations fully embed the negation into the statement using a Lean tactic, instead of jsut inserting a negation sign onto the statement.

This project has only suceeded in making a small demo dataset (perturbing 10 theorems at a time). To make a full dataset of perturbed Lean theorem statements, we would need to find a massive speedup in the perturbation process and build infrstaurcture for the dataset.

Next Steps:
- How can we make this faster?
- How do we scale our solution to compute for 200k theorems? (see FinalDesignDoc.md for more details)
- Are there more ways to perturb Lean statements we can add?
- Go train a text embedder usign contrastive loss (or something) with a dataset

# Fun Fact

This project is named "wiggle wiggle" as an alternate term for "perturbation", from a mysterious unnamed professor in the UW Math Department.

# Credits
- Vasily Ilin & Aristotle for the negate tactic
- Theodore Meek for some mathlib dependency generalization inspiration

