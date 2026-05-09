import subprocess
import os
import re

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

LEAN_CODE = """\
import Wiggle

-- Real.hasDerivAt_exp: contrapositive
lemma to_contrapose (x : ℝ) : HasDerivAt Real.exp (Real.exp x) x := by
  contrapositive
  extract_goal
  sorry
"""

tmp_path = os.path.join(PROJECT_DIR, "_contrapose_tmp.lean")
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

    match = re.search(r"^theorem .*extracted.*$", output, re.MULTILINE)
    if match:
        print("Contrapositive goal:")
        print(match.group(0))
    else:
        print("Could not find extracted goal. Raw Lean output:")
        print(output)
finally:
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
