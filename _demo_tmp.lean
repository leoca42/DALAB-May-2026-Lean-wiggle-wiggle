import Wiggle

lemma wiggle_demo  : ∃ m n, m + n ≠ n + m := by
  negate_state
  extract_goal
  sorry
