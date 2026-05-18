#!/usr/bin/env python3
"""
Compute patron-level data and patron-level metrics from order-level result files.

Expected project layout:

    <project_root>/
    ├── results/
    │   ├── OrderData/
    │   │   └── FCFS_10_4.txt
    │   ├── OrderMetrics/
    │   │   └── FCFS_10_4.txt
    │   ├── PatronData/              <-- created/overwritten by this script
    │   └── PatronMetrics/           <-- created/overwritten by this script
    └── scripts/
        └── compute_patron_metrics.py

Input files are tab-separated .txt files.

OrderData columns expected:
    primary_key
    patron_arrival_time
    drink_name
    order_arrival_time
    prepTime
    order_completion_time

OrderMetrics columns expected:
    primary_key
    waiting_time
    response_time
    turnaround_time

Output PatronData columns:
    patron_id
    patron_arrival_time
    num_of_drinks
    first_order_arrival_time
    last_order_completion_time
    total_prepTime

Output PatronMetrics columns:
    patron_id
    total_waiting_time
    total_response_time
    total_turnaround_time
    process_turnaround_time
    average_waiting_time
    average_response_time
    average_turnaround_time
    max_waiting_time
    max_response_time
    max_turnaround_time

Run from project root:
    python scripts/compute_patron_metrics.py

Or specify a results directory:
    python scripts/compute_patron_metrics.py --results-dir results
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


REQUIRED_ORDER_COLUMNS = [
    "primary_key",
    "patron_arrival_time",
    "drink_name",
    "order_arrival_time",
    "prepTime",
    "order_completion_time",
]

REQUIRED_METRIC_COLUMNS = [
    "primary_key",
    "waiting_time",
    "response_time",
    "turnaround_time",
]


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()

    # Expected:
    #   <project_root>/scripts/compute_patron_metrics.py
    # parents[0] = scripts
    # parents[1] = project root
    default_project_root = script_path.parents[1]
    default_results_dir = default_project_root / "results"

    parser = argparse.ArgumentParser(
        description="Compute PatronData and PatronMetrics files from OrderData and OrderMetrics."
    )

    parser.add_argument(
        "--results-dir",
        type=Path,
        default=default_results_dir,
        help="Path to the results directory. Default: <project_root>/results.",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail immediately if any matching file has bad data.",
    )

    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def require_columns(rows: list[dict[str, str]], required: list[str], path: Path) -> None:
    if not rows:
        return

    available = set(rows[0].keys())
    missing = [col for col in required if col not in available]

    if missing:
        raise ValueError(
            f"{path} is missing required columns {missing}. "
            f"Found columns: {sorted(available)}"
        )


def split_primary_key(primary_key: str) -> tuple[int, int]:
    """
    Splits primary_key of the form patronID_seqNum.

    Example:
        5_3 -> patron_id=5, seq_num=3
    """
    if "_" not in primary_key:
        raise ValueError(
            f"Bad primary_key '{primary_key}'. Expected format patronID_seqNum, e.g. 5_3."
        )

    patron_text, seq_text = primary_key.split("_", 1)
    return int(patron_text), int(seq_text)


def to_int(value: str, column_name: str, primary_key: str, file_path: Path) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid integer in {file_path}: primary_key={primary_key}, "
            f"column={column_name}, value={value!r}"
        ) from exc


def safe_average(total: int, count: int) -> float:
    if count == 0:
        return 0.0
    return total / count


def compute_one_file(
    order_file: Path,
    metrics_file: Path,
    patron_data_dir: Path,
    patron_metrics_dir: Path,
) -> tuple[Path, Path, int]:
    order_rows = read_tsv(order_file)
    metric_rows = read_tsv(metrics_file)

    require_columns(order_rows, REQUIRED_ORDER_COLUMNS, order_file)
    require_columns(metric_rows, REQUIRED_METRIC_COLUMNS, metrics_file)

    metrics_by_key = {}

    for row in metric_rows:
        primary_key = row["primary_key"]

        if primary_key in metrics_by_key:
            raise ValueError(
                f"Duplicate primary_key {primary_key!r} found in {metrics_file}."
            )

        metrics_by_key[primary_key] = row

    patrons: dict[int, dict[str, Any]] = {}

    for order_row in order_rows:
        primary_key = order_row["primary_key"]
        patron_id, _seq_num = split_primary_key(primary_key)

        metric_row = metrics_by_key.get(primary_key)
        if metric_row is None:
            raise ValueError(
                f"No matching metrics row found for primary_key {primary_key!r} "
                f"in {metrics_file}."
            )

        patron_arrival_time = to_int(
            order_row["patron_arrival_time"],
            "patron_arrival_time",
            primary_key,
            order_file,
        )

        order_arrival_time = to_int(
            order_row["order_arrival_time"],
            "order_arrival_time",
            primary_key,
            order_file,
        )

        prep_time = to_int(
            order_row["prepTime"],
            "prepTime",
            primary_key,
            order_file,
        )

        order_completion_time = to_int(
            order_row["order_completion_time"],
            "order_completion_time",
            primary_key,
            order_file,
        )

        waiting_time = to_int(
            metric_row["waiting_time"],
            "waiting_time",
            primary_key,
            metrics_file,
        )

        response_time = to_int(
            metric_row["response_time"],
            "response_time",
            primary_key,
            metrics_file,
        )

        turnaround_time = to_int(
            metric_row["turnaround_time"],
            "turnaround_time",
            primary_key,
            metrics_file,
        )

        if patron_id not in patrons:
            patrons[patron_id] = {
                "patron_id": patron_id,
                "patron_arrival_time": patron_arrival_time,
                "num_of_drinks": 0,
                "first_order_arrival_time": order_arrival_time,
                "last_order_completion_time": order_completion_time,
                "total_prepTime": 0,
                "total_waiting_time": 0,
                "total_response_time": 0,
                "total_turnaround_time": 0,
                "max_waiting_time": waiting_time,
                "max_response_time": response_time,
                "max_turnaround_time": turnaround_time,
            }

        patron = patrons[patron_id]

        # Keep the earliest patron arrival in case duplicate rows disagree.
        # They should not disagree, but this avoids silently trusting nonsense.
        patron["patron_arrival_time"] = min(
            int(patron["patron_arrival_time"]),
            patron_arrival_time,
        )

        patron["num_of_drinks"] = int(patron["num_of_drinks"]) + 1

        patron["first_order_arrival_time"] = min(
            int(patron["first_order_arrival_time"]),
            order_arrival_time,
        )

        patron["last_order_completion_time"] = max(
            int(patron["last_order_completion_time"]),
            order_completion_time,
        )

        patron["total_prepTime"] = int(patron["total_prepTime"]) + prep_time
        patron["total_waiting_time"] = int(patron["total_waiting_time"]) + waiting_time
        patron["total_response_time"] = int(patron["total_response_time"]) + response_time
        patron["total_turnaround_time"] = (
            int(patron["total_turnaround_time"]) + turnaround_time
        )

        patron["max_waiting_time"] = max(
            int(patron["max_waiting_time"]),
            waiting_time,
        )

        patron["max_response_time"] = max(
            int(patron["max_response_time"]),
            response_time,
        )

        patron["max_turnaround_time"] = max(
            int(patron["max_turnaround_time"]),
            turnaround_time,
        )

    patron_data_rows: list[dict[str, Any]] = []
    patron_metric_rows: list[dict[str, Any]] = []

    for patron_id in sorted(patrons):
        patron = patrons[patron_id]
        num_of_drinks = int(patron["num_of_drinks"])

        process_turnaround_time = (
            int(patron["last_order_completion_time"])
            - int(patron["patron_arrival_time"])
        )

        total_waiting_time = int(patron["total_waiting_time"])
        total_response_time = int(patron["total_response_time"])
        total_turnaround_time = int(patron["total_turnaround_time"])

        patron_data_rows.append(
            {
                "patron_id": patron_id,
                "patron_arrival_time": patron["patron_arrival_time"],
                "num_of_drinks": num_of_drinks,
                "first_order_arrival_time": patron["first_order_arrival_time"],
                "last_order_completion_time": patron["last_order_completion_time"],
                "total_prepTime": patron["total_prepTime"],
            }
        )

        patron_metric_rows.append(
            {
                "patron_id": patron_id,
                "total_waiting_time": total_waiting_time,
                "total_response_time": total_response_time,
                "total_turnaround_time": total_turnaround_time,
                "process_turnaround_time": process_turnaround_time,
                "average_waiting_time": f"{safe_average(total_waiting_time, num_of_drinks):.4f}",
                "average_response_time": f"{safe_average(total_response_time, num_of_drinks):.4f}",
                "average_turnaround_time": f"{safe_average(total_turnaround_time, num_of_drinks):.4f}",
                "max_waiting_time": patron["max_waiting_time"],
                "max_response_time": patron["max_response_time"],
                "max_turnaround_time": patron["max_turnaround_time"],
            }
        )

    patron_data_file = patron_data_dir / order_file.name
    patron_metrics_file = patron_metrics_dir / order_file.name

    write_tsv(
        patron_data_file,
        [
            "patron_id",
            "patron_arrival_time",
            "num_of_drinks",
            "first_order_arrival_time",
            "last_order_completion_time",
            "total_prepTime",
        ],
        patron_data_rows,
    )

    write_tsv(
        patron_metrics_file,
        [
            "patron_id",
            "total_waiting_time",
            "total_response_time",
            "total_turnaround_time",
            "process_turnaround_time",
            "average_waiting_time",
            "average_response_time",
            "average_turnaround_time",
            "max_waiting_time",
            "max_response_time",
            "max_turnaround_time",
        ],
        patron_metric_rows,
    )

    return patron_data_file, patron_metrics_file, len(patron_data_rows)


def compute_patron_metrics(results_dir: Path, strict: bool = False) -> int:
    order_data_dir = results_dir / "OrderData"
    order_metrics_dir = results_dir / "ordermetrics_dir"

    patron_data_dir = results_dir / "PatronData"
    patron_metrics_dir = results_dir / "patronmetrics_dir"

    if not order_data_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {order_data_dir}")

    if not order_metrics_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {order_metrics_dir}")

    patron_data_dir.mkdir(parents=True, exist_ok=True)
    patron_metrics_dir.mkdir(parents=True, exist_ok=True)

    order_files = sorted(order_data_dir.glob("*.txt"))

    if not order_files:
        print(f"No OrderData .txt files found in {order_data_dir}")
        return 0

    processed_count = 0
    failed_count = 0

    for order_file in order_files:
        metrics_file = order_metrics_dir / order_file.name

        if not metrics_file.exists():
            message = f"Skipping {order_file.name}: missing metrics file {metrics_file}"
            if strict:
                raise FileNotFoundError(message)
            print(message)
            failed_count += 1
            continue

        try:
            patron_data_file, patron_metrics_file, patron_count = compute_one_file(
                order_file=order_file,
                metrics_file=metrics_file,
                patron_data_dir=patron_data_dir,
                patron_metrics_dir=patron_metrics_dir,
            )

            processed_count += 1

            print(
                f"Processed {order_file.name}: "
                f"{patron_count} patrons -> "
                f"{patron_data_file}, {patron_metrics_file}"
            )

        except Exception as exc:
            failed_count += 1
            if strict:
                raise

            print(f"Failed to process {order_file.name}: {exc}", file=sys.stderr)

    print(
        f"Done. Processed files: {processed_count}. "
        f"Skipped/failed files: {failed_count}."
    )

    return processed_count


def main() -> int:
    args = parse_args()

    try:
        compute_patron_metrics(
            results_dir=args.results_dir.resolve(),
            strict=args.strict,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
