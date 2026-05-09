import Mathlib

-- tactic to negate state, from Aristotle:
open Lean Meta Elab Tactic in
elab "revert_all" : tactic => do
  let goals ← getGoals
  let mut newGoals : List MVarId := []
  for mvarId in goals do
    newGoals := newGoals.append [(← mvarId.revertAll)]
  setGoals newGoals

open Lean.Elab.Tactic in
macro "negate_state" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_all
    apply (by admit : ∀ {p : Prop}, ¬p → p)
    try (push Not; guard_goal_nums 1)
  )
)

-- Reverts only Prop-typed hypotheses, leaving type variables in context.
-- This lets contrapose! see a plain implication instead of a dependent ∀.
open Lean Meta Elab Tactic in
elab "revert_props" : tactic => do
  let goal ← getMainGoal
  let decl ← goal.getDecl
  let propFVars ← decl.lctx.foldlM (init := #[]) fun acc d => do
    if d.isImplementationDetail then return acc
    if ← isProp d.type then return acc.push d.fvarId
    else return acc
  let (_, newGoal) ← goal.revert propFVars (preserveOrder := true)
  replaceMainGoal [newGoal]

open Lean.Elab.Tactic in
macro "contrapositive" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_props
    try (simp only [← and_imp])
    contrapose
    simp only [not_and_or, not_le, not_lt]
    guard_goal_nums 1
  )
)
