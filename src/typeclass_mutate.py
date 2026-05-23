"""
typeclass_mutate.py

Systematically changes the generalization level of a typeclass in a Lean 4
theorem statement using the Mathlib typeclass hierarchy.

Four perturbation methods:
  weaken_statement_by_strengthening_hypotheses   – [TC α] → [StrongerChild α]
  strengthen_statement_by_strengthening_conclusion – conclusion [TC α] → [StrongerChild α]
  weaken_statement_by_weakening_conclusion         – conclusion [TC α] → [WeakerParent α]
  generalize_statement_by_weakening_hypotheses     – [TC α] → [WeakerParent α]

Hierarchy sources (in order of preference):
  1. Lean metaprogramming – getParentStructures (for parents)
  2. Mathlib4 HTML docs scrape (for children / subclasses)
  3. Hardcoded fallback map for the most common Mathlib algebra classes
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import urllib.request
from functools import lru_cache
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# Project helpers
# ---------------------------------------------------------------------------

# PROJECT_DIR is the Lake project root (one level up from src/).
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATHLIB_DOCS_BASE = "https://leanprover-community.github.io/mathlib4_docs"


def _run_lean(code: str, timeout: int = 120) -> str:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".lean", dir=PROJECT_DIR, delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp = f.name
    try:
        r = subprocess.run(
            ["lake", "env", "lean", tmp],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return "timeout"
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ---------------------------------------------------------------------------
# Hardcoded fallback hierarchy (direct parent → children edges)
# Used when docs scraping fails and for fast common-case lookups.
# ---------------------------------------------------------------------------

# Maps each typeclass to its known direct parents (weakening direction).
_HARDCODED_PARENTS: dict[str, list[str]] = {
    # ── Algebraic hierarchy (single type variable) ────────────────────────
    "MulOneClass":          [],
    "Monoid":               ["MulOneClass"],
    "CommMonoid":           ["Monoid"],
    "Group":                ["Monoid"],
    "CommGroup":            ["CommMonoid", "Group"],
    "AddMonoid":            [],
    "AddCommMonoid":        ["AddMonoid"],
    "AddGroup":             ["AddMonoid"],
    "AddCommGroup":         ["AddCommMonoid", "AddGroup"],
    "MulZeroClass":         [],
    "NonUnitalNonAssocSemiring": ["AddCommMonoid", "MulZeroClass"],
    "NonUnitalSemiring":    ["NonUnitalNonAssocSemiring"],
    "NonAssocSemiring":     ["NonUnitalNonAssocSemiring"],
    "Semiring":             ["NonUnitalSemiring", "NonAssocSemiring"],
    "CommSemiring":         ["Semiring", "CommMonoid"],
    "Ring":                 ["Semiring", "AddCommGroup"],
    "CommRing":             ["Ring", "CommSemiring"],
    "IsDomain":             ["CommRing"],
    "EuclideanDomain":      ["IsDomain"],
    "Field":                ["CommRing"],
    "LinearOrderedField":   ["Field"],
    # ── Order hierarchy ───────────────────────────────────────────────────
    "Preorder":             [],
    "PartialOrder":         ["Preorder"],
    "LinearOrder":          ["PartialOrder"],
    "Lattice":              ["PartialOrder"],
    "DistribLattice":       ["Lattice"],
    "LinearOrderedAddCommMonoid": ["AddCommMonoid", "LinearOrder"],
    "LinearOrderedCommMonoid":    ["CommMonoid", "LinearOrder"],
    "OrderedAddCommGroup":  ["AddCommGroup", "PartialOrder"],
    "OrderedRing":          ["Ring", "OrderedAddCommGroup"],
    "LinearOrderedRing":    ["OrderedRing", "LinearOrder"],
    "LinearOrderedCommRing":["CommRing", "LinearOrderedRing"],
    # ── Module / vector space ──────────────────────────────────────────────
    "Module":               ["AddCommGroup"],
    "Submodule":            [],
    # ── Norm / metric ─────────────────────────────────────────────────────
    "Norm":                 [],
    "SeminormedAddCommGroup": ["AddCommGroup", "Norm"],
    "NormedAddCommGroup":   ["SeminormedAddCommGroup"],
    "SeminormedRing":       ["Ring", "SeminormedAddCommGroup"],
    "NormedRing":           ["SeminormedRing", "NormedAddCommGroup"],
    "NormedField":          ["Field", "NormedRing"],
    # ── Topological ───────────────────────────────────────────────────────
    "TopologicalSpace":     [],
    "T0Space":              ["TopologicalSpace"],
    "T1Space":              ["T0Space"],
    "T2Space":              ["T1Space"],
    "T3Space":              ["T2Space"],
    "MetricSpace":          ["T2Space"],
    "CompleteSpace":        ["MetricSpace"],
    # ── Finiteness ────────────────────────────────────────────────────────
    "Fintype":              [],
    "Infinite":             [],
    # ── Decidability ──────────────────────────────────────────────────────
    "DecidableEq":          [],
}

# Reverse map: children[TC] = [subclasses that directly extend TC]
_HARDCODED_CHILDREN: dict[str, list[str]] = {}
for _child, _parents in _HARDCODED_PARENTS.items():
    for _p in _parents:
        _HARDCODED_CHILDREN.setdefault(_p, []).append(_child)

# ---------------------------------------------------------------------------
# Prop-valued typeclass hierarchy (used in theorem CONCLUSIONS)
# These classes appear as bare applications `TC α` rather than `[TC α]` and
# express structural properties as Propositions.
# ---------------------------------------------------------------------------

_PROP_TC_PARENTS: dict[str, list[str]] = {
    # Domain / field chain
    "IsField":              ["EuclideanDomain"],
    "EuclideanDomain":      ["IsDomain"],
    "IsDomain":             ["IsCancelMulZero", "Nontrivial"],
    "IsCancelMulZero":      ["NoZeroDivisors"],
    "NoZeroDivisors":       [],
    "Nontrivial":           [],
    # Commutativity / cancellation
    "IsCancelMul":          ["IsLeftCancelMul", "IsRightCancelMul"],
    "IsLeftCancelMul":      [],
    "IsRightCancelMul":     [],
    # Normality / simplicity
    "IsSimpleGroup":        [],
    "IsSimpleModule":       [],
    # Algebraically closed
    "IsAlgClosed":          [],
    # Unit / invertible
    "IsUnit":               [],
    # Dedekind / Noetherian
    "IsDedekindDomain":     ["IsNoetherian"],
    "IsNoetherian":         [],
    "IsPrincipalIdealRing": ["IsDedekindDomain"],
    # Integral / prime
    "Prime":                ["Irreducible"],
    "Irreducible":          [],
    "Associated":           [],
    # Group properties
    "IsAbelian":            [],
    # Separable / perfect field
    "IsSepClosed":          ["IsAlgClosed"],
}

_PROP_TC_CHILDREN: dict[str, list[str]] = {}
for _child, _parents in _PROP_TC_PARENTS.items():
    for _p in _parents:
        _PROP_TC_CHILDREN.setdefault(_p, []).append(_child)

# Combined set of all known typeclass names (for quick lookup)
_ALL_KNOWN_TC: set[str] = set(_HARDCODED_PARENTS) | set(_PROP_TC_PARENTS)


# ---------------------------------------------------------------------------
# Getting parents via Lean (most reliable for arbitrary classes)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=256)
def get_class_parents_lean(class_name: str) -> list[str]:
    """
    Query Lean for the direct parent structures of `class_name`.
    Uses Lean.StructureInfo.parentInfo from Lean's core API.
    Returns [] if not a structure/class or Lean times out.
    """
    lean_code = (
        "import Mathlib\n"
        "import Lean\n\n"
        "#eval show Lean.CoreM Unit from do\n"
        "  let env ← Lean.getEnv\n"
        f"  match Lean.getStructureInfo? env `{class_name} with\n"
        '  | none => IO.println "[]"\n'
        "  | some info =>\n"
        "    let parents := info.parentInfo.map (·.structName.toString)\n"
        "    IO.println (toString parents)\n"
    )
    output = _run_lean(lean_code)
    # Lean prints something like: #[Semiring, AddCommGroup, AddGroupWithOne]
    m = re.search(r'#?\[([^\]]*)\]', output)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    items = [x.strip() for x in raw.split(',') if x.strip()]
    # Strip Lean qualified prefixes: keep only the last segment
    return [name.rsplit('.', 1)[-1] for name in items]


# ---------------------------------------------------------------------------
# Getting children via Mathlib4 HTML docs scrape
# ---------------------------------------------------------------------------

class _ExtendsParser(HTMLParser):
    """Collect identifiers from the 'extends' clause on a Mathlib4 docs page."""

    def __init__(self) -> None:
        super().__init__()
        self._in_decl = False
        self._depth = 0
        self._extends_text = ""
        self._found: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        classes = dict(attrs).get("class", "") or ""
        if "decl" in classes or "structure" in classes:
            self._in_decl = True
            self._depth = 0
        if self._in_decl:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._in_decl:
            self._depth -= 1
            if self._depth <= 0:
                self._in_decl = False

    def handle_data(self, data: str) -> None:
        if self._in_decl:
            self._extends_text += data

    def get_extends(self) -> list[str]:
        text = self._extends_text
        m = re.search(r'extends\s+(.*?)(?:\s*where|\s*:=|\Z)', text, re.DOTALL)
        if not m:
            return []
        raw = m.group(1)
        # Strip type args, keep class names (Capitalized identifiers)
        return re.findall(r'\b([A-Z][A-Za-z0-9_]*)\b', raw)


def _fetch_url(url: str, timeout: int = 10) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None


@lru_cache(maxsize=256)
def _find_class_doc_url(class_name: str) -> str | None:
    """
    Search Mathlib4 docs for the HTML page of `class_name`.
    Returns the page URL or None.
    """
    search_url = f"{MATHLIB_DOCS_BASE}/find/?pattern={class_name}"
    html = _fetch_url(search_url)
    if not html:
        return None
    # Look for the first link matching /Mathlib/...html#ClassName
    pattern = rf'href="([^"]*Mathlib[^"]*\.html#{re.escape(class_name)})"'
    m = re.search(pattern, html)
    if m:
        href = m.group(1)
        if href.startswith("http"):
            return href
        return MATHLIB_DOCS_BASE + "/" + href.lstrip("./")
    return None


@lru_cache(maxsize=256)
def get_class_children_docs(class_name: str) -> list[str]:
    """
    Scrape the Mathlib4 docs page for `class_name` and return a list of
    direct subclasses (classes that `extend` it).
    """
    url = _find_class_doc_url(class_name)
    if not url:
        return []
    html = _fetch_url(url)
    if not html:
        return []
    # Search for classes that extend class_name in this page
    # Mathlib4 docs renders each declaration; look for 'extends ClassName' patterns
    children: list[str] = []
    # Pattern: class <Child> ... extends <class_name>
    for m in re.finditer(
        rf'class\s+([A-Z][A-Za-z0-9_]*)\b[^{{]*\bextends\b[^{{]*\b{re.escape(class_name)}\b',
        html,
    ):
        name = m.group(1)
        if name != class_name:
            children.append(name)
    return list(dict.fromkeys(children))  # deduplicate preserving order


# ---------------------------------------------------------------------------
# Public hierarchy API
# ---------------------------------------------------------------------------

def get_parents(class_name: str, use_lean: bool = True) -> list[str]:
    """
    Return direct parent classes of `class_name` (1 level up = more general).
    Tries Lean first (if use_lean), falls back to hardcoded map.
    """
    if class_name in _HARDCODED_PARENTS:
        return _HARDCODED_PARENTS[class_name]
    if use_lean:
        lean_result = get_class_parents_lean(class_name)
        if lean_result:
            return lean_result
    return []


def get_children(class_name: str) -> list[str]:
    """
    Return direct subclasses of `class_name` (1 level down = more specific).
    Tries hardcoded map first, then docs scraping.
    """
    hardcoded = _HARDCODED_CHILDREN.get(class_name, [])
    if hardcoded:
        return hardcoded
    return get_class_children_docs(class_name)


def get_ancestors(class_name: str, depth: int = 2) -> list[str]:
    """BFS up to `depth` levels up the hierarchy."""
    visited: set[str] = set()
    frontier = [class_name]
    result: list[str] = []
    for _ in range(depth):
        next_frontier: list[str] = []
        for name in frontier:
            for parent in get_parents(name):
                if parent not in visited and parent != class_name:
                    visited.add(parent)
                    result.append(parent)
                    next_frontier.append(parent)
        frontier = next_frontier
    return result


def get_descendants(class_name: str, depth: int = 2) -> list[str]:
    """BFS up to `depth` levels down the hierarchy."""
    visited: set[str] = set()
    frontier = [class_name]
    result: list[str] = []
    for _ in range(depth):
        next_frontier: list[str] = []
        for name in frontier:
            for child in get_children(name):
                if child not in visited and child != class_name:
                    visited.add(child)
                    result.append(child)
                    next_frontier.append(child)
        frontier = next_frontier
    return result


# ---------------------------------------------------------------------------
# Parsing and substituting typeclass brackets in a Lean type string
# ---------------------------------------------------------------------------

# Matches [inst? : ?TCName args] or [TCName args]
# Group 1: optional "varname :" prefix (including colon)
# Group 2: typeclass name (Capitalized identifier)
# Group 3: remainder (arguments and closing bracket content)
_TC_BRACKET_RE = re.compile(
    r'\['
    r'([A-Za-z_][A-Za-z0-9_₀-₉]*\s*:\s*)?'   # optional "inst : "
    r'([A-Z][A-Za-z0-9_.]*)'                    # TC name
    r'([^\[\]]*)\]'                              # args + closing bracket
)


def _find_tc_brackets(
    text: str,
) -> list[tuple[str, str, str, str, int, int]]:
    """
    Find all typeclass brackets in `text`.

    Returns list of (full_match, prefix, tc_name, args, start, end).
    """
    results = []
    for m in _TC_BRACKET_RE.finditer(text):
        prefix = m.group(1) or ""
        tc_name = m.group(2)
        args = m.group(3)
        results.append((m.group(0), prefix, tc_name, args, m.start(), m.end()))
    return results


def _substitute_tc(type_str: str, old_tc: str, new_tc: str) -> str:
    """
    Replace the first occurrence of typeclass `old_tc` with `new_tc`
    inside a `[...]` bracket, keeping all arguments unchanged.
    """
    brackets = _find_tc_brackets(type_str)
    for full, prefix, tc_name, args, start, end in brackets:
        if tc_name == old_tc:
            new_bracket = f"[{prefix}{new_tc}{args}]"
            return type_str[:start] + new_bracket + type_str[end:]
    return type_str


def _split_hyps_conclusion(type_str: str) -> tuple[str, str]:
    """
    Split a Lean type string into (hypotheses_part, conclusion_part).

    Handles two forms:
      ∀ {x : T} [TC x] (a : T), <conclusion>   – split on last top-level ','
      ∀ {x : T} [TC x] → <conclusion>           – split on last top-level '→'

    Returns ("", type_str) when no separator is found.
    """
    depth = 0
    last_sep: int = -1
    sep_len: int = 1
    i = 0
    while i < len(type_str):
        c = type_str[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0:
            # Unicode arrow → (U+2192, 3 bytes in UTF-8 but 1 char in Python str)
            if type_str[i] == "→":
                last_sep = i
                sep_len = 1
            elif c == ",":
                last_sep = i
                sep_len = 1
        i += 1
    if last_sep == -1:
        return "", type_str
    return type_str[: last_sep + sep_len], type_str[last_sep + sep_len :].strip()


def _compile_lean(type_str: str) -> bool:
    """Return True iff `example : <type_str> := by sorry` compiles in Lean."""
    code = f"import Mathlib\n\nexample : {type_str} := by sorry\n"
    output = _run_lean(code)
    # Lean 4 errors appear as both "error:" and "error(<kind>):" — match either.
    return not re.search(r"\berror[:(]", output) and "timeout" not in output


def _find_prop_tc_in_text(text: str) -> list[tuple[str, int, int]]:
    """
    Find bare Prop-valued typeclass applications in `text`.
    Matches `TCName <args>` where TCName is a known Prop-TC.
    Returns list of (tc_name, start, end_of_name).
    """
    results = []
    for m in re.finditer(r'\b([A-Z][A-Za-z0-9_]*)\b', text):
        name = m.group(1)
        if name in _PROP_TC_PARENTS:
            results.append((name, m.start(), m.end()))
    return results


def _substitute_prop_tc(type_str: str, old_tc: str, new_tc: str) -> str:
    """Replace first occurrence of bare Prop-TC `old_tc` with `new_tc` in the full string."""
    m = re.search(r'\b' + re.escape(old_tc) + r'\b', type_str)
    if not m:
        return type_str
    return type_str[: m.start()] + new_tc + type_str[m.end():]


def _substitute_prop_tc_in_conclusion(
    type_str: str, old_tc: str, new_tc: str, conclusion_offset: int
) -> str:
    """
    Replace first occurrence of bare Prop-TC `old_tc` in the CONCLUSION part
    of `type_str` (starting at byte offset `conclusion_offset`).
    """
    suffix = type_str[conclusion_offset:]
    m = re.search(r'\b' + re.escape(old_tc) + r'\b', suffix)
    if not m:
        return type_str
    abs_start = conclusion_offset + m.start()
    abs_end = conclusion_offset + m.end()
    return type_str[:abs_start] + new_tc + type_str[abs_end:]


def _get_prop_tc_ancestors(tc_name: str, depth: int) -> list[str]:
    visited: set[str] = set()
    frontier = [tc_name]
    result: list[str] = []
    for _ in range(depth):
        next_frontier: list[str] = []
        for name in frontier:
            for parent in _PROP_TC_PARENTS.get(name, []):
                if parent not in visited and parent != tc_name:
                    visited.add(parent)
                    result.append(parent)
                    next_frontier.append(parent)
        frontier = next_frontier
    return result


def _get_prop_tc_descendants(tc_name: str, depth: int) -> list[str]:
    visited: set[str] = set()
    frontier = [tc_name]
    result: list[str] = []
    for _ in range(depth):
        next_frontier: list[str] = []
        for name in frontier:
            for child in _PROP_TC_CHILDREN.get(name, []):
                if child not in visited and child != tc_name:
                    visited.add(child)
                    result.append(child)
                    next_frontier.append(child)
        frontier = next_frontier
    return result


# ---------------------------------------------------------------------------
# The four perturbation methods
# ---------------------------------------------------------------------------

def generalize_statement_by_weakening_hypotheses(
    sig: str,
    type_str: str,
    depth: int = 2,
) -> tuple[str, str] | None:
    """
    Find a typeclass [TC α] in the hypotheses and replace TC with a weaker
    ancestor class (moving UP the hierarchy). Returns (sig, new_type_str)
    for the first substitution that compiles, or None.
    """
    hyp_part, _ = _split_hyps_conclusion(type_str)
    brackets = _find_tc_brackets(hyp_part or type_str)
    for _, _, tc_name, _, _, _ in brackets:
        for ancestor in get_ancestors(tc_name, depth):
            new_type = _substitute_tc(type_str, tc_name, ancestor)
            if new_type == type_str:
                continue
            if _compile_lean(new_type):
                return sig, new_type
    return None


def weaken_statement_by_strengthening_hypotheses(
    sig: str,
    type_str: str,
    depth: int = 2,
) -> tuple[str, str] | None:
    """
    Find a typeclass [TC α] in the hypotheses and replace TC with a stronger
    descendant class (moving DOWN the hierarchy). Returns (sig, new_type_str)
    for the first substitution that compiles, or None.
    """
    hyp_part, _ = _split_hyps_conclusion(type_str)
    brackets = _find_tc_brackets(hyp_part or type_str)
    for _, _, tc_name, _, _, _ in brackets:
        for descendant in get_descendants(tc_name, depth):
            new_type = _substitute_tc(type_str, tc_name, descendant)
            if new_type == type_str:
                continue
            if _compile_lean(new_type):
                return sig, new_type
    return None


def strengthen_statement_by_strengthening_conclusion(
    sig: str,
    type_str: str,
    depth: int = 2,
) -> tuple[str, str] | None:
    """
    Find a typeclass in the conclusion and replace it with a stronger
    descendant (moving DOWN = more specific = stronger conclusion).

    Handles two conclusion forms:
      • [inst : TC α]  – structural typeclass in a binder
      • TC α           – bare Prop-valued typeclass application (e.g. IsDomain R)

    Returns (sig, new_type_str) for the first substitution that compiles,
    or None.
    """
    hyp_part, conclusion = _split_hyps_conclusion(type_str)
    conc_offset = len(hyp_part) if hyp_part else 0
    if not conclusion:
        conclusion = type_str
        conc_offset = 0

    # Pass 1: bracketed [TC ...] in the conclusion
    for _, _, tc_name, _, start, end in _find_tc_brackets(conclusion):
        for descendant in get_descendants(tc_name, depth):
            abs_start = conc_offset + start
            abs_end = conc_offset + end
            bracket = type_str[abs_start:abs_end]
            new_bracket = bracket.replace(tc_name, descendant, 1)
            new_type = type_str[:abs_start] + new_bracket + type_str[abs_end:]
            if new_type != type_str and _compile_lean(new_type):
                return sig, new_type

    # Pass 2: bare Prop-valued typeclass applications in the conclusion
    for tc_name, _, _ in _find_prop_tc_in_text(conclusion):
        for descendant in _get_prop_tc_descendants(tc_name, depth):
            new_type = _substitute_prop_tc_in_conclusion(
                type_str, tc_name, descendant, conc_offset
            )
            if new_type != type_str and _compile_lean(new_type):
                return sig, new_type

    return None


def weaken_statement_by_weakening_conclusion(
    sig: str,
    type_str: str,
    depth: int = 2,
) -> tuple[str, str] | None:
    """
    Find a typeclass in the conclusion and replace it with a weaker
    ancestor (moving UP = more general = weaker conclusion).

    Handles two conclusion forms:
      • [inst : TC α]  – structural typeclass in a binder
      • TC α           – bare Prop-valued typeclass application (e.g. IsDomain R)

    Returns (sig, new_type_str) for the first substitution that compiles,
    or None.
    """
    hyp_part, conclusion = _split_hyps_conclusion(type_str)
    conc_offset = len(hyp_part) if hyp_part else 0
    if not conclusion:
        conclusion = type_str
        conc_offset = 0

    # Pass 1: bracketed [TC ...] in the conclusion
    for _, _, tc_name, _, start, end in _find_tc_brackets(conclusion):
        for ancestor in get_ancestors(tc_name, depth):
            abs_start = conc_offset + start
            abs_end = conc_offset + end
            bracket = type_str[abs_start:abs_end]
            new_bracket = bracket.replace(tc_name, ancestor, 1)
            new_type = type_str[:abs_start] + new_bracket + type_str[abs_end:]
            if new_type != type_str and _compile_lean(new_type):
                return sig, new_type

    # Pass 2: bare Prop-valued typeclass applications in the conclusion
    for tc_name, _, _ in _find_prop_tc_in_text(conclusion):
        for ancestor in _get_prop_tc_ancestors(tc_name, depth):
            new_type = _substitute_prop_tc_in_conclusion(
                type_str, tc_name, ancestor, conc_offset
            )
            if new_type != type_str and _compile_lean(new_type):
                return sig, new_type

    return None


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

_DEMO_CASES = [
    (
        "add_comm",
        "∀ {α : Type u_1} [inst : AddCommMonoid α] (a b : α), a + b = b + a",
    ),
    (
        "mul_inv_cancel",
        "∀ {α : Type u_1} [inst : Field α] (a : α), a ≠ 0 → a * a⁻¹ = 1",
    ),
    # Conclusion contains a bare Prop-TC: IsDomain
    (
        "Polynomial.isDomain",
        "∀ {R : Type u_1} [inst : CommRing R] [inst_1 : IsDomain R], IsDomain (Polynomial R)",
    ),
]


def _demo() -> None:
    for name, type_str in _DEMO_CASES:
        print(f"\n{'='*60}")
        print(f"Original [{name}]:\n  {type_str}")

        result = generalize_statement_by_weakening_hypotheses(name, type_str)
        print(f"\ngeneralize_statement_by_weakening_hypotheses:")
        print(f"  {result[1] if result else '(none found)'}")

        result = weaken_statement_by_strengthening_hypotheses(name, type_str)
        print(f"\nweaken_statement_by_strengthening_hypotheses:")
        print(f"  {result[1] if result else '(none found)'}")

        result = strengthen_statement_by_strengthening_conclusion(name, type_str)
        print(f"\nstrengthen_statement_by_strengthening_conclusion:")
        print(f"  {result[1] if result else '(none found)'}")

        result = weaken_statement_by_weakening_conclusion(name, type_str)
        print(f"\nweaken_statement_by_weakening_conclusion:")
        print(f"  {result[1] if result else '(none found)'}")


if __name__ == "__main__":
    _demo()
