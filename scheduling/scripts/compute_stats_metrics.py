"""
compute_stats_metrics.py

Helper module only.

Computes one simple run-level statistics file from:
    results/PatronData/<ALG>_<noPatrons>_<seed>.txt
    results/PatronMetrics/<ALG>_<noPatrons>_<seed>.txt

Generated output:
    results/StatMetrics/<ALG>_<noPatrons>_<seed>.txt

No main(). No argparse. No logs.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


REQUIRED_PATRON_DATA_COLUMNS = [
    "patron_id",
    "num_of_drinks",
    "last_order_completion_time",
]

REQUIRED_PATRON_METRIC_COLUMNS = [
    "patron_id",
    "total_waiting_time",
    "total_response_time",
    "total_turnaround_time",
]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def require_columns(rows: list[dict[str, str]], required: list[str], path: Path) -> None:
    if not rows:
        raise ValueError(f"{path} has no data rows.")

    available = set(rows[0].keys())
    missing = [column for column in required if column not in available]

    if missing:
        raise ValueError(
            f"{path} is missing required columns {missing}. "
            f"Found columns: {sorted(available)}"
        )


def values_as_float(rows: list[dict[str, str]], column: str, path: Path) -> list[float]:
    values: list[float] = []

    for line_number, row in enumerate(rows, start=2):
        raw_value = row.get(column, "")

        try:
            values.append(float(raw_value))
        except ValueError as exc:
            raise ValueError(
                f"Invalid number in {path}, line {line_number}, "
                f"column {column!r}: {raw_value!r}"
            ) from exc

    return values


def values_as_int(rows: list[dict[str, str]], column: str, path: Path) -> list[int]:
    values: list[int] = []

    for line_number, row in enumerate(rows, start=2):
        raw_value = row.get(column, "")

        try:
            values.append(int(raw_value))
        except ValueError as exc:
            raise ValueError(
                f"Invalid integer in {path}, line {line_number}, "
                f"column {column!r}: {raw_value!r}"
            ) from exc

    return values


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def minimum(values: list[float]) -> float:
    return min(values) if values else 0.0


def maximum(values: list[float]) -> float:
    return max(values) if values else 0.0


def population_std(values: list[float]) -> float:
    if not values:
        return 0.0

    avg = average(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def coefficient_of_variation(values: list[float]) -> float:
    avg = average(values)

    if avg == 0:
        return 0.0

    return population_std(values) / avg


def predictability_ratio(values: list[float]) -> float:
    """
    Predictability based on variation in patrons' total waiting time.

    1.0 = perfectly predictable.
    Lower = more variable.
    """
    return 1.0 / (1.0 + coefficient_of_variation(values))


def fairness_ratio(values: list[float]) -> float:
    """
    Jain-style fairness ratio over patrons' total waiting times.

    1.0 = equal waiting distribution.
    Lower = less fair.
    """
    if not values:
        return 0.0

    total = sum(values)
    squared_total = sum(value ** 2 for value in values)

    if squared_total == 0:
        return 1.0

    return (total ** 2) / (len(values) * squared_total)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0

    sorted_values = sorted(values)

    if len(sorted_values) == 1:
        return sorted_values[0]

    position = q * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return sorted_values[int(position)]

    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def starvation_possibility(values: list[float]) -> float:
    """
    Fraction of patrons whose total waiting time is an outlier:
        waiting_time > Q3 + 1.5 * IQR

    This is starvation *risk*, not proof of infinite starvation.
    """
    if not values:
        return 0.0

    q1 = percentile(values, 0.25)
    q3 = percentile(values, 0.75)
    threshold = q3 + 1.5 * (q3 - q1)

    candidates = sum(1 for value in values if value > threshold)
    return candidates / len(values)


def compute_stats_metrics_for_file(
    results_dir: Path,
    file_name: str,
) -> Path:
    """
    Compute one simple StatMetrics file for one simulation run.

    This uses PatronData + PatronMetrics only.
    It does not re-read OrderData because PatronData already contains:
        num_of_drinks
        last_order_completion_time
    """
    patron_data_file = results_dir / "PatronData" / file_name
    patron_metrics_file = results_dir / "PatronMetrics" / file_name
    stats_file = results_dir / "StatMetrics" / file_name

    if not patron_data_file.exists():
        raise FileNotFoundError(f"Missing patron data file: {patron_data_file}")

    if not patron_metrics_file.exists():
        raise FileNotFoundError(f"Missing patron metrics file: {patron_metrics_file}")

    patron_data_rows = read_tsv(patron_data_file)
    patron_metric_rows = read_tsv(patron_metrics_file)

    require_columns(patron_data_rows, REQUIRED_PATRON_DATA_COLUMNS, patron_data_file)
    require_columns(patron_metric_rows, REQUIRED_PATRON_METRIC_COLUMNS, patron_metrics_file)

    waiting_values = values_as_float(
        patron_metric_rows,
        "total_waiting_time",
        patron_metrics_file,
    )

    response_values = values_as_float(
        patron_metric_rows,
        "total_response_time",
        patron_metrics_file,
    )

    turnaround_values = values_as_float(
        patron_metric_rows,
        "total_turnaround_time",
        patron_metrics_file,
    )

    num_drinks_values = values_as_int(
        patron_data_rows,
        "num_of_drinks",
        patron_data_file,
    )

    completion_values = values_as_float(
        patron_data_rows,
        "last_order_completion_time",
        patron_data_file,
    )

    completed_orders = sum(num_drinks_values)
    final_completion_time = maximum(completion_values)

    throughput_ratio = (
        (completed_orders / final_completion_time) * 1000.0
        if final_completion_time > 0
        else 0.0
    )

    row: dict[str, Any] = {
        "avg_waiting_time": average(waiting_values),
        "max_waiting_time": maximum(waiting_values),
        "min_waiting_time": minimum(waiting_values),

        "avg_response_time": average(response_values),
        "max_response_time": maximum(response_values),
        "min_response_time": minimum(response_values),

        "avg_turnaround_time": average(turnaround_values),
        "max_turnaround_time": maximum(turnaround_values),
        "min_turnaround_time": minimum(turnaround_values),

        "throughput_ratio": throughput_ratio,
        "fairness_ratio": fairness_ratio(waiting_values),
        "predictability_ratio": predictability_ratio(waiting_values),
        "starvation_possibility": starvation_possibility(waiting_values),
    }

    formatted_row = {
        key: f"{value:.4f}"
        for key, value in row.items()
    }

    write_tsv(stats_file, list(formatted_row.keys()), [formatted_row])
    return stats_file


def compute_all_stats_metrics(results_dir: Path) -> list[Path]:
    patron_data_dir = results_dir / "PatronData"

    if not patron_data_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {patron_data_dir}")

    return [
        compute_stats_metrics_for_file(results_dir=results_dir, file_name=patron_file.name)
        for patron_file in sorted(patron_data_dir.glob("*.txt"))
    ]
