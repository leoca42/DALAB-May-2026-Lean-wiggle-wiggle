import Wiggle

lemma wiggle_demo  : ∃ R inst, IsDomain R ∧ ¬IsDomain (Polynomial R) := by
  negate_state
  extract_goal
  sorry
