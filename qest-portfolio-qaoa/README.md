# Coop Pank QAOA Portfolio Optimization

**QEst Hack 2026 · Coop Bank challenge**

Pick **5 of 10** Nasdaq Baltic stocks to get the **highest return for the lowest risk**, with **at most 2 stocks from any one sector**. We solve it with **QAOA** (a quantum optimization algorithm) running on a simulator, and compare the result against the exact classical answer.

> **No quantum background? Start here:** [`docs/concepts.md`](docs/concepts.md) explains every idea in plain English, with analogies and a glossary. You do not need any physics or math to follow it.

---

## The problem in one sentence

From ten stocks spread across four sectors, choose five (equal weights, max two per sector) so the portfolio's **return is as high as possible** while its **risk is as low as possible**.

- 10 stocks, 4 sectors, choose 5, max 2 per sector
- 252 possible 5-stock portfolios; **210** obey the sector rule
- Selected using 2021–2024 data; 2025 is held back for validation
- Three "investor personalities" tune the return-vs-risk trade-off: **Gambling** (return only), **Neutral** (balanced), **Safe** (risk-averse)

### Extended datasets

The core challenge is the 10-stock `qest` universe, but the pipeline also loads two larger datasets for data analysis and visualization:

| `--dataset` | Assets |
|---|---:|
| `qest` (default) | 10 |
| `nasdaq_baltic` | 29 |
| `nyse` | 32 |

Pass `--dataset nasdaq_baltic` or `--dataset nyse` to the runner, the visualization CLI, or the hardware runner. The `qest` universe stays the default everywhere.

## Quick start

```bash
# 1. Install
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Put the data files in data/raw/. The default flow needs the qest pair;
#    the larger universes are optional:
#    qest_stock_data.csv + qest_correlation_2021_2024.csv            (10 assets, required)
#    nasdaq_baltic_stock_data.csv + nasdaq_baltic_correlation_2021_2024.csv  (29, optional)
#    nyse_stock_data.csv + nyse_correlation_2021_2024.csv            (32, optional)

# 3. Run the optimization experiment
python -m src.pipeline.runner --quick   # 5 runs, ~2 minutes
python -m src.pipeline.runner --full    # 45 runs, ~30 minutes

# 4. Generate all visualizations
python -m src.pipeline.visualizations --all

# Data/network plots for a large dataset (quantum plots are skipped above 12 assets)
python -m src.pipeline.visualizations --data --network --dataset nasdaq_baltic
python -m src.pipeline.visualizations --data --network --dataset nyse

# 5. (Optional) Run one circuit on real IBM hardware
python -m src.pipeline.hardware_runner --list-backends
python -m src.pipeline.hardware_runner --dry-run
python -m src.pipeline.hardware_runner --dataset qest --backend ibm_kingston --shots 2048
python -m src.pipeline.hardware_runner --dataset nasdaq_baltic --max-assets 12 --dry-run
```

Results land in `results/logs/` (CSV/JSON) and `results/visualisations/` (PNG). The hardware step is optional and needs an IBM Quantum account; see [`docs/hardware.md`](docs/hardware.md).

## What you get

| Output | What it is |
|---|---|
| `results/logs/philosophy_search_results_<timestamp>.csv` | One row per (philosophy, ansatz, depth, seed): energy, validity, return, volatility, Sharpe, chosen tickers |
| `results/logs/hardware_run_<timestamp>.json` / `.csv` | Optional real-hardware result: job id, backend, best bitstring, counts, validity, metrics |
| `results/visualisations/01–04_*.png` | Classic result plots (risk/return, energy, Sharpe, ticker frequency) |
| `results/visualisations/05–18_*.png` | Extended suite: data heatmaps, feasible-portfolio frontier, depth curves, circuit diagram, sampled distribution |
| `results/visualisations/qaoa_3d_landscape.png` | 3-D energy landscape over the two QAOA parameters (opt-in) |
| `results/visualisations/market_correlation_network.png` | Correlation graph, colored by sector |

## Documentation

| Document | Read it if you want to… |
|---|---|
| [`docs/README.md`](docs/README.md) | See the full documentation map and reading paths |
| [`docs/concepts.md`](docs/concepts.md) | Understand the problem and QAOA **without any quantum background** |
| [`docs/glossary.md`](docs/glossary.md) | Look up a term in one sentence |
| [`docs/architecture.md`](docs/architecture.md) | See how the code is organized and how data flows |
| [`docs/usage.md`](docs/usage.md) | Install, run experiments, generate plots, change settings |
| [`docs/results_and_visualizations.md`](docs/results_and_visualizations.md) | Read the CSV columns and interpret every plot |
| [`docs/hardware.md`](docs/hardware.md) | Run the optional demo on real IBM Quantum hardware |
| [`docs/faq.md`](docs/faq.md) | Get answers about limitations, empty placeholder files, and troubleshooting |

## Honest status

This is a **hackathon prototype**, not production software:

- The default "quantum" runs use **Aer**, a local quantum-circuit **simulator**; no real quantum hardware is required.
- An **optional hardware path** (`src/pipeline/hardware_runner.py`) optimizes angles on Aer and then samples one small circuit on a real IBM backend. It loads `configs/ibm_provider.yaml`. It is a demo, not a benchmark; see [`docs/hardware.md`](docs/hardware.md).
- The default problem is tiny (10 assets), so a laptop solves it **exactly** classically. The exact classical answer is used as the benchmark.
- The **full 29/32-asset QPU circuits are too deep** for a useful result on current IBM hardware. They are a demonstration of scale only, and the runner blocks them unless you pass `--allow-deep-circuit`. Use `--max-assets 12` for a practical QPU subset. See [`docs/hardware.md`](docs/hardware.md).
- The **large datasets are for data analysis and visualization**, or for smaller QPU subsets (`--max-assets N`). The simulator grid search stops above 24 assets, and quantum/landscape plots are skipped above 12 assets.
- `--quick` runs the **Neutral** philosophy only (5 rows); `--full` runs all three philosophies × 5 depths × 3 seeds (45 rows).
- Some files are **empty placeholders** (`configs/grid_search.yaml`, the notebook, `scripts/run_experiment.py`). `configs/ibm_provider.yaml` is now used by the hardware runner. See [`docs/faq.md`](docs/faq.md).
