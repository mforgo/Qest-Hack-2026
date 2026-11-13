# FAQ, Limitations & Troubleshooting

Short answers to the questions this project raises most often. For definitions, see [`glossary.md`](glossary.md).

---

## About the approach

### Is this running on a real quantum computer?

No. Everything runs on **Aer**, Qiskit's local simulator, on a normal CPU. No IBM account or quantum hardware is needed. The circuit is a genuine QAOA circuit; only the execution is simulated.

### Why use QAOA for a problem a laptop can solve instantly?

The point is the **pipeline**, not this instance. With 10 stocks there are only 210 valid portfolios, so the exact classical solver is the right tool and serves as ground truth. The same pipeline (QUBO → constrained QAOA → sampling → evaluation) is what you would scale to a larger universe, where brute force stops being feasible.

### What is genuinely interesting here?

The **constrained circuit**: a Dicke initial state plus an XY mixer enforces "exactly five stocks" *inside* the quantum circuit, instead of relying on a soft penalty. That is a real technique, and it is why every run in the 45-row result file is valid.

### Why is the reported portfolio the "most frequent" bitstring rather than the lowest-energy one?

That is the standard QAOA readout: measure many times and take the mode. It is simple and robust to a single noisy shot, but it is not guaranteed to return the single best sample. A production version could score the top-k samples and pick the best valid one.

---

## About the code and repository state

### Why does a fresh run only produce 5 rows?

`src/pipeline/runner.py` line 48 is intentionally restricted for fast testing:

```python
for phil_name, alpha in (("Neutral", 2.0),):  # For testing, only run Neutral philosophy
```

Restore the commented `for phil_name, alpha in philosophies.items():` line (and set `seeds = [42, 123, 999]`) to reproduce the 45-row sweep.

### Why are `configs/*.yaml`, `notebooks/*.ipynb`, `scripts/run_experiment.py`, and `src/quantum/optimizers.py` empty?

They are **placeholders** (0 bytes). No code reads them. All configuration lives in `runner.py` and `constraints.py`. They exist to signal intended structure, not implemented features. See [`architecture.md`](architecture.md).

### Why is there no "select exactly 5" penalty in the Hamiltonian?

Because the ansatz enforces it structurally. `build_xy_qaoa(..., use_dicke=True)` starts in a Dicke state (only five-1 patterns) and applies an XY mixer that conserves the number of 1s. Adding a cardinality penalty would be redundant — **and it would be required if you switch to `build_standard_qaoa`**, which does not conserve Hamming weight.

### Why does the sector penalty only matter for Financials and Consumer?

Only sectors with **more than two** members can violate "at most two". Financials has 3 and Consumer has 3; Energy & utilities and Transport have 2 each and can never exceed the cap. `PortfolioConstraints.binding_sectors()` encodes exactly this.

### Why are there two ways to build the problem (manual Hamiltonian and QuadraticProgram)?

- `build_portfolio_optimization_problem` builds a Qiskit `QuadraticProgram` with **explicit** constraints. It is used for the classical baselines (`solve_exact_classical`, `solve_continuous_relaxation`).
- `build_manual_hamiltonian` builds the **Ising operator** directly, with the sector rule folded in as a penalty. It is what the QAOA circuit minimizes.

They encode the same objective. The QP is convenient for classical solvers; the manual Hamiltonian is what the quantum circuit needs. `get_qubo_and_ising()` is a third, generic converter that is currently unused.

### Why is `offset = 0.0`?

The manual Hamiltonian path does not produce a separate constant offset, so the runner records the raw expectation value. A generic `QuadraticProgramToQubo` conversion would return an offset; that path is not used. This is why absolute energies should only be compared **within the same alpha**.

### Why are 2025 columns present but unused?

They are the **held-back validation period**. The optimizer uses 2021–2024 only, so 2025 can be used later to check whether the chosen portfolio generalizes. No current plot uses them.

### Are there tests?

No automated test suite. The pipeline was validated manually (compile, imports, numeric equivalence of the manual Hamiltonian vs the QP, validity parity checks, and an end-to-end smoke run). See [`architecture.md`](architecture.md).

---

## About the results

### Why is every row valid in the 45-row file? Is that suspicious?

No — it is the intended outcome of the constrained circuit. Dicke + XY guarantees exactly five stocks; the sector penalty suppressed the remaining violations. Plot 12 will therefore be flat at 1.0 for that file. If you see invalid rows, the likely cause is a different ansatz or a weaker penalty.

### Why can't I compare `final_energy` across Gambling / Neutral / Safe?

Because `alpha` scales the risk term, so each philosophy defines a different Hamiltonian with a different energy scale. Compare depths or seeds **within** one philosophy, or compare the financial metrics (return, volatility, Sharpe), which are on a common scale.

### Why is `final_energy` sometimes negative and sometimes positive?

The Ising conversion distributes constant terms across Pauli strings, and the objective mixes a negative return term with a positive risk term. The absolute value has no financial meaning; only relative comparisons within the same Hamiltonian do.

### Why does the Sharpe ratio differ from the textbook definition?

The code computes `return / volatility` with **no risk-free rate**. It is a relative "return per unit of risk" score, suitable for ranking runs, not for reporting to an investor.

### Why do different seeds give different portfolios?

QAOA starts from random parameter values (`np.random.seed(seed)`), and COBYLA is a local optimizer. Different starts can land in different local minima. The 45-row file uses seeds 42, 123, and 999 to expose this spread.

### Why does the QAOA result sometimes beat the classical optimum on Sharpe?

The classical QP optimum minimizes the **Hamiltonian energy**, which balances return and risk according to alpha. A sampled portfolio can have a slightly better return/volatility ratio while having a worse energy. They are different criteria; do not treat one as strictly dominating the other.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `FileNotFoundError: data/raw/qest_stock_data.csv` | Data files are gitignored and absent | Add both CSVs under `data/raw/` |
| `ModuleNotFoundError: No module named 'src'` | Running from the wrong directory | Run from the repository root (`qest-portfolio-qaoa/`) |
| `ModuleNotFoundError: qiskit_aer` | Dependencies not installed | `pip install -r requirements.txt` |
| Plot 17 fails with a LaTeX/`pylatexenc` error | Missing circuit-drawing dependency | `pip install pylatexenc` |
| Plots try to open a window or crash on a server | GUI backend | Use the package CLI (`python -m src.pipeline.visualizations`), which forces `Agg` |
| `ValueError: grid_points must be >= 2` | Landscape resolution too low | Use `--grid-points 2` or higher |
| Landscape takes minutes | It evaluates `grid_points²` circuits | Lower `--grid-points` (e.g. 12) |
| `--results` produces no plots | CSV lacks required columns | Use an 11-column `philosophy_search_results_*.csv`, or `--file` to point at one |
| `16_philosophy_comparison.png` is missing | The chosen CSV has no `philosophy` column | Use a philosophy CSV, not a 9-column grid CSV |
| `SparseEfficiencyWarning` printed | SciPy sparse conversion in Qiskit | Already suppressed in `runner.py`; harmless |
| Results look different from the committed CSVs | Different seed/alpha/depth configuration or simulator sampling noise | Match the constants in `runner.py`, or use the committed CSV with `--file` |

---

## Known limitations & future work

- **Simulator only.** No real-hardware execution path is wired up, despite the `qiskit-ibm-runtime` dependency and the empty `ibm_provider.yaml`.
- **Configs are not loaded.** YAML files are placeholders; parameters are hardcoded.
- **Runner is restricted to Neutral / one seed** for speed.
- **No automated tests.** Validation was manual.
- **Legacy plot 02** has a hardcoded classical reference line that may be stale.
- **Readout is the mode, not the best sample.** Consider scoring the top-k samples.
- **Warm-start path is unused.** `build_warm_started_qaoa` and `solve_continuous_relaxation` exist but are not on the active path.
- **2025 validation is not implemented** in any report or plot.
- **`src/quantum/optimizers.py`, `scripts/run_experiment.py`, and the notebook are empty.** Intended extension points, not working code.
- **`get_qubo_and_ising` is unused** by the runner.

### If you wanted to make this production-ready

1. Wire the YAML configs into `runner.py` (single source of truth for alpha, depths, seeds, ansatz, penalty).
2. Add a cardinality penalty (or keep Dicke + XY and document the coupling) so the ansatz and Hamiltonian agree.
3. Add unit tests: `is_valid` truth table, QUBO↔QP numeric equivalence, deterministic small-circuit checks.
4. Score the top-k sampled bitstrings and report the best **valid** one, not just the mode.
5. Add a real 2025 out-of-sample report.
6. Replace or remove the hardcoded reference line in plot 02.
7. Add a hardware backend path behind a flag, with error mitigation.
8. Add a `pyproject.toml`, CI, and linting.
