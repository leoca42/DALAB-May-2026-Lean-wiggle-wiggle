import argparse
import os
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def dump_instances(output_path: str, timeout: int) -> None:
    tmp_path = os.path.join(PROJECT_DIR, "_dump_instances_tmp.lean")
    code = "import Wiggle\n\n#wiggle_dump_instances\n"
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

        rows = [line for line in output.splitlines() if line.startswith("{")]
        with open(output_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(row + "\n")
        print(f"Wrote {len(rows)} instances to {output_path}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump registered Lean/Mathlib instances as JSONL.")
    parser.add_argument("--output", default="mathlib_instances.jsonl")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    dump_instances(args.output, args.timeout)


if __name__ == "__main__":
    main()
