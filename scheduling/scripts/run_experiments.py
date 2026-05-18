#!/usr/bin/env python3
"""
run_experiments.py

Only script with a main() function.

It runs the full set of scheduling simulation experiments, then calls helper
modules after each successful Java run.

Important behaviour:
    - At the start of a real run, results/ is deleted and recreated.
    - make run ARGS output is NOT captured or hidden. It prints normally.
    - This script only controls its own final status output.
    - Failure logs are created only when a failure occurs.
"""

from __future__ import annotations

import argparse
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from compute_patron_metrics import compute_patron_metrics_for_file
from compute_stats_metrics import compute_stats_metrics_for_file
from plot_metric_graphs import create_graphs_for_file


SCHEDULER_NAMES = {
    0: "FCFS",
    1: "SJF",
    2: "PRIORITY",
    3: "MLFQ",
}


RESULT_DIRS = [
    "OrderData",
    "OrderMetrics",
    "PatronData",
    "PatronMetrics",
    "StatMetrics",
    "OrderMetricsGraphs",
    "PatronMetricsGraphs",
    "StatMetricsGraphs",
]


@dataclass(frozen=True)
class Experiment:
    scheduler_code: int
    scheduler_name: str
    seed: int
    no_patrons: int
    context_switch_time: int

    @property
    def args_string(self) -> str:
        return (
            f"{self.no_patrons} "
            f"{self.scheduler_code} "
            f"{self.context_switch_time} "
            f"{self.seed}"
        )

    @property
    def file_name(self) -> str:
        return f"{self.scheduler_name}_{self.no_patrons}_{self.seed}.txt"

    @property
    def log_file_name(self) -> str:
        return f"{self.scheduler_name}_{self.no_patrons}_{self.seed}"


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_project_root = script_path.parents[1]

    parser = argparse.ArgumentParser(
        description="Run scheduling experiments and compute patron/stat metrics."
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

    for seed in range(args.seed_start, args.seed_end + 1):
        selected_no_patrons = choose_no_patrons(
            seed=seed,
            min_patrons=args.min_patrons,
            max_patrons=args.max_patrons,
            sample_count=args.samples_per_seed,
        )

        for scheduler_code in range(args.sched_start, args.sched_end + 1):
            scheduler_name = SCHEDULER_NAMES.get(
                scheduler_code,
                f"SCHED{scheduler_code}",
            )

            for no_patrons in selected_no_patrons:
                experiments.append(
                    Experiment(
                        scheduler_code=scheduler_code,
                        scheduler_name=scheduler_name,
                        seed=seed,
                        no_patrons=no_patrons,
                        context_switch_time=args.context_switch_time,
                    )
                )

    return experiments


def ensure_results_dirs(results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)

    for dirname in RESULT_DIRS:
        (results_dir / dirname).mkdir(parents=True, exist_ok=True)


def reset_results_dir(results_dir: Path) -> None:
    """
    Force clean the whole results directory at the start of the experiment batch.
    """
    if results_dir.exists():
        shutil.rmtree(results_dir)

    ensure_results_dirs(results_dir)


def clear_existing_failure_logs(logs_dir: Path) -> None:
    """
    Clear old failure logs at the start of the experiment batch.
    The directory is only recreated when a new failure occurs.
    """
    if logs_dir.exists():
        shutil.rmtree(logs_dir)


def write_failure_log(
    logs_dir: Path,
    experiment: Experiment,
    stage: str,
    message: str,
) -> Path:
    """
    Create a per-run failure log.

    File name format:
        alg_noPatrons_seed
    """
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_path = logs_dir / experiment.log_file_name

    with log_path.open("a", encoding="utf-8") as file:
        file.write("=" * 80 + "\n")
        file.write(f"stage: {stage}\n")
        file.write(f"algorithm: {experiment.scheduler_name}\n")
        file.write(f"scheduler_code: {experiment.scheduler_code}\n")
        file.write(f"noPatrons: {experiment.no_patrons}\n")
        file.write(f"seed: {experiment.seed}\n")
        file.write(f"context_switch_time: {experiment.context_switch_time}\n")
        file.write(f"args: {experiment.args_string}\n")
        file.write("error:\n")
        file.write(f"{message}\n")

    return log_path


def run_java_experiment(
    experiment: Experiment,
    project_root: Path,
) -> int:
    """
    Run Java simulation.

    Output is intentionally not captured, so make/java prints normally.
    """
    command = ["make", "run", f"ARGS={experiment.args_string}"]

    completed = subprocess.run(
        command,
        cwd=project_root,
        text=True,
        check=False,
    )

    return completed.returncode


def main() -> int:
    args = parse_args()

    project_root = args.project_root.resolve()
    results_dir = project_root / "results"
    logs_dir = project_root / "logs"

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

    # Force clean before running any combinations.
    reset_results_dir(results_dir)
    clear_existing_failure_logs(logs_dir)

    failures = 0

    for experiment in experiments:
        return_code = run_java_experiment(
            experiment=experiment,
            project_root=project_root,
        )

        if return_code != 0:
            failures += 1

            write_failure_log(
                logs_dir=logs_dir,
                experiment=experiment,
                stage="java_run",
                message=f"Java run failed with return code {return_code}.",
            )

            if args.stop_on_failure:
                break

            continue

        try:
            compute_patron_metrics_for_file(
                results_dir=results_dir,
                file_name=experiment.file_name,
            )

        except Exception as exc:
            failures += 1

            write_failure_log(
                logs_dir=logs_dir,
                experiment=experiment,
                stage="patron_metrics",
                message=repr(exc),
            )

            if args.stop_on_failure:
                break

            continue

        try:
            compute_stats_metrics_for_file(
                results_dir=results_dir,
                file_name=experiment.file_name,
            )

        except Exception as exc:
            failures += 1

            write_failure_log(
                logs_dir=logs_dir,
                experiment=experiment,
                stage="stat_metrics",
                message=repr(exc),
            )

            if args.stop_on_failure:
                break

            continue

        try:
            create_graphs_for_file(
                results_dir=results_dir,
                file_name=experiment.file_name,
            )

        except Exception as exc:
            failures += 1

            write_failure_log(
                logs_dir=logs_dir,
                experiment=experiment,
                stage="metric_graphs",
                message=repr(exc),
            )

            if args.stop_on_failure:
                break

            continue

    if failures:
        print(f"Completed with {failures} failed attempt(s). Check logs/ for details.")
        return 1

    print("Completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
