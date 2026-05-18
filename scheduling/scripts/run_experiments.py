#!/usr/bin/env python3
"""
run_experiments.py

This is the only script with a main() function.

It runs the full set of simulation experiments, then calls helper modules after
each successful Java run.

No log files are created.
No selected_noPatrons file is created.
Progress is printed to the terminal only.
"""

from __future__ import annotations

import argparse
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from compute_patron_metrics import compute_patron_metrics_for_file
from compute_stats_metrics import compute_stats_metrics_for_file


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
        help="Print the planned commands without running make or deleting results.",
    )

    parser.add_argument(
        "--force-clean",
        action="store_true",
        help="Delete results/ before running, even if planned files do not exist yet.",
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


def build_experiments(args: argparse.Namespace) -> tuple[list[Experiment], dict[int, list[int]]]:
    experiments: list[Experiment] = []
    selected_no_patrons_by_seed: dict[int, list[int]] = {}

    for seed in range(args.seed_start, args.seed_end + 1):
        selected_no_patrons = choose_no_patrons(
            seed=seed,
            min_patrons=args.min_patrons,
            max_patrons=args.max_patrons,
            sample_count=args.samples_per_seed,
        )

        selected_no_patrons_by_seed[seed] = selected_no_patrons

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

    return experiments, selected_no_patrons_by_seed


def output_files_for_experiment(results_dir: Path, experiment: Experiment) -> list[Path]:
    file_name = experiment.file_name

    return [
        results_dir / "OrderData" / file_name,
        results_dir / "OrderMetrics" / file_name,
        results_dir / "PatronData" / file_name,
        results_dir / "PatronMetrics" / file_name,
        results_dir / "StatMetrics" / file_name,
    ]


def planned_outputs_exist(results_dir: Path, experiments: list[Experiment]) -> bool:
    if not results_dir.exists():
        return False

    for experiment in experiments:
        for output_file in output_files_for_experiment(results_dir, experiment):
            if output_file.exists():
                return True

    return False


def reset_results_dir(results_dir: Path) -> None:
    if results_dir.exists():
        shutil.rmtree(results_dir)

    ensure_results_dirs(results_dir)


def ensure_results_dirs(results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)

    for dirname in RESULT_DIRS:
        (results_dir / dirname).mkdir(parents=True, exist_ok=True)


def run_java_experiment(
    experiment: Experiment,
    project_root: Path,
    dry_run: bool,
) -> tuple[int, float]:
    command = ["make", "run", f"ARGS={experiment.args_string}"]

    if dry_run:
        print(f"  DRY RUN: {' '.join(command)}")
        return 0, 0.0

    start = time.perf_counter()

    completed = subprocess.run(
        command,
        cwd=project_root,
        text=True,
        check=False,
    )

    duration = time.perf_counter() - start
    return completed.returncode, duration


def main() -> int:
    args = parse_args()

    project_root = args.project_root.resolve()
    results_dir = project_root / "results"

    if not project_root.exists():
        print(f"ERROR: project root does not exist: {project_root}", file=sys.stderr)
        return 1

    makefile = project_root / "Makefile"

    if not makefile.exists() and not args.dry_run:
        print(
            f"ERROR: Makefile not found at {makefile}. "
            "Use --project-root if the script inferred the wrong directory.",
            file=sys.stderr,
        )
        return 1

    experiments, selected_no_patrons_by_seed = build_experiments(args)

    print(f"Project root: {project_root}")
    print(f"Results dir: {results_dir}")
    print(f"Dry run: {args.dry_run}")
    print(f"Total runs planned: {len(experiments)}")

    print("Selected noPatrons values:")
    for seed, selected_values in selected_no_patrons_by_seed.items():
        print(f"  seed={seed}: {selected_values}")

    if args.dry_run:
        print("Dry run selected: results/ will not be deleted and make will not be run.")
    else:
        if args.force_clean or planned_outputs_exist(results_dir, experiments):
            print("Existing planned output detected. Deleting results/ and starting afresh.")
            reset_results_dir(results_dir)
        else:
            ensure_results_dirs(results_dir)

    failures = 0

    for index, experiment in enumerate(experiments, start=1):
        print(
            f"[{index:03d}/{len(experiments):03d}] "
            f"{experiment.scheduler_name}, "
            f"noPatrons={experiment.no_patrons}, "
            f"seed={experiment.seed}, "
            f"s={experiment.context_switch_time}"
        )

        return_code, duration = run_java_experiment(
            experiment=experiment,
            project_root=project_root,
            dry_run=args.dry_run,
        )

        if return_code != 0:
            failures += 1
            print(f"  FAILED Java run with return code {return_code}.", file=sys.stderr)

            if args.stop_on_failure:
                break

            continue

        if args.dry_run:
            continue

        try:
            patron_data_file, patron_metrics_file, patron_count = (
                compute_patron_metrics_for_file(
                    results_dir=results_dir,
                    file_name=experiment.file_name,
                )
            )

            print(f"  Java run completed in {duration:.4f}s.")
            print(f"  Patron metrics computed for {patron_count} patrons.")
            print(f"    {patron_data_file}")
            print(f"    {patron_metrics_file}")

        except Exception as exc:
            failures += 1
            print(
                f"  FAILED while computing patron metrics: {exc}",
                file=sys.stderr,
            )

            if args.stop_on_failure:
                break

            continue

        try:
            stats_file = compute_stats_metrics_for_file(
                results_dir=results_dir,
                file_name=experiment.file_name,
            )

            print(f"  Stat metrics written:")
            print(f"    {stats_file}")

        except Exception as exc:
            failures += 1
            print(
                f"  FAILED while computing stat metrics: {exc}",
                file=sys.stderr,
            )

            if args.stop_on_failure:
                break

    if args.dry_run:
        print("Dry run complete. No simulations were executed.")
    elif failures:
        print(f"Completed with {failures} failed step(s).")
    else:
        print("All simulations completed successfully.")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
