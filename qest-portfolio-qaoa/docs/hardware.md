# Running on Real IBM Quantum Hardware (optional demo)

The default pipeline runs on **Aer**, a simulator on your own CPU. This document describes the **optional** path that sends one small QAOA circuit to a real IBM Quantum backend and reads back actual hardware counts.

You do **not** need this path to use the project. It exists to show that the same constrained circuit can run on real hardware, and to make the simulator-vs-hardware comparison concrete.

---

## 1. The idea: optimize on the simulator, sample on hardware

Running the full COBYLA optimization loop on a real device would be slow and expensive: every energy evaluation would wait in a queue. Instead, the hardware runner uses **two stages**:

1. **Stage 1 — optimize on Aer.** Build the same constrained QAOA ansatz, run COBYLA locally, and keep the best angles. This is cheap and produces a good circuit.
2. **Stage 2 — sample on hardware.** Bind those angles into the circuit, transpile it for the chosen backend, submit it once with a small number of shots, and read the measured bitstrings.

The simulator remains the benchmark. The hardware run is a **demonstration**, not a replacement for the 45-run simulator sweep.

```
data ──► QUBO / Ising ──► constrained QAOA ansatz
                                   │
                     Stage 1: COBYLA on Aer (local)
                                   │  best angles
                                   ▼
                     bind angles ──► transpile for backend
                                   │
                     Stage 2: 1 job, N shots on IBM hardware
                                   │
                                   ▼
                     counts ──► most frequent valid portfolio
                                   │
                                   ▼
                     results/logs/hardware_run_<ts>.json / .csv
```

---

## 2. Why the circuit is kept shallow

A real device has limited coherence time, so circuit **depth** matters. The exact Dicke-state initializer is elegant on a simulator but transpiles to a very deep circuit on hardware. The hardware demo therefore uses a different, shallower combination:

- **Simple initial state** — set one qubit to 1 for each stock in a warm-start portfolio, instead of preparing an equal superposition of all five-stock combinations.
- **Ring XY mixer** — couple neighbouring qubits in a ring instead of all-to-all. Fewer couplings means fewer SWAPs.
- **Optimization level 3** — let Qiskit's transpiler work harder to reduce depth.

### Measured transpiled depth (p = 1, 10 qubits)

These numbers were measured on `ibm_kingston` with the same problem and a warm-started simple state. They are illustrative; exact depth depends on the backend, its coupling map, the transpiler version, and the chosen initial qubits.

| Initial state | Mixer | Optimization level | Transpiled depth | Notes |
|---|---|---:|---:|---|
| Simple (warm start) | Ring | 3 | **426** | The recorded demo run; 236 CZ gates. An earlier dry run measured 318 — depth varies with backend calibration and transpiler seed |
| Simple | Ring | 3 | 364 | Without the warm-start qubit choice |
| Simple | Ring | 1 | 580 | Less transpiler effort |
| Simple | Complete | 3 | 794 | All-to-all mixer costs more SWAPs |
| Simple | Complete | 1 | 1045 | |
| Dicke | Ring | 1 | 8439 | Too deep for a useful hardware demo |
| Dicke | Complete | 1 | 7988 | Too deep for a useful hardware demo |

The takeaway: **Dicke + XY is the right choice on a simulator; simple + ring is the right choice for this hardware demo.** The trade-off is documented rather than hidden.

---

## 3. Warm start: begin near a good portfolio

Instead of starting from a random five-stock selection, the simple initial state is built from the **best valid equal-weight portfolio** found by enumerating the 210 valid combinations and maximizing the Sharpe ratio. Those five stocks get a 1; the rest get a 0.

This does two things:

- It keeps the circuit shallow (no Dicke-state preparation).
- It starts the optimization near a sensible solution, which matters on a noisy device with a small shot budget.

The warm-start tickers are printed when the runner starts, for example:

```
Warm-start portfolio: ['CPA1T.TL', 'ROE1L.VS', 'APG1L.VS', 'PZV1L.VS', 'IGN1L.VS']
```

You can override this with `initial_indices` in the YAML, or by switching `initial_state` to `"dicke"` (accurate but deep).

---

## 4. Prerequisites

- The normal project dependencies (`pip install -r requirements.txt`), including `qiskit-ibm-runtime`.
- An IBM Quantum account with access to at least one operational backend with **10 or more qubits**. A larger dataset needs one qubit per asset (29 for `nasdaq_baltic`, 32 for `nyse`) unless you use `--max-assets N` to select a smaller subset.
- Credentials supplied in **one** of two ways:
  1. A saved Qiskit account (recommended), or
  2. The `QISKIT_IBM_TOKEN` environment variable.

**Never put a token in `configs/ibm_provider.yaml`.** The file is committed; the token is not.

### Save an account once

```bash
python -c "from qiskit_ibm_runtime import QiskitRuntimeService; \
           QiskitRuntimeService.save_account(channel='ibm_quantum_platform', \
           token='YOUR_TOKEN', instance='YOUR_CRN', overwrite=True)"
```

After that, the runner can find the account by name (or use the default saved account).

---

## 5. Configuration

`configs/ibm_provider.yaml` holds **non-secret** settings:

| Key | Default | Meaning |
|---|---|---|
| `account_name` | `""` | Saved account name; empty = default saved account |
| `channel` | `ibm_quantum_platform` | Only used when `QISKIT_IBM_TOKEN` is set |
| `instance` | `""` | IBM Cloud instance CRN, if required by your account |
| `backend` | `""` | Explicit backend; empty = least-busy operational backend |
| `dataset` | `qest` | `qest`, `nasdaq_baltic`, or `nyse`; resolves `<dataset>_*.csv` |
| `max_assets` | `0` | If >0, keep only the top-N assets by individual Sharpe ratio before building the circuit; `0` = all assets |
| `min_qubits` | `10` | **Floor** on backend size; the real minimum is the larger of this and the circuit's qubit count |
| `surrogate_assets` | `10` | Assets used for Stage 1 surrogate angle optimization when the universe is large (`0` disables) |
| `shots` | `2048` | Hardware shots |
| `optimization_level` | `3` | Transpiler effort (0–3) |
| `alpha` | `2.0` | Risk factor (Neutral philosophy) |
| `depth` | `1` | QAOA depth `p`; `p=1` keeps the circuit shallow |
| `initial_state` | `simple` | `simple` (shallow) or `dicke` (exact but deep) |
| `mixer_topology` | `ring` | `ring` (shallow) or `complete` (more mixing) |
| `initial_indices` | `[]` | Empty = warm-start from the best valid portfolio |
| `seed` | `42` | Seed for the simulator optimization stage |
| `sim_maxiter` | `100` | COBYLA iterations on Aer |
| `data_dir` | `data/raw` | Input CSVs |
| `output_dir` | `results/logs` | Where JSON/CSV results are written |
| `top_counts` | `20` | How many bitstrings to keep in the JSON |

Every setting can also be overridden on the command line (see below).

Backend selection now happens **after** the problem and ansatz are built. When no `--backend` is given, the runner picks the least-busy operational backend with at least `max(config["min_qubits"], ansatz.num_qubits)` qubits, so a larger dataset automatically raises the requirement. `--max-assets` is applied before the ansatz is built, so the qubit requirement reflects the subset size, not the original dataset size. An explicit `--backend` is rejected if it has fewer qubits than the ansatz needs. `--list-backends` still filters by `config["min_qubits"]` alone, because it does not build the problem.

---

## 6. Commands

Run from the repository root.

### List available backends

```bash
python -m src.pipeline.hardware_runner --list-backends
```

This prints each operational backend, its qubit count, pending jobs, and status. It does **not** submit anything.

### Validate without submitting

```bash
python -m src.pipeline.hardware_runner --dry-run
```

A dry run checks the credentials, selects a backend, builds the problem, optimizes on Aer, transpiles the circuit, and prints the depth and gate counts. It stops before submission.

### Run the demo

```bash
python -m src.pipeline.hardware_runner --backend ibm_kingston --shots 2048
```

If you omit `--backend`, the least-busy operational backend with at least `min_qubits` is chosen. The job is submitted once; the process waits for the result.

### Run a subset of a large dataset

```bash
python -m src.pipeline.hardware_runner --dataset nasdaq_baltic --max-assets 12 --dry-run
```

This builds a 12-qubit circuit from the 12 highest individual-Sharpe assets, instead of the full 29-qubit universe. The selected tickers are printed and saved in the result. Use `--max-assets 15` for a slightly larger experiment; estimated depths are in §10.

### Useful options

| Flag | Effect |
|---|---|
| `--config PATH` | Use a different YAML config |
| `--backend NAME` | Explicit backend (otherwise least busy) |
| `--dataset NAME` | `qest` (default), `nasdaq_baltic`, or `nyse` |
| `--max-assets N` | Build the circuit on the top-N assets by individual Sharpe ratio (`0` = all) |
| `--data-dir PATH` | Directory holding the `<dataset>_*.csv` files |
| `--shots N` | Hardware shots |
| `--alpha X` | Risk factor |
| `--depth P` | QAOA depth |
| `--initial-state {simple,dicke}` | Initial state |
| `--topology {ring,complete}` | XY mixer connectivity |
| `--seed N` | Simulator-stage seed |
| `--maxiter N` | COBYLA iterations on Aer |
| `--surrogate-assets N` | Stage 1 surrogate size (default 10; `0` disables) |
| `--params "A,B"` | Supply angles directly and skip Stage 1 |
| `--output-dir PATH` | Where to write results |
| `--no-sim-optimize` | Skip stage 1 and use random angles (debugging only) |
| `--allow-deep-circuit` | Submit even when transpiled depth exceeds 2000 |
| `--dry-run` | Validate and stop before submission |
| `--list-backends` | List backends and exit |

### Stage 1 scaling for large universes

Stage 1 never builds an Aer statevector for more than 20 qubits, so large datasets use one of these routes:

- `--max-assets N` shrinks the actual problem to the top-N individual-Sharpe assets before building the Hamiltonian. This reduces circuit width and depth, and is the recommended way to run a large universe on a QPU. `N` must be at least 5; `0` keeps all assets.
- `--surrogate-assets N` (default 10) optimizes the angles on the top-N individual-Sharpe subset and reuses them on the full ansatz when `n_assets > 20`.
- `--params "0.7,0.4"` supplies angles directly and skips Stage 1.
- `--no-sim-optimize` uses random angles (debugging only).

If `n_assets > 20` and `--surrogate-assets 0` is set with no `--params` and no `--no-sim-optimize`, the runner raises a clear `ValueError` instead of silently falling back.

---

## 7. What gets submitted

For the default `qest` configuration:

- 10 qubits (one per stock),
- QAOA depth `p = 1`,
- the warm-started simple initial state,
- a ring XY mixer,
- the sector penalty in the cost operator,
- measurements on all qubits,
- one job with 2048 shots.

By default, larger datasets use **all** of their assets as qubits (`nasdaq_baltic` = 29, `nyse` = 32). Use `--max-assets N` to build the circuit on the top-N individual-Sharpe assets instead. The full-universe runs may be blocked by the depth guard unless `--allow-deep-circuit` is passed; see §10.

The circuit is transpiled to the backend's instruction set (ISA) before submission. The runner prints the depth, size, and operation counts so you can see how expensive the circuit is. It also warns when the transpiled depth exceeds **1000**, and when `initial_state=dicke` is used with more than **12 assets**.

---

## 8. Output files

A real run writes two files with the same timestamp:

```
results/logs/hardware_run_<timestamp>.json
results/logs/hardware_run_<timestamp>.csv
```

### JSON

The JSON keeps the full record, including:

- `timestamp`, `alpha`, `depth`, `seed`
- `dataset`, `dataset_num_assets`, `max_assets`, `subset_indices`, `num_assets`, `num_qubits`, `universe_tickers`
- `sim_energy`, `sim_params`, `num_parameters` (stage 1)
- `sim_params_source` (`simulator`, `surrogate`, `cli`, or `random`), `surrogate_assets`
- `backend`, `job_id`, `shots`
- `transpiled_depth`, `transpiled_size`
- `hardware_best_bitstring`, `hardware_best_count`, `hardware_best_probability`
- `is_valid`, `return_pct`, `volatility_pct`, `sharpe`
- `tickers`, `issues`
- `top_counts` (the most frequent bitstrings and their counts)

### CSV

The CSV is a one-row summary with the same scalar fields (the `top_counts` dictionary is omitted). It is convenient for adding the hardware result to a report or a comparison table.

### How to read the result

- **`hardware_best_bitstring`** is the most frequent measured bitstring. Bit order is reversed to match the stock order used everywhere else.
- **`hardware_best_count` / `hardware_best_probability`** show how often it appeared. A low probability is normal on a noisy device.
- **`is_valid`** checks the same rules as the simulator: exactly five stocks, at most two per sector.
- **`return_pct`, `volatility_pct`, `sharpe`** are computed with the same evaluator as the simulator runs, so the numbers are directly comparable.
- **`sim_energy`** is the energy found on Aer before submission. It is not a hardware measurement; it tells you what the angles were optimized for.

---

## 9. Measured example from this repository

This is a real run recorded on **2026-11-12** with the default configuration, `--backend ibm_kingston --shots 2048 --maxiter 60`:

| Field | Value |
|---|---|
| Backend | `ibm_kingston` (156 qubits) |
| Job id | `dbr3glhabdes73fp7v20` |
| QAOA depth | `p = 1` |
| Simulator energy (stage 1) | `0.047572` |
| Optimized angles | `[3.141586, 0.688035]` |
| Transpiled depth / size | `426` / `1079` |
| Gate counts | `sx` 442, `rz` 363, `cz` 236, `x` 28, `measure` 10 |
| Shots | 2048 |
| Best bitstring | `0001110110` |
| Best count / probability | 611 / 2048 = **29.83%** |
| Valid | **Yes** |
| Tickers | `CPA1T.TL`, `ROE1L.VS`, `APG1L.VS`, `PZV1L.VS`, `IGN1L.VS` |
| Return / volatility | 14.36% / 12.37% |
| Sharpe | 1.161 |

The hardware result recovered exactly the **warm-start portfolio** (the best valid portfolio by Sharpe), and it was the most frequent bitstring by a wide margin (611 shots; the next most frequent had 120). That is a good outcome for a single noisy run, but it is still one sample: do not read it as a general hardware advantage.

The saved files are:

```
results/logs/hardware_run_20261112_231745.json
results/logs/hardware_run_20261112_231745.csv
```

---

## 10. Large universes (29/32 assets)

The `nasdaq_baltic` (29) and `nyse` (32) universes are too deep to run in full on current IBM hardware. Use `--max-assets N` to build the circuit on the top-N individual-Sharpe assets; this is the practical QPU path. The runner blocks any submission whose transpiled depth exceeds **2000** unless `--allow-deep-circuit` is passed.

### Estimated transpiled depth (fake backend)

Measured with `FakeSherbrooke` (127 qubits), `optimization_level=3`, `p=1`, `initial_state=simple`, `mixer_topology=ring`, and the same top-Sharpe subset selection used by `--max-assets`. These are **fake-backend estimates, not real calibration data**; exact depth varies by backend, transpiler version, and seed. A representative run:

| Dataset / subset | Qubits | Transpiled depth | Transpiled size | ECR gates |
|---|---:|---:|---:|---:|
| `qest` (all) | 10 | 582 | 1793 | 213 |
| `nasdaq_baltic` top-10 | 10 | 637 | 1839 | 226 |
| `nasdaq_baltic` top-12 | 12 | 789 | 2539 | 307 |
| `nasdaq_baltic` top-15 | 15 | 1178 | 4051 | 542 |
| `nasdaq_baltic` top-20 | 20 | 2024 | 8306 | 1199 |
| `nyse` top-12 | 12 | 1307 | 3500 | 472 |
| `nyse` top-15 | 15 | 1650 | 4747 | 647 |
| `nasdaq_baltic` full | 29 | 4107 | 19475 | 2744 |
| `nyse` full | 32 | 6378 | 31082 | 4425 |

### What this means

- `qest` (10 assets) and `--max-assets` subsets up to roughly **12–15 assets** are the practical QPU targets.
- A top-20 subset is already around the 2000-depth guard; do not expect a useful result from much larger subsets.
- The full 29/32-asset circuits are **too deep for a useful result**. A run at that depth is a demonstration of scale, not a useful portfolio result. Do not present it as feasible or meaningful.
- The >2000 depth guard blocks those submissions by default. `--allow-deep-circuit` exists only for intentional experiments, not for routine use.
- For a useful QPU run on a large universe, reduce the problem: use `--dataset qest`, or `--dataset nasdaq_baltic --max-assets 12` (or 15). The selected tickers are printed and saved in the result.

---

## 11. Honest caveats

- **This is a demo, not a benchmark.** One small job on a noisy device does not establish quantum advantage, and it is not a statistically strong comparison with the simulator.
- **No error mitigation.** The runner uses the plain sampler. Real deployments would add readout mitigation, dynamical decoupling, or zero-noise extrapolation.
- **Queue time dominates.** The local work takes seconds; the wait for the device can take minutes.
- **Hardware results vary.** Noise, calibration drift, and shot noise all affect the counts. Re-running the same circuit can produce a different most-frequent bitstring.
- **The simulator is still the reference.** The 45-row sweep and the exact classical benchmark remain the basis for the project's conclusions.

---

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Could not create QiskitRuntimeService` | No saved account and no `QISKIT_IBM_TOKEN` | Save an account or export the token |
| `No operational backends found` | Account has no access, or `min_qubits` too high | Check `--list-backends`; lower `min_qubits` |
| Backend selected but job stays `QUEUED` | Normal queue | Wait; the runner blocks until the result arrives |
| Transpiled depth is thousands | `initial_state: dicke`, `topology: complete`, or a large universe | Use `simple` + `ring`, add `--max-assets 12`, or lower `optimization_level` expectations |
| Result is invalid | Hardware noise or too few shots | Increase `--shots`, re-run, or treat it as a noisy sample |
| `ModuleNotFoundError: qiskit_ibm_runtime` | Dependency missing | `pip install -r requirements.txt` |

For the simulator-only workflow, see [`usage.md`](usage.md). For the concepts behind the circuit, see [`concepts.md`](concepts.md).
