"""
fix_tc_generalize_labels.py

Sets is_true = "unknown" for every record in demo_perturbations.jsonl
where perturbations_applied == ["tc_generalize"].

Rationale: weakening a typeclass hypothesis (e.g. AddCommMonoid -> AddMonoid)
produces a STRONGER claim (it must hold for more types), which may be false.
The _compile_lean check uses `sorry` and only verifies type-validity, not
provability, so the original True labels are incorrect.
"""

import json
from pathlib import Path

JSONL_PATH = Path(__file__).parent / "demo_perturbations.jsonl"


def fix(path: Path) -> None:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    changed = 0
    for r in records:
        if r.get("perturbations_applied") == ["tc_generalize"] and r.get("is_true") is True:
            r["is_true"] = "unknown"
            changed += 1

    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    print(f"Updated {changed} record(s) in {path}")


if __name__ == "__main__":
    fix(JSONL_PATH)
