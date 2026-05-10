import Wiggle

lemma wiggle_demo (n : ℕ) : n ≠ 0 → n > 0 := by
  converse
  extract_goal
  sorry
