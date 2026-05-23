"""
Lean execution backend.

Wraps ``lake env lean`` and the ``extract_goal`` trick used by the
tactic-driven perturbations. Centralised here so that:

  1. There is one place to swap in a faster Lean server later (the docs/Final
     Design Doc.md flags Lean elaboration as the main bottleneck).
  2. Tests can monkeypatch ``run_lean`` to mock Lean output and avoid the 5–30s
     compile cost for every unit test.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

__all__ = [
    "get_project_root",
    "run_lean",
    "compile_lean",
    "extract_goal",
]


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """Return the Lake project root (directory containing ``Wiggle.lean``).

    Walks up from this file. Cached because the answer never changes within a
    single process.
    """
    cur = Path(__file__).resolve()
    while cur != cur.parent:
        if (cur / "Wiggle.lean").exists():
            return cur
        cur = cur.parent
    raise RuntimeError(
        "Could not locate Wiggle.lean walking up from " + str(Path(__file__))
    )


def run_lean(code: str, timeout: int = 300) -> str:
    """Run ``lake env lean`` on the given source and return combined stdout+stderr.

    Each call writes to a unique temp file under the project root so concurrent
    callers don't clobber each other. The file is removed on the way out.
    """
    project_root = get_project_root()
    # NamedTemporaryFile with delete=False so subprocess can read it after we
    # close the handle. We remove it explicitly in the finally clause.
    fd, path = tempfile.mkstemp(
        prefix="_wiggle_", suffix=".lean", dir=project_root
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        result = subprocess.run(
            ["lake", "env", "lean", path],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout + result.stderr
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def compile_lean(variant_sig: str, variant_type: str) -> bool:
    """Return True iff ``example : <variant_type> := by sorry`` type-checks.

    Used as a validity oracle: we accept any well-formed Lean statement
    regardless of provability. ``variant_sig`` is currently unused but kept
    in the signature so the call site reads naturally.
    """
    del variant_sig  # reserved for future per-theorem context
    output = run_lean(
        "import Mathlib\n\nexample : " + variant_type + " := by sorry\n"
    )
    return "error:" not in output


# extract_goal scrapes lines that look like:
#   theorem wiggle_demo.extracted_1_1 {i j : N} : body := sorry
_EXTRACTED_RE = re.compile(r"^theorem .*extracted.*$", re.MULTILINE)


def extract_goal(tactic: str, type_str: str) -> tuple[str, str] | None:
    """Run a Lean snippet that applies ``tactic`` then ``extract_goal``.

    Returns ``(variant_sig, variant_type)`` if the goal extraction succeeded,
    otherwise ``None``.

    The snippet shape:

        import Mathlib
        import Wiggle

        example : <type_str> := by
          <tactic>
          extract_goal
          sorry
    """
    code = (
        "import Mathlib\n"
        "import Wiggle\n\n"
        f"example : {type_str} := by\n"
        f"  {tactic}\n"
        "  extract_goal\n"
        "  sorry\n"
    )
    output = run_lean(code)
    m = _EXTRACTED_RE.search(output)
    if m is None:
        return None
    full_statement = m.group(0)
    without_proof = full_statement.rsplit(":= sorry", 1)[0].strip()
    parts = without_proof.split(" : ", 1)
    if len(parts) != 2:
        return None
    variant_sig, variant_type = parts
    return variant_sig.strip(), variant_type.strip()
