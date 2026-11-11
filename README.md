# Qest-Hack-2026 — Quantum Optimization Sandbox (IBM + IQM)

A small, reproducible Python setup for running **QAOA / VQE-style optimization**
on **IBM Quantum** and **IQM** hardware (or local simulators), on
**Windows, Linux and macOS**.

The example solves a tiny weighted **MaxCut** problem with QAOA:

```
problem -> QUBO -> Ising Hamiltonian -> QAOAAnsatz -> sampler -> best cut
```

---

## Why two environments?

The current IBM and IQM stacks pin **mutually exclusive** versions of `qiskit`
and `pydantic`, so they cannot live in one environment:

| Package | `qiskit-ibm-runtime` 0.52 | `iqm-client` 37 |
|---|---|---|
| `qiskit` | `>=2.3,<3` | `<2.2,>=1.0` |
| `pydantic` | `>=2.13` | `<2.13,>=2.12.4` |

Therefore this repo creates two isolated environments:

| Environment | Purpose | Key packages |
|---|---|---|
| **`qest-ibm`** | IBM Quantum | `qiskit` 2.6, `qiskit-aer` 0.18, `qiskit-ibm-runtime` 0.52, `qiskit-addon-opt-mapper` |
| **`qest-iqm`** | IQM Resonance | `iqm-client` 37 (with Qiskit adapter), `iqm-qaoa` 3.1 |

---

## Supported platforms

- **Windows 10/11** (x64)
- **Linux** (x64)
- **macOS** (Intel and Apple Silicon)

All pinned packages ship wheels for these platforms on Python 3.13. Python 3.14
also works on Linux (verified), but **3.13 is the default** because it has the
widest wheel coverage across all three operating systems.

---

## Prerequisites

- **Python 3.13** (recommended), or 3.14
- Either:
  - **conda** (Miniconda / Anaconda), **or**
  - a working **`python`** with the stdlib `venv` module (no conda required)

Check your tools:

```bash
conda --version
python --version
```

> On Windows use `python`. On some Linux/macOS systems the interpreter is
> `python3` — substitute accordingly.

---

## Setup

### Option A — one command (recommended, all OS)

The bootstrapper uses **conda if available**, otherwise falls back to stdlib
`venv`. It works identically on Windows, Linux and macOS.

```bash
python setup_env.py
```

Force a specific backend:

```bash
python setup_env.py --conda   # named conda envs: qest-ibm, qest-iqm
python setup_env.py --venv    # local venvs: .venv-ibm, .venv-iqm
```

### Option B — conda (all OS)

```bash
conda env create -f environment-ibm.yml
conda env create -f environment-iqm.yml
```

To refresh later:

```bash
conda env update -f environment-ibm.yml --prune
conda env update -f environment-iqm.yml --prune
```

### Option C — plain venv + pip (all OS)

```bash
python -m venv .venv-ibm
python -m venv .venv-iqm
```

```bash
# Linux / macOS
.venv-ibm/bin/python -m pip install -r requirements-ibm.txt
.venv-iqm/bin/python -m pip install -r requirements-iqm.txt
```

```bat
:: Windows (cmd / PowerShell)
.venv-ibm\Scripts\python.exe -m pip install -r requirements-ibm.txt
.venv-iqm\Scripts\python.exe -m pip install -r requirements-iqm.txt
```

> **Do not** install with `pip install --only-binary=:all:`. The optimization
> mapper depends on `docplex`, which is published as a source distribution only.

---

## Activate the environment

**conda** (same command on every OS):

```bash
conda activate qest-ibm     # IBM
conda activate qest-iqm     # IQM
```

**venv**:

```bash
# Linux / macOS
source .venv-ibm/bin/activate
```

```powershell
# Windows PowerShell
.venv-ibm\Scripts\Activate.ps1
```

```bat
:: Windows cmd
.venv-ibm\Scripts\activate.bat
```

---

## Credentials

Copy the template and fill in your keys:

```bash
# Linux / macOS
cp .env.example .env
```

```bat
:: Windows
copy .env.example .env
```

`.env` is loaded automatically by the examples (via `python-dotenv`) and is
git-ignored.

| Variable | Used by | Meaning |
|---|---|---|
| `QISKIT_IBM_TOKEN` | IBM | 44-char IBM Cloud **API key** (not a bearer token) |
| `QISKIT_IBM_INSTANCE` | IBM | Optional service CRN |
| `QISKIT_IBM_CHANNEL` | IBM | `ibm_quantum_platform` (default) |
| `IQM_SERVER_URL` | IQM | `https://resonance.iqm.tech/` (base URL only) |
| `IQM_TOKEN` | IQM | Token from the Resonance dashboard |
| `IQM_QUANTUM_COMPUTER` | IQM | e.g. `garnet`, `sirius`, `garnet:mock` |

Alternatively, save the IBM account once on a trusted machine:

```python
from qiskit_ibm_runtime import QiskitRuntimeService
QiskitRuntimeService.save_account(token="<api-key>", instance="<CRN>", overwrite=True)
```

---

## Run the examples

Run from the **repository root** so the shared `common/` package is importable.

### IBM

```bash
conda activate qest-ibm

python examples/ibm_qaoa.py                         # local noiseless simulation
python examples/ibm_qaoa.py --hardware              # least-busy real IBM backend
python examples/ibm_qaoa.py --hardware --backend ibm_brisbane
```

### IQM

```bash
conda activate qest-iqm

python examples/iqm_qaoa.py                         # local IQMFakeGarnet, no token
python examples/iqm_qaoa.py --resonance             # IQM Resonance (needs .env)
python examples/iqm_qaoa.py --resonance --quantum-computer garnet:mock
```

Each script prints the QUBO/Ising operator, the optimized energy, the top
sampled bitstrings, and the brute-force optimum for comparison.

---

## Project layout

```
.
├── setup_env.py              # cross-platform bootstrapper (conda or venv)
├── environment-ibm.yml       # conda env definition (IBM)
├── environment-iqm.yml       # conda env definition (IQM)
├── requirements-ibm.txt      # pip requirements (IBM)
├── requirements-iqm.txt      # pip requirements (IQM)
├── .env.example              # credentials template
├── common/
│   ├── maxcut.py             # framework-agnostic MaxCut / QUBO helpers
│   └── qiskit_ising.py       # QUBO -> Ising (SparsePauliOp) conversion
└── examples/
    ├── ibm_qaoa.py           # QAOA on IBM (local or hardware)
    └── iqm_qaoa.py           # QAOA on IQM (fake backend or Resonance)
```

---

## Version notes and gotchas

- **Do not use `qiskit-optimization` or `qiskit-algorithms`** for new work — IBM
  no longer supports them. The recommended path is
  `qiskit-addon-opt-mapper` + `QAOAAnsatz`.
- **Do not install `qiskit-ibm-transpiler`** on Python 3.14 (it requires `<3.14`).
- **Do not use the old `qiskit-iqm` package** — it is deprecated and caps Python
  at `<3.13`. The Qiskit adapter now ships with `iqm-client[qiskit]`.
- **IQM auth:** use the base URL only. Do not append the quantum-computer name
  or a `:timeslot` suffix (rejected since `iqm-client` 35).
- **IQM on Python 3.14:** skip the `[qrisp]` extra (Qrisp requires `<3.14`). The
  Qiskit path is unaffected.
- **IBM channel:** `ibm_quantum` was removed. Use `ibm_quantum_platform`
  (default) — no need to pass `channel`.
- **Open Plan:** `Session` is unavailable; submit each iteration as a separate
  job. The example's hardware path already avoids `Session`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `conda: command not found` | Install Miniconda, or use `python setup_env.py --venv` |
| `No matching distribution found for docplex` | You used `--only-binary=:all:`; plain `pip install` works |
| `ModuleNotFoundError: common` | Run the script from the repo root |
| `401 Unauthorized` on IBM | Use a 44-char IBM Cloud API key, not a bearer token |
| IQM URL rejected | Use `https://resonance.iqm.tech/` and pass the QC name separately |
| pip downgrades Qiskit unexpectedly | You are mixing IBM and IQM packages in one env; use the two envs |
