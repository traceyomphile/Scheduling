"""
plot_metric_graphs.py

Helper module only.

Creates graph image files from:
    results/OrderMetrics/<ALG>_<noPatrons>_<seed>.txt
    results/PatronMetrics/<ALG>_<noPatrons>_<seed>.txt
    results/StatMetrics/<ALG>_<noPatrons>_<seed>.txt

Generated output directories:
    results/OrderMetricsGraphs/
    results/PatronMetricsGraphs/
    results/StatMetricsGraphs/
    results/AlgoMetricsGraphs/

Generated per-file graph names use the same base file name as the input metric
file, but with a .png extension because the output is an image.

Generated algorithm-comparison graphs use one file per selected StatMetrics
metric, for example:
    results/AlgoMetricsGraphs/avg_waiting_time.png

No main(). No argparse. No logs.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

# Required when running from scripts/ or make in a terminal without a GUI.
matplotlib.use("Agg")

import matplotlib.pyplot as plt


GRAPH_DPI = 150


METRIC_GRAPH_DIRS = {
    "OrderMetrics": "OrderMetricsGraphs",
    "PatronMetrics": "PatronMetricsGraphs",
    "StatMetrics": "StatMetricsGraphs",
}


ALGO_METRICS_GRAPH_DIR = "AlgoMetricsGraphs"


ALGO_COMPARISON_METRICS = [
    "avg_waiting_time",
    "median_waiting_time",
    "std_waiting_time",
    "avg_response_time",
    "median_response_time",
    "std_response_time",
    "avg_turnaround_time",
    "median_turnaround_time",
    "std_turnaround_time",
    "fairness_ratio",
    "predictability_ratio",
    "starvation_possibility",
]


METRIC_DISPLAY_NAMES = {
    "avg_waiting_time": "Average waiting time",
    "median_waiting_time": "Median waiting time",
    "std_waiting_time": "Waiting time standard deviation",
    "avg_response_time": "Average response time",
    "median_response_time": "Median response time",
    "std_response_time": "Response time standard deviation",
    "avg_turnaround_time": "Average turnaround time",
    "median_turnaround_time": "Median turnaround time",
    "std_turnaround_time": "Turnaround time standard deviation",
    "fairness_ratio": "Fairness ratio",
    "predictability_ratio": "Predictability ratio",
    "starvation_possibility": "Starvation ratio",
}


METRIC_OUTPUT_NAMES = {
    "avg_waiting_time": "avg_waiting_time",
    "median_waiting_time": "median_waiting_time",
    "std_waiting_time": "std_waiting_time",
    "avg_response_time": "avg_response_time",
    "median_response_time": "median_response_time",
    "std_response_time": "std_response_time",
    "avg_turnaround_time": "avg_turnaround_time",
    "median_turnaround_time": "median_turnaround_time",
    "std_turnaround_time": "std_turnaround_time",
    "fairness_ratio": "fairness_ratio",
    "predictability_ratio": "predictability_ratio",
    # The StatMetrics column is called starvation_possibility, but the graph
    # file uses the assignment wording.
    "starvation_possibility": "starvation_ratio",
}


PREFERRED_X_COLUMNS = [
    "primary_key",
    "patron_id",
    "scheduler_name",
    "algorithm",
]


SCHEDULER_ORDER = ["FCFS", "SJF", "PRIORITY", "MLFQ"]


def read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a tab-separated metric file as a list of dictionaries."""
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def to_float(value: str, column: str, path: Path, line_number: int) -> float:
    """Convert a string value to float with a useful error message."""
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid numeric value in {path}, line {line_number}, "
            f"column {column!r}: {value!r}"
        ) from exc


def require_rows(rows: list[dict[str, str]], path: Path) -> None:
    """Ensure the input file has at least one data row."""
    if not rows:
        raise ValueError(f"{path} has no data rows to plot.")


def choose_x_column(fieldnames: list[str]) -> str | None:
    """Pick the best identifier column for the x-axis, if one exists."""
    for column in PREFERRED_X_COLUMNS:
        if column in fieldnames:
            return column

    return None


def numeric_columns(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    exclude: set[str],
    path: Path,
) -> list[str]:
    """
    Return columns that are numeric for every row.

    Non-numeric identifier columns, such as primary_key, are skipped.
    """
    numeric: list[str] = []

    for column in fieldnames:
        if column in exclude:
            continue

        values = [row.get(column, "") for row in rows]

        if not values:
            continue

        try:
            for value in values:
                float(value)
        except ValueError:
            continue

        numeric.append(column)

    if not numeric:
        raise ValueError(f"No numeric metric columns found in {path}.")

    return numeric


def output_graph_path(results_dir: Path, output_dir_name: str, file_name: str) -> Path:
    """Build the graph output path using the same base name as the input file."""
    graph_dir = results_dir / output_dir_name
    graph_dir.mkdir(parents=True, exist_ok=True)
    return graph_dir / f"{Path(file_name).stem}.png"


def format_axis_labels(axis: Any, x_labels: list[str]) -> None:
    """Keep x-axis labels readable. Too many labels become visual soup."""
    if len(x_labels) <= 30:
        axis.set_xticks(list(range(len(x_labels))))
        axis.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=8)
    else:
        axis.set_xticks([])
        axis.set_xlabel("row index")


def ordered_algorithms(algorithms: set[str]) -> list[str]:
    """Return algorithms in the known scheduler order, then any extras alphabetically."""
    ordered = [algorithm for algorithm in SCHEDULER_ORDER if algorithm in algorithms]
    ordered.extend(sorted(algorithm for algorithm in algorithms if algorithm not in SCHEDULER_ORDER))
    return ordered


def parse_stat_metrics_file_name(file_name: str) -> tuple[str, int, int]:
    """
    Parse <ALG>_<noPatrons>_<seed>.txt.

    rsplit is used so this still works if an algorithm name ever contains an
    underscore. The current scheduler names do not, but future-you is exactly
    the kind of person who will accidentally create that problem at 2 a.m.
    """
    stem = Path(file_name).stem
    parts = stem.rsplit("_", 2)

    if len(parts) != 3:
        raise ValueError(
            f"Bad StatMetrics file name {file_name!r}. "
            "Expected format <ALG>_<noPatrons>_<seed>.txt."
        )

    algorithm, no_patrons_text, seed_text = parts

    try:
        no_patrons = int(no_patrons_text)
        seed = int(seed_text)
    except ValueError as exc:
        raise ValueError(
            f"Bad StatMetrics file name {file_name!r}. "
            "noPatrons and seed must be integers."
        ) from exc

    return algorithm, no_patrons, seed


def experiment_label(no_patrons: int, seed: int) -> str:
    """Create the requested x-axis label: noPatrons_seed."""
    return f"{no_patrons}_{seed}"


def plot_multi_metric_file(
    input_file: Path,
    output_file: Path,
    title: str,
) -> Path:
    """
    Plot one metric file.

    Each numeric metric column gets its own axis inside one figure.
    """
    rows = read_tsv(input_file)
    require_rows(rows, input_file)

    fieldnames = list(rows[0].keys())
    x_column = choose_x_column(fieldnames)
    excluded_columns = {x_column} if x_column is not None else set()
    y_columns = numeric_columns(rows, fieldnames, excluded_columns, input_file)

    x_values = list(range(len(rows)))
    x_labels = [row[x_column] for row in rows] if x_column is not None else [str(i) for i in x_values]

    fig_height = max(3.0, 2.3 * len(y_columns))
    fig_width = max(8.0, min(18.0, 0.35 * len(rows)))

    fig, axes = plt.subplots(
        nrows=len(y_columns),
        ncols=1,
        figsize=(fig_width, fig_height),
        squeeze=False,
    )

    fig.suptitle(title)

    for index, column in enumerate(y_columns):
        axis = axes[index][0]
        y_values = [
            to_float(row[column], column, input_file, line_number)
            for line_number, row in enumerate(rows, start=2)
        ]

        axis.plot(x_values, y_values, marker="o", linewidth=1)
        axis.set_title(column)
        axis.set_ylabel(column)
        axis.grid(True, alpha=0.3)

        if index == len(y_columns) - 1:
            axis.set_xlabel(x_column if x_column is not None else "row index")
            format_axis_labels(axis, x_labels)
        else:
            axis.set_xticks([])

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(output_file, dpi=GRAPH_DPI, bbox_inches="tight")
    plt.close(fig)

    return output_file


def plot_stats_metrics_file(input_file: Path, output_file: Path, title: str) -> Path:
    """
    Plot one StatMetrics file.

    StatMetrics files normally contain one row, so a bar chart is clearer than
    pretending there is a time series. If there are multiple rows, the values are
    averaged per metric column.
    """
    rows = read_tsv(input_file)
    require_rows(rows, input_file)

    fieldnames = list(rows[0].keys())
    y_columns = numeric_columns(rows, fieldnames, set(), input_file)

    values: list[float] = []
    for column in y_columns:
        column_values = [
            to_float(row[column], column, input_file, line_number)
            for line_number, row in enumerate(rows, start=2)
        ]
        values.append(sum(column_values) / len(column_values))

    fig_width = max(10.0, 0.65 * len(y_columns))
    fig, axis = plt.subplots(figsize=(fig_width, 5.5))

    x_values = list(range(len(y_columns)))
    axis.bar(x_values, values)
    axis.set_title(title)
    axis.set_ylabel("value")
    axis.set_xticks(x_values)
    axis.set_xticklabels(y_columns, rotation=45, ha="right", fontsize=8)
    axis.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_file, dpi=GRAPH_DPI, bbox_inches="tight")
    plt.close(fig)

    return output_file


def create_order_metrics_graph_for_file(results_dir: Path, file_name: str) -> Path:
    """Create one graph image for one OrderMetrics file."""
    input_file = results_dir / "OrderMetrics" / file_name

    if not input_file.exists():
        raise FileNotFoundError(f"Missing OrderMetrics file: {input_file}")

    output_file = output_graph_path(results_dir, "OrderMetricsGraphs", file_name)
    return plot_multi_metric_file(
        input_file=input_file,
        output_file=output_file,
        title=f"Order metrics: {Path(file_name).stem}",
    )


def create_patron_metrics_graph_for_file(results_dir: Path, file_name: str) -> Path:
    """Create one graph image for one PatronMetrics file."""
    input_file = results_dir / "PatronMetrics" / file_name

    if not input_file.exists():
        raise FileNotFoundError(f"Missing PatronMetrics file: {input_file}")

    output_file = output_graph_path(results_dir, "PatronMetricsGraphs", file_name)
    return plot_multi_metric_file(
        input_file=input_file,
        output_file=output_file,
        title=f"Patron metrics: {Path(file_name).stem}",
    )


def create_stats_metrics_graph_for_file(results_dir: Path, file_name: str) -> Path:
    """Create one graph image for one StatMetrics file."""
    input_file = results_dir / "StatMetrics" / file_name

    if not input_file.exists():
        raise FileNotFoundError(f"Missing StatMetrics file: {input_file}")

    output_file = output_graph_path(results_dir, "StatMetricsGraphs", file_name)
    return plot_stats_metrics_file(
        input_file=input_file,
        output_file=output_file,
        title=f"Stat metrics: {Path(file_name).stem}",
    )


def create_graphs_for_file(results_dir: Path, file_name: str) -> dict[str, Path]:
    """
    Create OrderMetrics, PatronMetrics, and StatMetrics graphs for one run.

    This is the function run_experiment.py should call after a simulation run
    has successfully produced all three metric files.
    """
    return {
        "order_metrics_graph": create_order_metrics_graph_for_file(results_dir, file_name),
        "patron_metrics_graph": create_patron_metrics_graph_for_file(results_dir, file_name),
        "stats_metrics_graph": create_stats_metrics_graph_for_file(results_dir, file_name),
    }


def create_all_order_metrics_graphs(results_dir: Path) -> list[Path]:
    """Create graphs for every file in results/OrderMetrics."""
    input_dir = results_dir / "OrderMetrics"

    if not input_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {input_dir}")

    return [
        create_order_metrics_graph_for_file(results_dir, input_file.name)
        for input_file in sorted(input_dir.glob("*.txt"))
    ]


def create_all_patron_metrics_graphs(results_dir: Path) -> list[Path]:
    """Create graphs for every file in results/PatronMetrics."""
    input_dir = results_dir / "PatronMetrics"

    if not input_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {input_dir}")

    return [
        create_patron_metrics_graph_for_file(results_dir, input_file.name)
        for input_file in sorted(input_dir.glob("*.txt"))
    ]


def create_all_stats_metrics_graphs(results_dir: Path) -> list[Path]:
    """Create graphs for every file in results/StatMetrics."""
    input_dir = results_dir / "StatMetrics"

    if not input_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {input_dir}")

    return [
        create_stats_metrics_graph_for_file(results_dir, input_file.name)
        for input_file in sorted(input_dir.glob("*.txt"))
    ]


def create_all_metric_graphs(results_dir: Path) -> dict[str, list[Path]]:
    """Create all OrderMetrics, PatronMetrics, and StatMetrics per-file graphs."""
    return {
        "order_metrics_graphs": create_all_order_metrics_graphs(results_dir),
        "patron_metrics_graphs": create_all_patron_metrics_graphs(results_dir),
        "stats_metrics_graphs": create_all_stats_metrics_graphs(results_dir),
    }


def read_stat_metric_value(input_file: Path, metric_name: str) -> float:
    """
    Read one metric value from one StatMetrics file.

    StatMetrics should contain one row. If multiple rows somehow exist, this
    function averages them. That keeps the graph code defensive instead of
    fainting dramatically over one extra line.
    """
    rows = read_tsv(input_file)
    require_rows(rows, input_file)

    if metric_name not in rows[0]:
        raise ValueError(f"{input_file} is missing metric column {metric_name!r}.")

    values = [
        to_float(row[metric_name], metric_name, input_file, line_number)
        for line_number, row in enumerate(rows, start=2)
    ]

    return sum(values) / len(values)


def collect_algo_metric_rows(results_dir: Path) -> list[dict[str, Any]]:
    """
    Collect selected StatMetrics values across all experiment runs.

    Each returned row contains:
        algorithm, no_patrons, seed, experiment_label, and selected metrics.
    """
    input_dir = results_dir / "StatMetrics"

    if not input_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {input_dir}")

    rows: list[dict[str, Any]] = []

    for input_file in sorted(input_dir.glob("*.txt")):
        algorithm, no_patrons, seed = parse_stat_metrics_file_name(input_file.name)
        stat_rows = read_tsv(input_file)
        require_rows(stat_rows, input_file)

        row: dict[str, Any] = {
            "algorithm": algorithm,
            "no_patrons": no_patrons,
            "seed": seed,
            "experiment_label": experiment_label(no_patrons, seed),
        }

        for metric_name in ALGO_COMPARISON_METRICS:
            if metric_name in stat_rows[0]:
                row[metric_name] = read_stat_metric_value(input_file, metric_name)
            else:
                # Keep missing metrics explicit. The plotter will simply skip
                # metrics that have no values anywhere.
                row[metric_name] = math.nan

        rows.append(row)

    if not rows:
        raise ValueError(f"No StatMetrics files found in {input_dir}.")

    return rows


def plot_algorithm_metric_comparison(
    rows: list[dict[str, Any]],
    metric_name: str,
    output_file: Path,
) -> Path:
    """
    Create one grouped bar chart for one StatMetrics metric.

    X-axis: noPatrons_seed.
    Bars: algorithms.
    """
    usable_rows = [row for row in rows if not math.isnan(float(row[metric_name]))]

    if not usable_rows:
        raise ValueError(f"No values found for metric {metric_name!r}.")

    label_pairs = sorted(
        {(int(row["no_patrons"]), int(row["seed"])) for row in usable_rows},
        key=lambda pair: (pair[0], pair[1]),
    )
    x_labels = [experiment_label(no_patrons, seed) for no_patrons, seed in label_pairs]

    algorithms = ordered_algorithms({str(row["algorithm"]) for row in usable_rows})

    values_by_label_and_algo: dict[tuple[str, str], float] = {}
    for row in usable_rows:
        values_by_label_and_algo[(str(row["experiment_label"]), str(row["algorithm"]))] = float(row[metric_name])

    fig_width = max(10.0, min(24.0, 1.1 * len(x_labels)))
    fig, axis = plt.subplots(figsize=(fig_width, 6.0))

    x_positions = list(range(len(x_labels)))
    group_width = 0.82
    bar_width = group_width / max(1, len(algorithms))

    for algo_index, algorithm in enumerate(algorithms):
        offsets = [
            x - (group_width / 2) + (bar_width / 2) + (algo_index * bar_width)
            for x in x_positions
        ]
        values = [
            values_by_label_and_algo.get((label, algorithm), 0.0)
            for label in x_labels
        ]
        axis.bar(offsets, values, width=bar_width, label=algorithm)

    display_name = METRIC_DISPLAY_NAMES.get(metric_name, metric_name)
    axis.set_title(f"{display_name} by experiment and algorithm")
    axis.set_xlabel("noPatrons_seed")
    axis.set_ylabel(display_name)
    axis.set_xticks(x_positions)
    axis.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=8)
    axis.grid(True, axis="y", alpha=0.3)
    axis.legend(title="Algorithm")

    fig.tight_layout()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_file, dpi=GRAPH_DPI, bbox_inches="tight")
    plt.close(fig)

    return output_file


def clear_algo_metrics_graphs(results_dir: Path) -> None:
    """Remove old algorithm-comparison graphs before writing fresh ones."""
    output_dir = results_dir / ALGO_METRICS_GRAPH_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    for graph_file in output_dir.glob("*.png"):
        graph_file.unlink()


def create_algo_metrics_graphs(results_dir: Path) -> dict[str, Path]:
    """
    Create algorithm-comparison graphs from all files in results/StatMetrics.

    This should be called by run_experiments.py after the batch has finished,
    not by run_experiment.py after a single run. A comparison graph with one
    lonely algorithm is just a bar chart having an existential crisis.
    """
    rows = collect_algo_metric_rows(results_dir)
    clear_algo_metrics_graphs(results_dir)

    output_dir = results_dir / ALGO_METRICS_GRAPH_DIR
    outputs: dict[str, Path] = {}

    for metric_name in ALGO_COMPARISON_METRICS:
        # Some projects may rename starvation_possibility later. This function
        # keeps the current assignment-compatible name as the source of truth.
        if all(math.isnan(float(row[metric_name])) for row in rows):
            continue

        output_stem = METRIC_OUTPUT_NAMES.get(metric_name, metric_name)
        output_file = output_dir / f"{output_stem}.png"
        outputs[metric_name] = plot_algorithm_metric_comparison(
            rows=rows,
            metric_name=metric_name,
            output_file=output_file,
        )

    if not outputs:
        raise ValueError("No algorithm-comparison graphs were created.")

    return outputs
