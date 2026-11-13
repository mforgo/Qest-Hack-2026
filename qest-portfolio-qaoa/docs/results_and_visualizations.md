# Results & Visualizations

How to read the experiment output: the CSV columns, the metrics, and every plot. For the underlying ideas, see [`concepts.md`](concepts.md).

---

## 1. Result CSV files

`runner.py` writes a **timestamped** file to `results/logs/`. Two schemas exist in the repo:

### A. `philosophy_search_results_<timestamp>.csv` — 11 columns (current runner)

| Column | Type | Meaning |
|---|---|---|
| `philosophy` | text | `Gambling`, `Neutral`, or `Safe` |
| `alpha` | float | Risk factor for that philosophy (0.0 / 2.0 / 5.0) |
| `ansatz` | text | Circuit type; currently always `xy_mixer` |
| `depth` | int | QAOA depth `p` (1–5) |
| `seed` | int | Random seed for initial parameters |
| `final_energy` | float | Optimized expectation value of the Ising Hamiltonian |
| `is_valid` | bool | Exactly 5 stocks **and** no sector over 2 |
| `return_pct` | float | Annualized expected return of the sampled portfolio (%) |
| `volatility_pct` | float | Annualized volatility of the sampled portfolio (%) |
| `sharpe` | float | `return_pct / volatility_pct` (risk-free rate assumed 0) |
| `tickers` | string | Python-list literal of the selected tickers, e.g. `"['LHV1T.TL', ...]"` |

### B. `grid_search_results_<timestamp>.csv` — 9 columns (older format)

Same as above minus `philosophy` and `alpha`. The extended plotting package handles both, but philosophy-comparison plots require the 11-column format.

### What is actually in the repo

| File | Rows | Notes |
|---|---|---|
| `philosophy_search_results_20261112_183740.csv` | 45 | 3 philosophies × 5 depths × 3 seeds (42, 123, 999); all rows valid. **Richest file — used by default.** |
| `philosophy_search_results_20261112_184746.csv` | 5 | Neutral, depths 1–5, seed 42 |
| `philosophy_search_results_20261112_185138.csv` | 5 | Neutral, depths 1–5, seed 42 |
| `grid_search_results_*.csv` | 4–5 each | Older 9-column runs |

> The current `runner.py` is limited to **Neutral** and **one seed**, so a fresh run writes 5 rows. The 45-row file came from a fuller sweep. See [`architecture.md`](architecture.md).

---

## 2. How to read the metrics

### `is_valid`

A hard yes/no:

- **True** — exactly five stocks, and no sector contributes more than two.
- **False** — the sampled portfolio broke a rule. Because the Dicke + XY circuit *guarantees* exactly five, a `False` here almost always means **three stocks from Financials or Consumer** (the sector penalty was not strong enough to suppress it).

### `return_pct` and `volatility_pct`

Both are **annualized percentages**. For an equal-weight portfolio of the selected stocks:

```
return     = average of the selected stocks' annualized returns
volatility = sqrt(wᵀ Σ w) × 100,  with w = 1/5 for each selected stock
```

Higher return is better; lower volatility is better.

### `sharpe`

```
sharpe = return_pct / volatility_pct
```

This is **return per unit of risk** with a risk-free rate of zero. Higher is better. It is *not* the textbook Sharpe ratio (which subtracts a risk-free rate); treat it as a relative comparison between runs.

### `final_energy`

The value COBYLA minimized: the expectation value of the Ising Hamiltonian under the optimized QAOA state. **Lower is better — but only within the same alpha.**

> **Critical caveat:** `alpha` multiplies the risk term, so each philosophy defines a *different* Hamiltonian. Energies from Gambling, Neutral, and Safe are on **different scales** and must not be compared directly. Compare depths/seeds *within* one philosophy.

### `tickers`

Stored as a Python list literal so it survives a CSV round-trip. Parse with `ast.literal_eval`.

---

## 3. Caveats to keep in mind

1. **The reported portfolio is the most frequent sampled bitstring**, not necessarily the lowest-energy one. Sampling noise can make a slightly worse portfolio appear more often.
2. **The offset is a placeholder.** `runner.py` sets `offset = 0.0`, so `final_energy` is the raw expectation value. A generic QP→Ising conversion would add a constant offset; the manual Hamiltonian path does not, so absolute energies are only meaningful relatively.
3. **All 45 rows in the richest file are valid**, so plots of validity will look flat at 1.0. That is a *good* result (the constrained circuit worked), not a bug.
4. **Plot 02 (legacy) has a hardcoded classical reference line** at `-0.16788`. It was computed for one specific configuration and may not match the current alpha/data. Treat it as illustrative.
5. **Plot 18 re-optimizes independently** (default 60 COBYLA iterations, 4096 shots) rather than reading the results CSV, so its energy may differ slightly from the CSV.
6. **2025 data is not used** by any optimizer or plot; it is held back for validation only.

---

## 4. Plot catalog

All plots are written to `results/visualisations/` at 300 dpi (plot 17 at 200 dpi).

### Legacy plots — `python -m src.pipeline.visualize_results` (01–04)

These read a results CSV (by default the **most recently created** file in `results/logs/`).

| # | File | What it shows | How to read it |
|---|---|---|---|
| 01 | `01_risk_vs_return.png` | Scatter of volatility (x) vs return (y), one point per run, colored by philosophy/depth/seed | Up-and-left is better (high return, low risk). Points on the dashed zero-return line earn nothing. |
| 02 | `02_qaoa_energy.png` | Bar chart of `final_energy` per run, with a green dashed classical reference at −0.16788 | Lower bars are better. Ignore the reference line unless your alpha matches the one it was computed for. |
| 03 | `03_sharpe_ratio.png` | Bar chart of Sharpe ratio per run | Taller is better. |
| 04 | `04_ticker_frequency.png` | How often each ticker appears across all runs | Stocks that appear often are robust choices; a stock never selected is consistently unattractive. |

### Data plots — `--data` (05–10)

These describe the **market data and the feasible universe**, independent of any QAOA run.

| # | File | What it shows | How to read it |
|---|---|---|---|
| 05 | `05_correlation_heatmap.png` | 10×10 correlation matrix, annotated | Red = move together, blue = move oppositely, near 0 = independent. Strong red pairs add little diversification. |
| 06 | `06_covariance_heatmap.png` | 10×10 annualized covariance matrix | The diagonal is each stock's variance (risk²). Off-diagonal cells drive portfolio risk. |
| 07 | `07_asset_risk_return.png` | Each stock as a risk-vs-return dot, colored by sector, labeled with its ticker; black star = equal-weight all-10 portfolio | Compare individual stocks to the all-10 average. Up-and-left is attractive. |
| 08 | `08_sector_exposure.png` | Bar chart of sector sizes, with a dashed line at the max-per-sector limit (2); red bars are "binding" | Red sectors have more members than the cap, so at least one must be dropped. Here: Financials and Consumer. |
| 09 | `09_portfolio_frontier.png` | All **210 valid** equal-weight portfolios as dots (x = risk, y = return, color = Sharpe), plus highlights | Gold star = max Sharpe; blue diamond = min risk; green square = max return; red plus = exact classical QP optimum (alpha = 2); black × = QAOA runs (when a results CSV is supplied). The "frontier" is the upper-left edge of the cloud. |
| 10 | `10_risk_return_contribution.png` | Two panels for the max-Sharpe portfolio: each stock's contribution to return and to risk | Shows which holdings drive the portfolio's upside vs its bumpiness. A stock can contribute a lot of risk for little return. |

### Results plots — `--results` (11–16)

These read the results CSV (default: the **richest** file, i.e. most rows). They require the corresponding columns; unsupported plots are skipped silently.

| # | File | What it shows | How to read it |
|---|---|---|---|
| 11 | `11_depth_vs_energy.png` | Final energy vs depth `p`, one line per philosophy (or ansatz), shaded ± standard deviation across seeds | Lower is better. Flat lines mean extra depth did not help; rising lines suggest optimization difficulty or noise. |
| 12 | `12_depth_vs_valid_rate.png` | Fraction of valid portfolios vs depth, per philosophy | 1.0 = every sampled portfolio obeyed the rules. Dips reveal constraint violations. |
| 13 | `13_depth_vs_sharpe.png` | Sharpe ratio vs depth, per philosophy | Higher is better. Look for the depth where gains flatten. |
| 14 | `14_ticker_selection_heatmap.png` | Heatmap: ticker (rows) × depth (columns), cell = times selected | Bright rows are consistently chosen; patterns across columns show whether depth changes the choice. |
| 15 | `15_energy_vs_sharpe.png` | Scatter of final energy (x) vs Sharpe (y), colored by validity, shaped by philosophy | Ideal runs sit **top-left** (low energy, high Sharpe). Red points are invalid. |
| 16 | `16_philosophy_comparison.png` | Three bar panels: mean return, mean Sharpe, mean final energy per philosophy, with standard-deviation whiskers | Shows how the risk dial changes outcomes. Remember: energy is only comparable within a philosophy. |

### Quantum plots — `--quantum` (17–18)

| # | File | What it shows | How to read it |
|---|---|---|---|
| 17 | `17_ansatz_circuit.png` | The p=1 QAOA circuit diagram (Dicke init → cost layer γ → XY mixer β), decomposed one level | The left block prepares the five-stock superposition; the middle block encodes the problem; the right block shuffles candidates. This is a *schematic* of one layer. |
| 18 | `18_sampled_distribution.png` | The 15 most frequent measured bitstrings after a short p=1 optimization (4096 shots) | Bar height = sampling probability; **green = valid**, **red = violates a rule**. A good run concentrates probability on green bars near the left. |

### Extra plots (opt-in)

| File | Generated by | What it shows | How to read it |
|---|---|---|---|
| `market_correlation_network.png` | `--network` | Graph of stocks; an edge exists when \|correlation\| > 0.3, and thicker edges mean stronger correlation; node color = sector | Clusters = stocks that move together. Dense clusters offer less diversification. |
| `qaoa_3d_landscape.png` | `--landscape` | 3-D surface of the p=1 QAOA energy over β and γ, each swept from −π to π at `grid_points` resolution (default 20 → 400 circuit evaluations) | Valleys are good parameter regions. The optimizer is searching for the lowest point. Uses alpha = 2.0. |

---

## 5. Quick interpretation checklist

When you open a fresh set of results:

1. **Validity first.** Are all rows `is_valid = True`? If not, the sector penalty or circuit is misconfigured.
2. **Compare like with like.** Only compare energies within one `alpha`.
3. **Check the Sharpe trend** (plot 13): did more depth actually help, or did it plateau?
4. **Locate the QAOA runs on the frontier** (plot 09): are they near the classical optimum (red plus), or far from it?
5. **Look at the sampled distribution** (plot 18): is probability concentrated on valid, high-quality bitstrings, or spread thinly?
6. **Sanity-check the winner's tickers** against the data plots (05, 07): do they make financial sense?
