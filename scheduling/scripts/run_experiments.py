#!/usr/bin/env python3
"""
run_experiments.py

Builds a batch of scheduling simulation experiments and runs each one through
run_experiment.py.

Important behaviour:
    - It does NOT delete the whole results/ directory at the start.
    - Each individual experiment clears only its own result/graph files before
      it reruns.
    - make run ARGS output is NOT captured or hidden. It prints normally.
    - This script only controls its own final status output.
    - Failure logs are created only when a failure occurs.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from run_experiment import Experiment, make_experiment, run_single_experiment
from plot_metric_graphs import create_algo_metrics_graphs


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_project_root = script_path.parents[1]

    parser = argparse.ArgumentParser(
        description="Run scheduling experiment batches and compute metrics/graphs."
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=default_project_root,
        help="Project root containing the Makefile. Default: inferred from script location.",
    )

    parser.add_argument("--min-patrons", type=int, default=8)
    parser.add_argument("--max-patrons", type=int, default=50)
    parser.add_argument("--samples-per-seed", type=int, default=3)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--seed-end", type=int, default=3)
    parser.add_argument("--sched-start", type=int, default=0)
    parser.add_argument("--sched-end", type=int, default=3)
    parser.add_argument("--context-switch-time", type=int, default=0)

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate the experiment plan. Do not run make or delete result files.",
    )

    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop immediately after the first failed run.",
    )

    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not clear existing output files for each experiment before running.",
    )

    return parser.parse_args()


def choose_no_patrons(
    seed: int,
    min_patrons: int,
    max_patrons: int,
    sample_count: int,
) -> list[int]:
    if min_patrons > max_patrons:
        raise ValueError("min_patrons cannot be greater than max_patrons.")

    population = list(range(min_patrons, max_patrons + 1))

    if sample_count > len(population):
        raise ValueError(
            f"samples_per_seed={sample_count} is larger than the available patron range."
        )

    rng = random.Random(seed)
    return sorted(rng.sample(population, sample_count))


def build_experiments(args: argparse.Namespace) -> list[Experiment]:
    experiments: list[Experiment] = []

    if args.seed_start > args.seed_end:
        raise ValueError("seed_start cannot be greater than seed_end.")

    if args.sched_start > args.sched_end:
        raise ValueError("sched_start cannot be greater than sched_end.")

    for seed in range(args.seed_start, args.seed_end + 1):
        selected_no_patrons = choose_no_patrons(
            seed=seed,
            min_patrons=args.min_patrons,
            max_patrons=args.max_patrons,
            sample_count=args.samples_per_seed,
        )

        for scheduler_code in range(args.sched_start, args.sched_end + 1):
            for no_patrons in selected_no_patrons:
                experiments.append(
                    make_experiment(
                        no_patrons=no_patrons,
                        scheduler_code=scheduler_code,
                        context_switch_time=args.context_switch_time,
                        seed=seed,
                    )
                )

    return experiments


def main() -> int:
    args = parse_args()

    project_root = args.project_root.resolve()

    if not project_root.exists():
        print(
            f"Completed with 1 failed attempt. Project root does not exist: {project_root}",
            file=sys.stderr,
        )
        return 1

    makefile = project_root / "Makefile"

    if not makefile.exists() and not args.dry_run:
        print(
            f"Completed with 1 failed attempt. Makefile not found at {makefile}",
            file=sys.stderr,
        )
        return 1

    try:
        experiments = build_experiments(args)
    except Exception as exc:
        print(
            f"Completed with 1 failed attempt. Could not build experiment plan: {exc}",
            file=sys.stderr,
        )
        return 1

    if args.dry_run:
        print(f"Dry run completed successfully. Planned {len(experiments)} simulation run(s).")
        return 0

    failures = 0

    for experiment in experiments:
        result = run_single_experiment(
            experiment=experiment,
            project_root=project_root,
            clean_previous=not args.no_clean,
            write_logs=True,
        )

        if not result.succeeded:
            failures += 1

            if args.stop_on_failure:
                break

            continue

    try:
        create_algo_metrics_graphs(project_root / "results")
    except Exception as exc:
        failures += 1
        print(
            f"Completed with {failures} failed attempt(s). "
            f"Could not create algorithm metric graphs: {exc}",
            file=sys.stderr,
        )
        return 1

    if failures:
        print(f"Completed with {failures} failed attempt(s). Check logs/ for details.")
        return 1

    print("Completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
