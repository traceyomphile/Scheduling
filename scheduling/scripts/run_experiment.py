#!/usr/bin/env python3
"""
run_experiment.py

Runs one scheduling simulation experiment, then computes patron/stat metrics
and metric graphs for that same run.

This script can be used in two ways:
    1. As a helper imported by run_experiments.py.
    2. As a standalone script for one experiment.

Important behaviour:
    - It clears only the files belonging to this exact experiment before rerun.
    - It does not delete the whole results/ directory.
    - make run ARGS output is NOT captured or hidden. It prints normally.
    - Failure logs are created only when a failure occurs.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from compute_patron_metrics import compute_patron_metrics_for_file
from compute_stats_metrics import compute_stats_metrics_for_file
from plot_metric_graphs import create_graphs_for_file


SCHEDULER_NAMES = {
    0: "FCFS",
    1: "SJF",
    2: "PRIORITY",
    3: "MLFQ",
}


TEXT_RESULT_DIRS = [
    "OrderData",
    "OrderMetrics",
    "PatronData",
    "PatronMetrics",
    "StatMetrics",
]


GRAPH_RESULT_DIRS = [
    "OrderMetricsGraphs",
    "PatronMetricsGraphs",
    "StatMetricsGraphs",
]


RESULT_DIRS = TEXT_RESULT_DIRS + GRAPH_RESULT_DIRS


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
    def graph_file_name(self) -> str:
        return f"{self.scheduler_name}_{self.no_patrons}_{self.seed}.png"

    @property
    def log_file_name(self) -> str:
        return f"{self.scheduler_name}_{self.no_patrons}_{self.seed}"


@dataclass(frozen=True)
class ExperimentResult:
    experiment: Experiment
    succeeded: bool
    failed_stage: str | None = None
    message: str | None = None
    log_path: Path | None = None


def scheduler_name_for_code(scheduler_code: int) -> str:
    try:
        return SCHEDULER_NAMES[scheduler_code]
    except KeyError as exc:
        raise ValueError(
            f"Invalid scheduler_code={scheduler_code}. "
            "Valid values are: 0=FCFS, 1=SJF, 2=PRIORITY, 3=MLFQ."
        ) from exc


def make_experiment(
    no_patrons: int,
    scheduler_code: int,
    context_switch_time: int,
    seed: int,
) -> Experiment:
    return Experiment(
        scheduler_code=scheduler_code,
        scheduler_name=scheduler_name_for_code(scheduler_code),
        seed=seed,
        no_patrons=no_patrons,
        context_switch_time=context_switch_time,
    )


def ensure_results_dirs(results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)

    for dirname in RESULT_DIRS:
        (results_dir / dirname).mkdir(parents=True, exist_ok=True)


def experiment_output_paths(results_dir: Path, experiment: Experiment) -> list[Path]:
    """
    Return every output file that belongs to one experiment.

    Text outputs keep the .txt file name. Graph outputs use the same base name
    with a .png extension.
    """
    paths: list[Path] = []

    for dirname in TEXT_RESULT_DIRS:
        paths.append(results_dir / dirname / experiment.file_name)

    for dirname in GRAPH_RESULT_DIRS:
        paths.append(results_dir / dirname / experiment.graph_file_name)

    return paths


def clear_experiment_outputs(results_dir: Path, experiment: Experiment) -> None:
    """
    Delete only output files belonging to this exact experiment.

    This prevents rerunning FCFS_13_2 from appending to old FCFS_13_2 files,
    without destroying every other experiment result like a tiny filesystem war
    crime.
    """
    ensure_results_dirs(results_dir)

    for path in experiment_output_paths(results_dir, experiment):
        if path.exists():
            path.unlink()


def clear_experiment_failure_log(logs_dir: Path, experiment: Experiment) -> None:
    """Delete the old failure log for this exact experiment, if one exists."""
    log_path = logs_dir / experiment.log_file_name

    if log_path.exists():
        log_path.unlink()


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

    with log_path.open("w", encoding="utf-8") as file:
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


def _failure_result(
    experiment: Experiment,
    logs_dir: Path,
    stage: str,
    message: str,
    write_logs: bool,
) -> ExperimentResult:
    log_path = None

    if write_logs:
        log_path = write_failure_log(
            logs_dir=logs_dir,
            experiment=experiment,
            stage=stage,
            message=message,
        )

    return ExperimentResult(
        experiment=experiment,
        succeeded=False,
        failed_stage=stage,
        message=message,
        log_path=log_path,
    )


def run_single_experiment(
    experiment: Experiment,
    project_root: Path,
    *,
    clean_previous: bool = True,
    write_logs: bool = True,
) -> ExperimentResult:
    """
    Run one full experiment pipeline.

    Stages:
        1. Clear only this experiment's previous outputs.
        2. Run Java simulation.
        3. Compute PatronData and PatronMetrics.
        4. Compute StatMetrics.
        5. Create OrderMetrics, PatronMetrics, and StatMetrics graphs.
    """
    project_root = project_root.resolve()
    results_dir = project_root / "results"
    logs_dir = project_root / "logs"

    if not project_root.exists():
        return _failure_result(
            experiment=experiment,
            logs_dir=logs_dir,
            stage="setup",
            message=f"Project root does not exist: {project_root}",
            write_logs=write_logs,
        )

    makefile = project_root / "Makefile"

    if not makefile.exists():
        return _failure_result(
            experiment=experiment,
            logs_dir=logs_dir,
            stage="setup",
            message=f"Makefile not found at {makefile}",
            write_logs=write_logs,
        )

    if clean_previous:
        clear_experiment_outputs(results_dir, experiment)
        clear_experiment_failure_log(logs_dir, experiment)
    else:
        ensure_results_dirs(results_dir)

    return_code = run_java_experiment(
        experiment=experiment,
        project_root=project_root,
    )

    if return_code != 0:
        return _failure_result(
            experiment=experiment,
            logs_dir=logs_dir,
            stage="java_run",
            message=f"Java run failed with return code {return_code}.",
            write_logs=write_logs,
        )

    try:
        compute_patron_metrics_for_file(
            results_dir=results_dir,
            file_name=experiment.file_name,
        )
    except Exception as exc:
        return _failure_result(
            experiment=experiment,
            logs_dir=logs_dir,
            stage="patron_metrics",
            message=repr(exc),
            write_logs=write_logs,
        )

    try:
        compute_stats_metrics_for_file(
            results_dir=results_dir,
            file_name=experiment.file_name,
        )
    except Exception as exc:
        return _failure_result(
            experiment=experiment,
            logs_dir=logs_dir,
            stage="stat_metrics",
            message=repr(exc),
            write_logs=write_logs,
        )

    try:
        create_graphs_for_file(
            results_dir=results_dir,
            file_name=experiment.file_name,
        )
    except Exception as exc:
        return _failure_result(
            experiment=experiment,
            logs_dir=logs_dir,
            stage="metric_graphs",
            message=repr(exc),
            write_logs=write_logs,
        )

    return ExperimentResult(
        experiment=experiment,
        succeeded=True,
    )


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_project_root = script_path.parents[1]

    parser = argparse.ArgumentParser(
        description="Run one scheduling experiment and compute metrics/graphs."
    )

    parser.add_argument(
        "positional_args",
        nargs="*",
        help="Optional shorthand: no_patrons scheduler_code context_switch_time seed",
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=default_project_root,
        help="Project root containing the Makefile. Default: inferred from script location.",
    )

    parser.add_argument("--no-patrons", type=int, default=None)
    parser.add_argument("--scheduler-code", type=int, default=None)
    parser.add_argument("--context-switch-time", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)

    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not clear existing output files for this experiment before running.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate the single experiment plan. Do not run make or delete result files.",
    )

    return parser.parse_args()


def resolved_experiment_values(args: argparse.Namespace) -> tuple[int, int, int, int]:
    """
    Resolve experiment values from either positional shorthand or named flags.

    Named flags override positional values when both are provided.
    """
    positional = args.positional_args

    if positional and len(positional) != 4:
        raise ValueError(
            "Positional shorthand requires exactly 4 values: "
            "no_patrons scheduler_code context_switch_time seed."
        )

    positional_values: list[int | None] = [None, None, None, None]

    if positional:
        try:
            positional_values = [int(value) for value in positional]
        except ValueError as exc:
            raise ValueError("All positional shorthand values must be integers.") from exc

    no_patrons = args.no_patrons if args.no_patrons is not None else positional_values[0]
    scheduler_code = (
        args.scheduler_code if args.scheduler_code is not None else positional_values[1]
    )
    context_switch_time = (
        args.context_switch_time
        if args.context_switch_time is not None
        else positional_values[2]
    )
    seed = args.seed if args.seed is not None else positional_values[3]

    missing = []
    if no_patrons is None:
        missing.append("no_patrons")
    if scheduler_code is None:
        missing.append("scheduler_code")
    if context_switch_time is None:
        missing.append("context_switch_time")
    if seed is None:
        missing.append("seed")

    if missing:
        raise ValueError(
            "Missing required experiment value(s): "
            + ", ".join(missing)
            + ". Use either positional shorthand or named flags."
        )

    return int(no_patrons), int(scheduler_code), int(context_switch_time), int(seed)


def main() -> int:
    args = parse_args()

    try:
        no_patrons, scheduler_code, context_switch_time, seed = resolved_experiment_values(args)
        experiment = make_experiment(
            no_patrons=no_patrons,
            scheduler_code=scheduler_code,
            context_switch_time=context_switch_time,
            seed=seed,
        )
    except Exception as exc:
        print(
            f"Completed with 1 failed attempt. Could not build experiment: {exc}",
            file=sys.stderr,
        )
        return 1

    if args.dry_run:
        print(
            "Dry run completed successfully. "
            f"Planned 1 simulation run: {experiment.args_string} "
            f"-> {experiment.file_name}"
        )
        return 0

    result = run_single_experiment(
        experiment=experiment,
        project_root=args.project_root,
        clean_previous=not args.no_clean,
        write_logs=True,
    )

    if not result.succeeded:
        print("Completed with 1 failed attempt. Check logs/ for details.")
        return 1

    print("Completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
