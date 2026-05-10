import argparse
import json
import os
import subprocess
from collections import defaultdict, deque

from typeclass_implication_table import head_symbol

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_decl_typeclasses(decl_name: str, timeout: int = 300) -> dict:
    tmp_path = os.path.join(PROJECT_DIR, "_decl_typeclasses_tmp.lean")
    code = f"import Wiggle\n\n#wiggle_decl_typeclasses {decl_name}\n"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(code)
        result = subprocess.run(
            ["lake", "env", "lean", tmp_path],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0 or "error:" in output:
            raise RuntimeError(output)
        for line in output.splitlines():
            if line.startswith("{"):
                return json.loads(line)
        raise RuntimeError(f"No JSON output from Lean:\n{output}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def load_head_graph(edge_path: str) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    weaker: dict[str, set[str]] = defaultdict(set)
    stronger: dict[str, set[str]] = defaultdict(set)
    with open(edge_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            edge = json.loads(line)
            source = edge["source_head"]
            target = edge["target_head"]
            if source == target:
                continue
            weaker[source].add(target)
            stronger[target].add(source)
    return weaker, stronger


def within_steps(graph: dict[str, set[str]], start: str, steps: int) -> list[dict[str, object]]:
    seen = {start}
    out: list[dict[str, object]] = []
    queue = deque([(start, 0)])
    while queue:
        node, depth = queue.popleft()
        if depth == steps:
            continue
        for neighbor in sorted(graph.get(node, ())):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            next_depth = depth + 1
            out.append({"class": neighbor, "distance": next_depth})
            queue.append((neighbor, next_depth))
    return out


def declaration_neighborhood(
    decl_name: str,
    edge_path: str,
    steps: int = 2,
    timeout: int = 300,
) -> dict[str, object]:
    decl_info = run_decl_typeclasses(decl_name, timeout=timeout)
    weaker_graph, stronger_graph = load_head_graph(edge_path)

    classes = []
    for item in decl_info["typeclasses"]:
        typeclass = item["typeclass"]
        head = head_symbol(typeclass)
        if not head:
            continue
        classes.append({
            "typeclass": typeclass,
            "head": head,
            "weaker_downstream": within_steps(weaker_graph, head, steps),
            "stronger_upstream": within_steps(stronger_graph, head, steps),
        })

    return {
        "declaration": decl_name,
        "type": decl_info["type"],
        "steps": steps,
        "typeclasses": classes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Get a declaration's typeclasses and two-hop hierarchy neighborhood."
    )
    parser.add_argument("declaration")
    parser.add_argument("--edges", default="instance_implications.jsonl")
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output")
    args = parser.parse_args()

    result = declaration_neighborhood(
        args.declaration,
        args.edges,
        steps=args.steps,
        timeout=args.timeout,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
