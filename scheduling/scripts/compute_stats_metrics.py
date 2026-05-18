
"""
compute_stats_metrics.py

Helper module only.

This file computes run-level statistics from:
    results/OrderData/<ALG>_<noPatrons>_<seed>.txt
    results/OrderMetrics/<ALG>_<noPatrons>_<seed>.txt
    results/PatronData/<ALG>_<noPatrons>_<seed>.txt
    results/PatronMetrics/<ALG>_<noPatrons>_<seed>.txt

Generated output:
    results/StatMetrics/<ALG>_<noPatrons>_<seed>.txt

It intentionally has:
    - no main()
    - no argparse
    - no command-line interface
    - no log creation
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import median
from typing import Any


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


def values_as_float(rows: list[dict[str, str]], column: str) -> list[float]:
    return [float(row[column]) for row in rows]


def mean(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def population_std(values: list[float]) -> float:
    if not values:
        return 0.0

    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def coefficient_of_variation(values: list[float]) -> float:
    avg = mean(values)

    if avg == 0:
        return 0.0

    return population_std(values) / avg


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


def metric_summary(values: list[float], prefix: str) -> dict[str, float]:
    if not values:
        return {
            f"{prefix}_average": 0.0,
            f"{prefix}_median": 0.0,
            f"{prefix}_max": 0.0,
            f"{prefix}_std": 0.0,
            f"{prefix}_min": 0.0,
            f"{prefix}_q1": 0.0,
            f"{prefix}_q3": 0.0,
        }

    return {
        f"{prefix}_average": mean(values),
        f"{prefix}_median": float(median(values)),
        f"{prefix}_max": max(values),
        f"{prefix}_std": population_std(values),
        f"{prefix}_min": min(values),
        f"{prefix}_q1": percentile(values, 0.25),
        f"{prefix}_q3": percentile(values, 0.75),
    }


def fairness_from_total_waiting(total_waiting_times: list[float]) -> dict[str, float]:
    """
    Simple fairness over patrons:
        lower std/range means waiting time was distributed more evenly.
    """
    if not total_waiting_times:
        return {
            "fairness_waiting_std": 0.0,
            "fairness_waiting_range": 0.0,
        }

    return {
        "fairness_waiting_std": population_std(total_waiting_times),
        "fairness_waiting_range": max(total_waiting_times) - min(total_waiting_times),
    }


def throughput_metrics(
    completed_orders: int,
    completed_patrons: int,
    final_completion_time_ms: float,
) -> dict[str, float]:
    if final_completion_time_ms <= 0:
        return {
            "throughput_orders_per_ms": 0.0,
            "throughput_orders_per_second": 0.0,
            "throughput_patrons_per_ms": 0.0,
            "throughput_patrons_per_second": 0.0,
        }

    orders_per_ms = completed_orders / final_completion_time_ms
    patrons_per_ms = completed_patrons / final_completion_time_ms

    return {
        "throughput_orders_per_ms": orders_per_ms,
        "throughput_orders_per_second": orders_per_ms * 1000.0,
        "throughput_patrons_per_ms": patrons_per_ms,
        "throughput_patrons_per_second": patrons_per_ms * 1000.0,
    }


def predictability_metrics(
    total_waiting_times: list[float],
    total_response_times: list[float],
    total_turnaround_times: list[float],
    process_turnaround_times: list[float],
) -> dict[str, float]:
    """
    Predictability = variability across patrons.
    Lower coefficient of variation means more predictable behaviour.
    """
    return {
        "predictability_waiting_cv": coefficient_of_variation(total_waiting_times),
        "predictability_response_cv": coefficient_of_variation(total_response_times),
        "predictability_total_turnaround_cv": coefficient_of_variation(total_turnaround_times),
        "predictability_process_turnaround_cv": coefficient_of_variation(process_turnaround_times),
    }


def starvation_metrics(total_waiting_times: list[float]) -> dict[str, float]:
    """
    Finite simulations cannot prove permanent starvation.
    This flags starvation risk using an outlier threshold:
        threshold = Q3 + 1.5 * IQR
    """
    if not total_waiting_times:
        return {
            "starvation_threshold_total_waiting": 0.0,
            "starvation_candidate_count": 0,
            "starvation_candidate_rate": 0.0,
            "starvation_max_to_median_waiting_ratio": 0.0,
        }

    q1 = percentile(total_waiting_times, 0.25)
    q3 = percentile(total_waiting_times, 0.75)
    iqr = q3 - q1
    threshold = q3 + 1.5 * iqr

    candidate_count = sum(1 for value in total_waiting_times if value > threshold)
    candidate_rate = candidate_count / len(total_waiting_times)

    max_wait = max(total_waiting_times)
    median_wait = float(median(total_waiting_times))

    if median_wait == 0:
        max_to_median_ratio = 0.0 if max_wait == 0 else max_wait
    else:
        max_to_median_ratio = max_wait / median_wait

    return {
        "starvation_threshold_total_waiting": threshold,
        "starvation_candidate_count": candidate_count,
        "starvation_candidate_rate": candidate_rate,
        "starvation_max_to_median_waiting_ratio": max_to_median_ratio,
    }


def parse_file_name(file_name: str) -> tuple[str, int, int]:
    """
    Parse file names like:
        FCFS_10_4.txt
        SJF_30_2.txt
        PRIORITY_50_3.txt

    Returns:
        (algorithm, noPatrons, seed)
    """
    stem = Path(file_name).stem
    parts = stem.split("_")

    if len(parts) < 3:
        raise ValueError(
            f"Bad stats file name {file_name!r}. "
            "Expected ALG_noPatrons_seed.txt"
        )

    algorithm = "_".join(parts[:-2])
    no_patrons = int(parts[-2])
    seed = int(parts[-1])

    return algorithm, no_patrons, seed


def compute_stats_metrics_for_file(
    results_dir: Path,
    file_name: str,
) -> Path:
    """
    Compute run-level StatMetrics for one experiment file.

    Returns:
        path to generated StatMetrics file.
    """
    order_data_file = results_dir / "OrderData" / file_name
    order_metrics_file = results_dir / "OrderMetrics" / file_name
    patron_data_file = results_dir / "PatronData" / file_name
    patron_metrics_file = results_dir / "PatronMetrics" / file_name
    stats_file = results_dir / "StatMetrics" / file_name

    if not order_data_file.exists():
        raise FileNotFoundError(f"Missing order data file: {order_data_file}")

    if not order_metrics_file.exists():
        raise FileNotFoundError(f"Missing order metrics file: {order_metrics_file}")

    if not patron_data_file.exists():
        raise FileNotFoundError(f"Missing patron data file: {patron_data_file}")

    if not patron_metrics_file.exists():
        raise FileNotFoundError(f"Missing patron metrics file: {patron_metrics_file}")

    order_data_rows = read_tsv(order_data_file)
    order_metric_rows = read_tsv(order_metrics_file)
    patron_data_rows = read_tsv(patron_data_file)
    patron_metric_rows = read_tsv(patron_metrics_file)

    require_columns(
        order_data_rows,
        [
            "primary_key",
            "patron_arrival_time",
            "drink_name",
            "order_arrival_time",
            "prepTime",
            "order_completion_time",
        ],
        order_data_file,
    )

    require_columns(
        order_metric_rows,
        [
            "primary_key",
            "waiting_time",
            "response_time",
            "turnaround_time",
        ],
        order_metrics_file,
    )

    require_columns(
        patron_data_rows,
        [
            "patron_id",
            "patron_arrival_time",
            "num_of_drinks",
            "first_order_arrival_time",
            "last_order_completion_time",
            "total_prepTime",
        ],
        patron_data_file,
    )

    require_columns(
        patron_metric_rows,
        [
            "patron_id",
            "total_waiting_time",
            "total_response_time",
            "total_turnaround_time",
            "process_turnaround_time",
        ],
        patron_metrics_file,
    )

    algorithm, no_patrons, seed = parse_file_name(file_name)

    completed_orders = len(order_data_rows)
    completed_patrons = len(patron_data_rows)

    order_completion_times = values_as_float(order_data_rows, "order_completion_time")
    final_completion_time_ms = max(order_completion_times) if order_completion_times else 0.0

    total_waiting_times = values_as_float(patron_metric_rows, "total_waiting_time")
    total_response_times = values_as_float(patron_metric_rows, "total_response_time")
    total_turnaround_times = values_as_float(patron_metric_rows, "total_turnaround_time")
    process_turnaround_times = values_as_float(patron_metric_rows, "process_turnaround_time")

    row: dict[str, Any] = {
        "algorithm": algorithm,
        "noPatrons": no_patrons,
        "seed": seed,
        "completed_orders": completed_orders,
        "completed_patrons": completed_patrons,
        "final_completion_time_ms": final_completion_time_ms,
    }

    row.update(metric_summary(total_waiting_times, "patron_total_waiting_time"))
    row.update(metric_summary(total_response_times, "patron_total_response_time"))
    row.update(metric_summary(total_turnaround_times, "patron_total_turnaround_time"))
    row.update(metric_summary(process_turnaround_times, "process_turnaround_time"))

    row.update(
        throughput_metrics(
            completed_orders=completed_orders,
            completed_patrons=completed_patrons,
            final_completion_time_ms=final_completion_time_ms,
        )
    )

    row.update(
        predictability_metrics(
            total_waiting_times=total_waiting_times,
            total_response_times=total_response_times,
            total_turnaround_times=total_turnaround_times,
            process_turnaround_times=process_turnaround_times,
        )
    )

    row.update(fairness_from_total_waiting(total_waiting_times))
    row.update(starvation_metrics(total_waiting_times))

    formatted_row: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, float):
            formatted_row[key] = f"{value:.4f}"
        else:
            formatted_row[key] = value

    fieldnames = list(formatted_row.keys())

    write_tsv(stats_file, fieldnames, [formatted_row])
    return stats_file


def compute_all_stats_metrics(results_dir: Path) -> list[Path]:
    """
    Compute StatMetrics for every .txt file in OrderData.
    """
    order_data_dir = results_dir / "OrderData"

    if not order_data_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {order_data_dir}")

    output_files: list[Path] = []

    for order_file in sorted(order_data_dir.glob("*.txt")):
        output_files.append(
            compute_stats_metrics_for_file(
                results_dir=results_dir,
                file_name=order_file.name,
            )
        )

    return output_files
