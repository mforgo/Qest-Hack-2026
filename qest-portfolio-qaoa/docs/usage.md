# Usage — Install, Run, Visualize

Everything you need to go from a fresh clone to plots. Commands assume you are in the repository root (`qest-portfolio-qaoa/`).

---

## 1. Prerequisites

- Python **3.10+** (3.11/3.12 recommended)
- ~1 GB free disk space for the virtual environment and dependencies
- The default workflow needs **no IBM account and no quantum hardware** — everything runs on the local **Aer** simulator. An optional real-hardware demo is described in [`hardware.md`](hardware.md).

## 2. Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` installs: Qiskit, Qiskit Aer, Qiskit Optimization, Qiskit Algorithms, NumPy, SciPy, pandas, Matplotlib, Seaborn, NetworkX, pylatexenc, yfinance, PyYAML, Jupyter.

> **Why `pylatexenc`?** Qiskit's Matplotlib circuit drawer uses it to render gate labels. Without it, plot 17 fails.

## 3. Data

The code expects exactly these two files:

```
data/raw/qest_stock_data.csv
data/raw/qest_correlation_2021_2024.csv
```

### `qest_stock_data.csv`

One row per stock (10 rows), columns:

| Column | Meaning |
|---|---|
| `sector` | Financials / Consumer / Energy & utilities / Transport |
| `company` | Human-readable name |
| `ticker` | Symbol, e.g. `LHV1T.TL` |
| `return_2021_2024_pct_per_yr` | Annualized return used for optimization |
| `volatility_2021_2024_pct` | Annualized volatility used for optimization |
| `return_2025_pct` | Held-back 2025 return (not used by the optimizer) |
| `volatility_2025_pct` | Held-back 2025 volatility (not used by the optimizer) |

The ten stocks:

| Sector | Tickers |
|---|---|
| Financials | `LHV1T.TL`, `CPA1T.TL`, `ROE1L.VS` |
| Consumer | `TKM1T.TL`, `APG1L.VS`, `PZV1L.VS` |
| Energy & utilities | `IGN1L.VS`, `TVE1T.TL` |
| Transport | `TAL1T.TL`, `TSM1T.TL` |

### `qest_correlation_2021_2024.csv`

A 10×10 correlation matrix with a `ticker` index column. The loader reorders it to match the stock CSV and builds the covariance matrix as `corr × outer(vol, vol)`.

## 4. Run the optimization experiment

```bash
# Quick run: Neutral philosophy, depths 1-5, seed 42 -> 5 rows
python -m src.pipeline.runner --quick

# Full sweep: 3 philosophies x 5 depths x 3 seeds -> 45 rows
python -m src.pipeline.runner --full
```

`--quick` is the default if you pass no flags. `--full` is the configuration that produced the 45-row reference CSV.

### What happens

1. Loads the data and prints the classical baselines (exact optimum and continuous relaxation).
2. For each selected philosophy and depth: builds the Dicke+XY QAOA circuit, runs COBYLA (up to 1000 iterations per seed), samples 1024 shots, picks the most frequent portfolio, and scores it.
3. Prints progress every 10 optimizer iterations and a result line per (depth, seed).
4. Writes a timestamped CSV to `results/logs/`.

### Grid overrides

You can run any subset without editing code:

```bash
# One philosophy, one depth, one seed
python -m src.pipeline.runner --philosophies Neutral --depths 3 --seeds 42

# Two philosophies, depths 1 and 2
python -m src.pipeline.runner --philosophies Gambling Safe --depths 1 2

# Change the optimizer budget and output directory
python -m src.pipeline.runner --quick --maxiter 300 --output-dir /tmp/qaoa_runs
```

| Flag | Default | Meaning |
|---|---|---|
| `--quick` | active | Neutral, depths 1–5, seed 42 (5 rows) |
| `--full` | | Gambling/Neutral/Safe, depths 1–5, seeds 42/123/999 (45 rows) |
| `--philosophies NAME...` | from mode | Any of `Gambling`, `Neutral`, `Safe` |
| `--depths N...` | `1 2 3 4 5` | QAOA depths |
| `--seeds N...` | `42` (`--full`: `42 123 999`) | Random seeds |
| `--ansatz NAME...` | `xy_mixer` | `xy_mixer`, `standard`, or `warm_start` |
| `--maxiter N` | `1000` | COBYLA iterations per seed |
| `--output-dir PATH` | `results/logs` | Where the CSV is written |

### What you will see (approximate)

```
Loading data...
==================================================
   Executing Philosophy: Neutral (Alpha = 2.0)
==================================================
Computing classical baselines for Neutral...
Exact Classical Energy: ...
Exact Classical Tickers: ['ROE1L.VS', 'TKM1T.TL', 'APG1L.VS', 'IGN1L.VS', 'TVE1T.TL']

--- Running: xy_mixer | p=1 | seed=42 ---
  -> Iteration 010: Energy = ...
  ...
Result: Valid=True | Sharpe=... | [...]
...
Search complete. Saved to results/logs/philosophy_search_results_<timestamp>.csv
```

### Runtime

- `--quick` (5 runs) takes roughly **2–3 minutes** on a laptop.
- `--full` (45 runs) takes roughly **30–45 minutes**. Higher depths dominate: the circuit has `2p` parameters, and COBYLA may use hundreds of evaluations per seed.
- The simulator stage is effectively single-threaded; the p=4 and p=5 runs account for most of the wall-clock time.

## 5. Generate visualizations

### Extended suite (plots 05–18)

```bash
python -m src.pipeline.visualizations --all
```

This produces **15 files** in `results/visualisations/` (plots 05–18 plus the correlation network) in roughly **15–20 seconds** on a laptop.

Useful variants:

```bash
# Only market-data plots (05–10)
python -m src.pipeline.visualizations --data

# Only experiment-result plots (11–16)
python -m src.pipeline.visualizations --results

# Only quantum-circuit plots (17–18)
python -m src.pipeline.visualizations --quantum

# Correlation network only
python -m src.pipeline.visualizations --network

# 3-D QAOA energy landscape (slower; ~40s at default grid)
python -m src.pipeline.visualizations --landscape

# Point at a specific results CSV
python -m src.pipeline.visualizations --results --file results/logs/philosophy_search_results_20261112_183740.csv

# Change the landscape grid resolution (default 20; higher = slower)
python -m src.pipeline.visualizations --landscape --grid-points 30

# Write plots somewhere else
python -m src.pipeline.visualizations --all --output-dir /tmp/plots
```

| Flag | Effect |
|---|---|
| `--all` | Everything except the 3-D landscape (15 plots) |
| `--data` | Plots 05–10 (market data) |
| `--results` | Plots 11–16 (experiment results) |
| `--quantum` | Plots 17–18 (circuit + sampled distribution) |
| `--network` | `market_correlation_network.png` |
| `--landscape` | `qaoa_3d_landscape.png` |
| `--file PATH` | Use a specific results CSV (default: richest CSV in `results/logs/`) |
| `--data-dir PATH` | Directory holding the two input CSVs |
| `--output-dir PATH` | Where PNGs are written |
| `--grid-points N` | Landscape resolution per axis (default 20; evaluates N² circuits) |
| `--maxiter N` | COBYLA iterations for the sampled-distribution plot (default 60) |

### Legacy suite (plots 01–04)

```bash
python -m src.pipeline.visualize_results
```

Add `--landscape` and/or `--network` to also render those two plots from the legacy CLI:

```bash
python -m src.pipeline.visualize_results --landscape --network
```

### Which CSV is used by default?

The extended package scans `results/logs/*.csv` and picks the one with the **most data rows** (richest sweep). With the committed files that is `philosophy_search_results_20261112_183740.csv` (45 rows). Use `--file` to override.

## 6. Outputs

```
results/
├── logs/
│   ├── philosophy_search_results_<timestamp>.csv   # written by runner.py
│   ├── hardware_run_<timestamp>.json / .csv        # written by hardware_runner.py (optional)
│   ├── grid_search_results_<timestamp>.csv         # older 9-column format
│   └── ...
└── visualisations/
    ├── 01_risk_vs_return.png
    ├── 02_qaoa_energy.png
    ├── 03_sharpe_ratio.png
    ├── 04_ticker_frequency.png
    ├── 05_correlation_heatmap.png
    ├── 06_covariance_heatmap.png
    ├── 07_asset_risk_return.png
    ├── 08_sector_exposure.png
    ├── 09_portfolio_frontier.png
    ├── 10_risk_return_contribution.png
    ├── 11_depth_vs_energy.png
    ├── 12_depth_vs_valid_rate.png
    ├── 13_depth_vs_sharpe.png
    ├── 14_ticker_selection_heatmap.png
    ├── 15_energy_vs_sharpe.png
    ├── 16_philosophy_comparison.png
    ├── 17_ansatz_circuit.png
    ├── 18_sampled_distribution.png
    ├── market_correlation_network.png
    └── qaoa_3d_landscape.png
```

`results/` and `data/raw/` are gitignored — regenerate them locally.

## 7. Changing settings

The simulator runner has sensible defaults but no YAML config; use the CLI flags in §4 for normal overrides. The defaults live near the top of `src/pipeline/runner.py`:

```python
ALL_PHILOSOPHIES = {"Gambling": 0.0, "Neutral": 2.0, "Safe": 5.0}
```

To change the **rules** (select count, max per sector), edit `src/data/constraints.py`:

```python
DEFAULT_CONSTRAINTS = PortfolioConstraints(num_to_select=5, max_per_sector=2)
```

To change **COBYLA iterations**, use `--maxiter N` (default 1000). The hardware runner is different: it **does** load `configs/ibm_provider.yaml`, and every key can be overridden on its CLI. See [`hardware.md`](hardware.md).

## 8. Reproducibility

- `np.random.seed(seed)` is set before drawing initial QAOA parameters, so the same seed + same code + same data gives the same starting point.
- COBYLA itself is deterministic given the same start.
- Simulator sampling is seeded by Qiskit Aer's defaults; small run-to-run variation in sampled counts is possible.
- Results files are timestamped, so runs never overwrite each other.

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `FileNotFoundError: data/raw/...` | Put both CSVs in `data/raw/` (they are gitignored) |
| `ModuleNotFoundError: src` | Run from the repo root, not from inside `src/` |
| Plot 17 fails with a LaTeX/`pylatexenc` error | `pip install pylatexenc` |
| Plots open a window / crash on a server | The package already forces `Agg`; ensure you use `python -m src.pipeline.visualizations` |
| Landscape is slow | Lower `--grid-points` (e.g. 12) or `--maxiter` |
| Only 5 result rows | You ran `--quick` (the default); use `--full` for 45 rows |
| Hardware job stays `QUEUED` | Normal IBM queue; the runner blocks until the result arrives. See [`hardware.md`](hardware.md) |
| `SparseEfficiencyWarning` | Already suppressed in `runner.py` |

More in [`faq.md`](faq.md).
