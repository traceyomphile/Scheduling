Project: Bar Scheduling Simulation

Overview
- **Purpose:** Simulate bar drink-order scheduling policies (FCFS, SJF, PRIORITY, MLFQ), compute per-order and per-patron metrics, and produce graphs comparing algorithms.
- **Language:** Java (simulation) + Python (post-processing and plotting).

Prerequisites
- **Java JDK 11+**: required to compile and run the simulation.
- **Python 3.8+**: used for metric computation and plotting.
- **Python package:** `matplotlib` (install with `pip install matplotlib`).
- **GNU make** (recommended). On Windows use WSL, Git Bash with make, or run `javac`/`java` directly.

Quick file map
- **Makefile:** [Makefile](Makefile) — compile and run targets.
- **Java sources:** [src/barScheduling/](src/barScheduling/) — `Barman.java`, `DrinkOrder.java`, `Patron.java`, `SchedulingSimulation.java` (entry point).
- **Python scripts:** [scripts/](scripts/) — `run_experiment.py` (single-run pipeline), `run_experiments.py` (batch runner), `compute_patron_metrics.py`, `compute_stats_metrics.py`, `plot_metric_graphs.py` (helper modules for metrics and plots).
- **Results:** `results/` — generated output subdirectories (OrderData, OrderMetrics, PatronData, PatronMetrics, StatMetrics and graphs folders). See `results/` after running experiments.

How the pipeline works (high level)
- 1) Java simulation produces per-order text outputs in `results/OrderData/` and `results/OrderMetrics/`.
- 2) `compute_patron_metrics.py` converts order-level files into per-patron files under `results/PatronData/` and `results/PatronMetrics/`.
- 3) `compute_stats_metrics.py` creates a run-level summary under `results/StatMetrics/`.
- 4) `plot_metric_graphs.py` creates per-file graphs and algorithm comparison graphs under `results/*Graphs/` and `results/AlgoMetricsGraphs/`.

Running a single experiment (full pipeline)
- Recommended: use the provided Python wrapper which runs the Java simulation then computes metrics and graphs.

Example (positional shorthand):
```bash
python3 scripts/run_experiment.py 10 0 0 1
# meaning: no_patrons=10 scheduler_code=0 context_switch_time=0 seed=1
```

Equivalent using named flags:
```bash
python3 scripts/run_experiment.py --no-patrons 10 --scheduler-code 0 --context-switch-time 0 --seed 1
```

Notes about scheduler codes (match Java):
- 0 = FCFS
- 1 = SJF
- 2 = PRIORITY
- 3 = MLFQ

What `run_experiment.py` does
- Clears only the files belonging to the specified experiment (safe rerun).
- Calls `make run ARGS="<no_patrons> <scheduler_code> <context_switch_time> <seed>"` to launch the Java simulation.
- Runs patron/stat metrics and per-file plots after a successful simulation.

Running only the Java simulation
- If you want only the simulation output (no metrics/plots), run the Makefile target directly from the project root:
```bash
make compile
make run ARGS="10 0 0 1"
# or without make:
javac -d bin src/barScheduling/*.java
java -cp bin barScheduling.SchedulingSimulation 10 0 0 1
```

Running multiple experiments (batch)
- Use the batch orchestrator to build a suite of experiments and run them sequentially, then produce algorithm-comparison graphs.

Example (default behaviour):
```bash
python3 scripts/run_experiments.py
```

Example (custom batch):
```bash
python3 scripts/run_experiments.py --min-patrons 8 --max-patrons 50 --samples-per-seed 3 --seed-start 1 --seed-end 3 --sched-start 0 --sched-end 3 --context-switch-time 0
```

Useful flags for both runners
- `--project-root`: set project root if you run scripts from elsewhere (defaults to repo parent of `scripts/`).
- `--dry-run`: validate the planned runs without executing `make` or deleting files.
- `--no-clean`: do not remove previous files for an experiment before running it.
- `--stop-on-failure` (batch only): stop at first failed run.

Running “just one experiment” (clarification)
- If by "just one experiment" you mean: run only one Java simulation and keep existing results, call `make run ARGS="..."` (see "Running only the Java simulation").
- If you mean run the full pipeline exactly once, use `scripts/run_experiment.py` as shown above.

What each source/script does (concise)
- **SchedulingSimulation.java**: main Java entrypoint. Arguments: `noPatrons scheduler_code context_switch_time seed`. See [src/barScheduling/SchedulingSimulation.java](src/barScheduling/SchedulingSimulation.java).
- **Barman.java**: simulation thread implementing the server/barman and scheduling logic. See [src/barScheduling/Barman.java](src/barScheduling/Barman.java).
- **Patron.java**: patron threads that place drink orders. See [src/barScheduling/Patron.java](src/barScheduling/Patron.java).
- **DrinkOrder.java**: data structure for drink orders used by threads. See [src/barScheduling/DrinkOrder.java](src/barScheduling/DrinkOrder.java).
- **Makefile**: build + run convenience. See [Makefile](Makefile).
- **scripts/run_experiment.py**: orchestrates a single experiment (simulation -> metrics -> graphs). See [scripts/run_experiment.py](scripts/run_experiment.py).
- **scripts/run_experiments.py**: builds and runs batches of experiments, then creates algorithm-comparison graphs. See [scripts/run_experiments.py](scripts/run_experiments.py).
- **scripts/compute_patron_metrics.py**: helper that converts order-level outputs to per-patron data/metrics. See [scripts/compute_patron_metrics.py](scripts/compute_patron_metrics.py).
- **scripts/compute_stats_metrics.py**: helper that computes run-level statistics (fairness, predictability, throughput, etc.) from patron files. See [scripts/compute_stats_metrics.py](scripts/compute_stats_metrics.py).
- **scripts/plot_metric_graphs.py**: helper to generate per-file plots and algorithm comparison plots using `matplotlib`. See [scripts/plot_metric_graphs.py](scripts/plot_metric_graphs.py).

Results layout (after running)
- `results/OrderData/` — per-order raw data from simulation.
- `results/OrderMetrics/` — per-order metrics computed by the Java simulation.
- `results/PatronData/` — aggregated per-patron derived from OrderData.
- `results/PatronMetrics/` — per-patron metrics derived from OrderMetrics.
- `results/StatMetrics/` — one-row run-level statistics files.
- `results/*Graphs/` — PNG graphs for each metric file and algorithm comparisons.

Troubleshooting
- If `make` is unavailable on Windows, either use WSL/Git Bash or run `javac`/`java` commands shown above.
- If plotting fails with a GUI error, ensure `matplotlib` is installed and `DISPLAY` is not required (scripts set Agg backend for headless runs).
- Check `logs/` (created by scripts on failures) for per-experiment failure details.

Extending or debugging
- To compute patron/stat metrics for an existing `results/OrderData/` and `results/OrderMetrics/` pair, call `scripts/run_experiment.py` with the matching filename arguments, or import the helper functions from `scripts/` in a Python REPL.

Contact / Author
- Author: M. M. Kuttel (see header in `SchedulingSimulation.java`).
- Additional author: Tracey Letlape.

License
- No license file included — treat this as course assignment code. Contact the author for reuse permissions.
