import subprocess
import os
import re
import tempfile

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

LEAN_CODE = """\
import Negate

-- hasSum_geometric_of_lt_one negated
lemma to_negate {r : ℝ} (h₁ : 0 ≤ r) (h₂ : r < 1) :
    HasSum (fun n : ℕ ↦ r ^ n) (1 - r)⁻¹ := by
  negate_state
  extract_goal
  sorry
"""

tmp_path = os.path.join(PROJECT_DIR, "_negate_tmp.lean")
try:
    with open(tmp_path, "w") as f:
        f.write(LEAN_CODE)

    result = subprocess.run(
        ["lake", "env", "lean", tmp_path],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )

    output = result.stdout + result.stderr

    # extract_goal emits a "Try this:" info message with the negated goal
    match = re.search(r"^theorem .*extracted.*$", output, re.MULTILINE)
    if match:
        print("Negated goal:")
        print(match.group(0))
    else:
        print("Could not find extracted goal. Raw Lean output:")
        print(output)
finally:
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

