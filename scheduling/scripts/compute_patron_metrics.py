"""
compute_patron_metrics.py

Helper module only.

This file contains the logic for computing patron-level data and patron-level
metrics from order-level result files.

It intentionally has:
    - no main()
    - no argparse
    - no command-line interface
    - no log creation

Expected input files:
    results/OrderData/<ALG>_<noPatrons>_<seed>.txt
    results/OrderMetrics/<ALG>_<noPatrons>_<seed>.txt

Generated output files:
    results/PatronData/<ALG>_<noPatrons>_<seed>.txt
    results/PatronMetrics/<ALG>_<noPatrons>_<seed>.txt
"""

from __future__ import annotations

import csv
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


def read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a tab-separated text file as a list of dictionaries."""
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    """Write rows to a tab-separated text file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def require_columns(rows: list[dict[str, str]], required: list[str], path: Path) -> None:
    """Validate that the file contains all required columns."""
    if not rows:
        raise ValueError(f"{path} has no data rows.")

    available = set(rows[0].keys())
    missing = [column for column in required if column not in available]

    if missing:
        raise ValueError(
            f"{path} is missing required columns {missing}. "
            f"Found columns: {sorted(available)}"
        )


def split_primary_key(primary_key: str) -> tuple[int, int]:
    """
    Split a primary key of the form patronID_seqNum.

    Example:
        5_3 -> patron_id=5, seq_num=3
    """
    if "_" not in primary_key:
        raise ValueError(
            f"Bad primary_key {primary_key!r}. "
            "Expected format patronID_seqNum, for example 5_3."
        )

    patron_text, seq_text = primary_key.split("_", 1)
    return int(patron_text), int(seq_text)


def to_int(value: str, column_name: str, primary_key: str, file_path: Path) -> int:
    """Convert a table value to int and give a useful error if it fails."""
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid integer in {file_path}: "
            f"primary_key={primary_key}, column={column_name}, value={value!r}"
        ) from exc


def safe_average(total: int, count: int) -> float:
    """Avoid division by zero when calculating averages."""
    if count == 0:
        return 0.0

    return total / count


def compute_patron_metrics_for_file(
    results_dir: Path,
    file_name: str,
) -> tuple[Path, Path, int]:
    """
    Compute PatronData and PatronMetrics for one experiment output file.

    Parameters:
        results_dir:
            Parent results directory.

        file_name:
            Shared file name in OrderData and OrderMetrics.
            Example: FCFS_10_4.txt

    Returns:
        (patron_data_file, patron_metrics_file, patron_count)
    """
    order_file = results_dir / "OrderData" / file_name
    metrics_file = results_dir / "OrderMetrics" / file_name

    patron_data_file = results_dir / "PatronData" / file_name
    patron_metrics_file = results_dir / "PatronMetrics" / file_name

    if not order_file.exists():
        raise FileNotFoundError(f"Missing order data file: {order_file}")

    if not metrics_file.exists():
        raise FileNotFoundError(f"Missing order metrics file: {metrics_file}")

    order_rows = read_tsv(order_file)
    metric_rows = read_tsv(metrics_file)

    require_columns(order_rows, REQUIRED_ORDER_COLUMNS, order_file)
    require_columns(metric_rows, REQUIRED_METRIC_COLUMNS, metrics_file)

    metrics_by_key: dict[str, dict[str, str]] = {}

    for metric_row in metric_rows:
        primary_key = metric_row["primary_key"]

        if primary_key in metrics_by_key:
            raise ValueError(
                f"Duplicate primary_key {primary_key!r} found in {metrics_file}."
            )

        metrics_by_key[primary_key] = metric_row

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

        # Patron arrival should be identical for all rows from the same patron.
        # If bad data says otherwise, keep the earliest arrival time.
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

        patron["total_waiting_time"] = (
            int(patron["total_waiting_time"]) + waiting_time
        )

        patron["total_response_time"] = (
            int(patron["total_response_time"]) + response_time
        )

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
        total_waiting_time = int(patron["total_waiting_time"])
        total_response_time = int(patron["total_response_time"])
        total_turnaround_time = int(patron["total_turnaround_time"])

        process_turnaround_time = (
            int(patron["last_order_completion_time"])
            - int(patron["patron_arrival_time"])
        )

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


def compute_all_patron_metrics(results_dir: Path) -> list[tuple[Path, Path, int]]:
    """
    Compute PatronData and PatronMetrics files for every .txt file in OrderData.
    """
    order_data_dir = results_dir / "OrderData"
    order_metrics_dir = results_dir / "OrderMetrics"

    if not order_data_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {order_data_dir}")

    if not order_metrics_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {order_metrics_dir}")

    outputs: list[tuple[Path, Path, int]] = []

    for order_file in sorted(order_data_dir.glob("*.txt")):
        metrics_file = order_metrics_dir / order_file.name

        if not metrics_file.exists():
            raise FileNotFoundError(
                f"Missing metrics file for {order_file.name}: {metrics_file}"
            )

        outputs.append(
            compute_patron_metrics_for_file(
                results_dir=results_dir,
                file_name=order_file.name,
            )
        )

    return outputs
