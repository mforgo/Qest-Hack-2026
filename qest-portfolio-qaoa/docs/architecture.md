# Architecture & Data Flow

This document is for readers who want to understand **how the code is organized**. For the ideas behind it, read [`concepts.md`](concepts.md) first.

---

## Repository tree

```
qest-portfolio-qaoa/
├── README.md                     # one-page overview (start here)
├── Baltic Stock Selection.md     # original challenge statement
├── requirements.txt              # Python dependencies
├── data/raw/                     # gitignored; you supply the CSVs
│   ├── qest_stock_data.csv                     # 10 assets (default)
│   ├── qest_correlation_2021_2024.csv          # 10×10 correlation matrix
│   ├── nasdaq_baltic_stock_data.csv            # 29 assets (experimental)
│   ├── nasdaq_baltic_correlation_2021_2024.csv # 29×29 correlation matrix
│   ├── nyse_stock_data.csv                     # 32 assets (experimental)
│   └── nyse_correlation_2021_2024.csv          # 32×32 correlation matrix
├── results/
│   ├── logs/                     # experiment CSV outputs
│   └── visualisations/           # generated PNG plots
├── src/
│   ├── data/
│   │   ├── loader.py             # PortfolioData: CSV → returns, covariance, sectors
│   │   └── constraints.py        # PortfolioConstraints: the rules, in one place
│   ├── problem/
│   │   ├── qubo_builder.py       # QUBO / Ising Hamiltonians
│   │   └── classical_solver.py   # exact + relaxed classical baselines
│   ├── quantum/
│   │   ├── ansatzes.py           # Dicke state, XY mixer, QAOA circuit builders
│   │   ├── execution.py          # objective function + COBYLA optimizer
│   │   └── optimizers.py         # EMPTY placeholder (unused)
│   └── pipeline/
│       ├── runner.py             # MAIN ENTRY POINT: grid search
│       ├── evaluator.py          # score a bitstring → portfolio metrics
│       ├── hardware_runner.py    # optional IBM hardware path (loads configs/ibm_provider.yaml)
│       ├── visualize_results.py  # legacy plotting CLI (plots 01–04 + landscape + network)
│       └── visualizations/       # extended plotting package (plots 05–18)
│           ├── __init__.py       # forces Matplotlib "Agg" backend
│           ├── __main__.py       # CLI: python -m src.pipeline.visualizations
│           ├── _common.py        # shared loading, styling, helpers
│           ├── data_plots.py     # plots 05–10 (market data)
│           ├── results_plots.py  # plots 11–16 (experiment results)
│           └── quantum_plots.py  # plots 17–18 (circuit + sampled distribution)
├── configs/
│   ├── grid_search.yaml          # EMPTY placeholder (not loaded by code)
│   └── ibm_provider.yaml         # hardware-runner settings (loaded by hardware_runner.py)
├── notebooks/                    # EMPTY placeholder (not used)
│   └── 01_data_exploration.ipynb
└── scripts/
    └── run_experiment.py         # EMPTY placeholder (unused)
```

> **Note:** `configs/grid_search.yaml`, `notebooks/`, `scripts/run_experiment.py`, and `src/quantum/optimizers.py` are **0-byte placeholders**. The simulator's configuration is hardcoded in `src/pipeline/runner.py` (CLI flags for overrides); `configs/ibm_provider.yaml` **is** loaded, but only by the hardware runner. See [`faq.md`](faq.md).

---

## Module responsibilities

### `src/data/loader.py` — load and normalize the market data

`PortfolioData(stock_csv, corr_csv)` reads both CSVs and exposes:

| Attribute | Meaning |
|---|---|
| `tickers` | Ticker symbols, in row order (10 for `qest`, 29 for `nasdaq_baltic`, 32 for `nyse`) |
| `n_assets` | Number of assets in the loaded dataset |
| `returns` | Annualized return per stock, as decimals (e.g. 0.134) |
| `volatilities` | Annualized volatility per stock, as decimals |
| `covariance` | `n_assets × n_assets` covariance matrix, built as `corr × outer(vol, vol)` |
| `sector_indices` | `{sector_name: [row indices]}` |

`get_formulation_data()` returns `(returns, covariance, sector_indices, tickers)`. `subset(indices)` returns a new `PortfolioData` containing only those assets, with every array and sector mapping sliced consistently; the hardware runner uses it for `--max-assets`.

The 2025 columns (`return_2025_pct`, `volatility_2025_pct`) are **read into the CSV but not used** by the optimizer. They are held back for validation.

### `src/data/constraints.py` — the rules, in one place

A frozen dataclass so the rules cannot drift between modules:

```python
DEFAULT_CONSTRAINTS = PortfolioConstraints(num_to_select=5, max_per_sector=2)
```

| Method | Purpose |
|---|---|
| `is_valid(selected_indices, sector_indices)` | Returns `(bool, issues)` — exactly 5 **and** no sector over 2 |
| `binding_sectors(sector_indices)` | Sectors that *can* violate (those with more than `max_per_sector` members) |
| `violation_combinations(sector_indices)` | All stock-index groups that would violate the sector rule (used to build the penalty) |

`is_valid` is the single source of truth used by `evaluator.py`; `binding_sectors` and `violation_combinations` are used by `qubo_builder.py`.

### `src/problem/qubo_builder.py` — three ways to write the problem

| Function | Used by runner? | Purpose |
|---|---|---|
| `build_manual_hamiltonian(...)` | **Yes** | Builds the Ising Hamiltonian directly from returns/covariance/sector penalty. Returns a `SparsePauliOp`. |
| `build_portfolio_optimization_problem(...)` | **Yes** | Builds a Qiskit `QuadraticProgram` with explicit `select_k` and per-sector constraints. Used for the classical baselines. |
| `get_qubo_and_ising(qp, penalty_weight)` | No | Generic QP→QUBO→Ising converter. Kept for reference/experiments. |

**Important design note:** `build_manual_hamiltonian` includes the **sector penalty** but **not** an "exactly five" penalty. The "exactly five" rule is enforced by the **Dicke initial state + XY mixer** in the ansatz (see [`concepts.md`](concepts.md), Part 4). If you switch to a standard ansatz, add a cardinality penalty or the circuit can return invalid portfolio sizes.

### `src/problem/classical_solver.py` — the benchmark

| Function | What it returns |
|---|---|
| `solve_exact_classical(qp)` | The true optimum of the QP via `NumPyMinimumEigensolver` (`result.x`, `result.fval`) |
| `solve_continuous_relaxation(qp)` | Fractional solution in `[0,1]` via SLSQP — used as a warm-start reference |

### `src/quantum/ansatzes.py` — circuit construction

| Function | What it builds |
|---|---|
| `build_dicke_state(n, k)` | Equal superposition of all bitstrings with exactly `k` ones |
| `build_simple_valid_state(n, k)` | Shallow alternative: sets the first `k` qubits to 1 |
| `build_xy_mixer(n, topology)` | `0.5·Σ(XᵢXⱼ + YᵢYⱼ)` over qubit pairs; `"complete"` or `"ring"` |
| `build_xy_qaoa(ising_op, p_depth, use_dicke)` | **Used by the runner.** Dicke (or simple) init + XY mixer + cost operator, repeated `p` times |
| `build_standard_qaoa(ising_op, p_depth)` | Textbook QAOA from a uniform superposition |
| `build_warm_started_qaoa(ising_op, relaxed_probs, p_depth)` | Initial `Ry` rotations from the classical relaxation |

All of these return a Qiskit `QuantumCircuit` (via `QAOAAnsatz`).

### `src/quantum/execution.py` — run the hybrid loop

| Function | Purpose |
|---|---|
| `create_objective_function(ansatz, ising_op, estimator=None, backend=None)` | Transpiles the ansatz once, returns `objective(params) -> energy` using `AerEstimator` |
| `optimize_circuit(objective, initial_params, method='COBYLA', maxiter=1000)` | Runs SciPy's COBYLA; returns `(optimal_params, final_energy)` |

Reusing a single `AerSimulator`/`AerEstimator` across the whole grid is a deliberate performance choice: it avoids re-instantiating the simulator and re-transpiling for every depth/seed.

### `src/pipeline/evaluator.py` — score a measured bitstring

`evaluate_portfolio(bitstring, returns, covariance, tickers, sector_indices)`:

1. Takes the first `n_assets` bits (one per stock).
2. Selects the corresponding tickers.
3. Checks validity via `DEFAULT_CONSTRAINTS.is_valid`.
4. Computes equal-weight return, volatility, and Sharpe ratio.
5. Returns a dict: `valid`, `selected_tickers`, `return_pct`, `volatility_pct`, `sharpe_ratio`, `issues`.

### `src/pipeline/runner.py` — the main experiment

`run_grid_search()` does, in order:

1. Resolve `--dataset` (default `qest`) to `<dataset>_stock_data.csv` / `<dataset>_correlation_2021_2024.csv` and load `PortfolioData` from `data/raw/`.
2. Define philosophies (`Gambling=0.0`, `Neutral=2.0`, `Safe=5.0`), depths `1..5`, seeds `[42]`, ansatz `["xy_mixer"]`.
3. Create one `AerSimulator`, `AerSampler`, `AerEstimator` for the whole run.
4. Loop over philosophies (currently restricted to Neutral — see below).
5. For each: build the QP and the manual Hamiltonian; compute exact + relaxed classical baselines.
6. Loop over ansatz/depth: build the ansatz, create the objective, transpile the measured circuit once.
7. For each seed: random-init parameters, run COBYLA, bind the optimal parameters, sample 1024 shots, take the most frequent bitstring, evaluate it, append a row.
8. Write `results/logs/philosophy_search_results_<timestamp>.csv`.

**Current limitation:** line 48 is

```python
for phil_name, alpha in (("Neutral", 2.0),):  # For testing, only run Neutral philosophy
```

so a fresh run produces **5 rows** (depths 1–5, seed 42). To reproduce the 45-row sweep (3 philosophies × 5 depths × 3 seeds), restore the commented loop over `philosophies.items()` and use seeds `[42, 123, 999]`.

### `src/pipeline/visualize_results.py` — legacy plotting CLI

Generates plots **01–04** from a results CSV, plus two optional plots:

- `--landscape` → `qaoa_3d_landscape.png`
- `--network` → `market_correlation_network.png`

### `src/pipeline/visualizations/` — extended plotting package

Generates plots **05–18**. Entry point: `python -m src.pipeline.visualizations`. The package forces the non-interactive `Agg` backend at import time to avoid GUI/shutdown crashes on headless machines.

---

## End-to-end data flow

```
--dataset {qest,nasdaq_baltic,nyse}   (default: qest)
                │  resolves to
                ▼
data/raw/<dataset>_stock_data.csv ──┐
data/raw/<dataset>_correlation_*.csv ┘
                │
                ▼
        PortfolioData (loader.py)
        returns, covariance, sector_indices, tickers
                │
      ┌─────────┴──────────────────────────┐
      ▼                                    ▼
build_portfolio_optimization_problem   build_manual_hamiltonian
(QuadraticProgram, explicit rules)     (SparsePauliOp, sector penalty)
      │                                    │
      ▼                                    ▼
solve_exact_classical              build_xy_qaoa (Dicke + XY mixer)
solve_continuous_relaxation                 │
      │                                     ▼
      │                          create_objective_function (AerEstimator)
      │                                     │
      │                          optimize_circuit (COBYLA)
      │                                     │
      │                          sample 1024 shots (AerSampler)
      │                                     ▼
      │                          most frequent bitstring
      │                                     │
      └──────────────┬──────────────────────┘
                     ▼
          evaluate_portfolio (evaluator.py)
          valid, return, volatility, Sharpe, tickers
                     │
                     ▼
     results/logs/philosophy_search_results_<ts>.csv
                     │
                     ▼
     visualizations (legacy CLI + extended package)
                     │
                     ▼
          results/visualisations/*.png
```

---

## Hardcoded parameters (single source of truth)

| Parameter | Value | Where |
|---|---|---|
| Stocks | 10 for the default `qest` dataset (`--dataset` selects 29 for `nasdaq_baltic`, 32 for `nyse`) | data CSV |
| Select count | 5 | `constraints.py` |
| Max per sector | 2 | `constraints.py` |
| Philosophies | Gambling 0.0, Neutral 2.0, Safe 5.0 | `runner.py` |
| Active philosophy | **Neutral only** | `runner.py` line 48 |
| Depths | 1, 2, 3, 4, 5 | `runner.py` |
| Seeds | `[42]` (current); 42/123/999 in the 45-row file | `runner.py` |
| Ansatz | `xy_mixer` (Dicke init, complete topology) | `runner.py` |
| Penalty weight | 10.0 | `runner.py` |
| Offset | 0.0 (placeholder; not added meaningfully) | `runner.py` |
| COBYLA max iterations | 1000 | `execution.py` |
| Shots per evaluation | 1024 (primitive default) | `runner.py` (sampler) |
| Data window | 2021–2024 (2025 held back) | `loader.py` |

Changing any of these means editing `runner.py` (or the relevant module). The simulator does **not** read YAML; the hardware runner reads `configs/ibm_provider.yaml`.

---

## Where to look next

- **Run it:** [`usage.md`](usage.md)
- **Read the output:** [`results_and_visualizations.md`](results_and_visualizations.md)
- **Why is X empty / why only Neutral?** [`faq.md`](faq.md)
