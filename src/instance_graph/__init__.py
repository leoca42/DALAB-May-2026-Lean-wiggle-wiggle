"""Mathlib instance-graph utilities.

Three CLI entry points, each runnable as `python -m` from the project root:

    dump_mathlib_instances        - dump every registered Lean/Mathlib instance
                                    as JSONL (writes data/mathlib_instances.jsonl).
    build_instance_implications   - turn the instance dump into a
                                    (source -> target) edge list of typeclass
                                    implications (writes data/instance_implications.jsonl).
    typeclass_implication_table   - verify candidate edges from the
                                    mathlib-types dataset via Lean's #synth
                                    (writes data/typeclass_implications.jsonl).
"""
