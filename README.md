# DALAB-May-2026-Lean-wiggle-wiggle

We perturb Lean theorem statements to create similar but distinct statements. We do this using Lean tactics to perturb the Lean statements by:
- Finding a negation
- Finding a contrapositive
- Finding a converse
- Generalizing statements by removing hypotheses
- Strengthening or weakening the hypotheses or conclusions by going up or down the mathlib typeclass dependency tree
- Shifting numerical bounds in the statement

All peturbed Lean statements are checked by the Lean compiler to be valid Lean statements. However, many of them are mathematically incorrect. This project does not care whether a statement is true or not, just whether or not it is a valid Lean statement.

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

Next Steps:
- How can we make this faster?
- Are there more ways to perturb Lean statements we can add?
- Go train a text embedder usign contrastive loss (or something) with a dataset

# Fun Fact

This project is named "wiggle wiggle" as an alternate term for "perturbation", from a mysterious unnamed professor in the UW Math Department.
