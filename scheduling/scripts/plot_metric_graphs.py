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

Generated graph names use the same base file name as the input metric file,
but with a .png extension because the output is an image.

No main(). No argparse. No logs.
"""

from __future__ import annotations

import csv
import math
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


PREFERRED_X_COLUMNS = [
    "primary_key",
    "patron_id",
    "scheduler_name",
    "algorithm",
]


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

    This is the function run_experiments.py should call after a simulation run
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
    """Create all OrderMetrics, PatronMetrics, and StatMetrics graphs."""
    return {
        "order_metrics_graphs": create_all_order_metrics_graphs(results_dir),
        "patron_metrics_graphs": create_all_patron_metrics_graphs(results_dir),
        "stats_metrics_graphs": create_all_stats_metrics_graphs(results_dir),
    }
