import os
import re
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_lean_and_extract(lean_code: str, tmp_filename: str, label: str) -> None:
    tmp_path = os.path.join(PROJECT_DIR, tmp_filename)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(lean_code)

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
            print(f"{label} goal:")
            print(match.group(0))
        else:
            print(f"Could not find extracted {label.lower()} goal. Raw Lean output:")
            print(output)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


LEAN_CODE = """\
import Negate

-- Generalization by weakening hypotheses.
-- The tactic removes Prop hypotheses that are not used by the final goal.
lemma to_generalize (x : ℝ) (h_unused : True) :
    HasDerivAt Real.exp (Real.exp x) x := by
  generalize_statement_by_weakening_hypotheses
  extract_goal
  sorry
"""


if __name__ == "__main__":
    run_lean_and_extract(
        LEAN_CODE,
        "_generalize_tmp.lean",
        "Generalized",
    )
