-- tactic to negate state, from Aristotle:
import Mathlib

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
