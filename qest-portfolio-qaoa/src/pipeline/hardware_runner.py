"""IBM Quantum hardware execution path (opt-in).

The hardware run is deliberately a *two-stage* demo:

1. Optimize the QAOA angles on the local Aer simulator (cheap, no queue).
2. Bind those angles and sample the circuit on a real IBM backend with a small
   number of shots.

This avoids running a full COBYLA loop on hardware, which would be slow,
expensive, and dominated by queue time. The simulator remains the default path
for the full grid search; this module is only used when you explicitly run it.

Usage:
    python -m src.pipeline.hardware_runner --list-backends
    python -m src.pipeline.hardware_runner --dry-run
    python -m src.pipeline.hardware_runner --backend ibm_brisbane --shots 1024

Credentials are never stored in the YAML. They come from a saved Qiskit account
or the QISKIT_IBM_TOKEN environment variable. See configs/ibm_provider.yaml.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from qiskit import transpile
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import EstimatorV2 as AerEstimator
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

from src.data.constraints import DEFAULT_CONSTRAINTS
from src.data.loader import PortfolioData
from src.pipeline.evaluator import evaluate_portfolio
from src.problem.qubo_builder import build_manual_hamiltonian
from src.quantum.ansatzes import build_xy_qaoa
from src.quantum.execution import create_objective_function, optimize_circuit

DEFAULT_CONFIG_PATH = "configs/ibm_provider.yaml"

DEFAULTS = {
    "account_name": "",
    "channel": "ibm_quantum_platform",
    "instance": "",
    "backend": "",
    "min_qubits": 10,
    "shots": 2048,
    "optimization_level": 1,
    "alpha": 2.0,
    "depth": 1,
    "initial_state": "simple",
    "mixer_topology": "ring",
    "initial_indices": [],
    "seed": 42,
    "sim_maxiter": 100,
    "data_dir": "data/raw",
    "dataset": "qest",
    "max_assets": 0,
    "surrogate_assets": 10,
    "output_dir": "results/logs",
    "top_counts": 20,
}


def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Load the YAML config, filling in defaults for missing keys."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config not found: {path}. Expected configs/ibm_provider.yaml."
        )
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    config = dict(DEFAULTS)
    config.update(loaded)
    return config


def build_service(config: dict) -> QiskitRuntimeService:
    """Create a Runtime service without ever printing or storing the token."""
    token = os.environ.get("QISKIT_IBM_TOKEN")
    account_name = (config.get("account_name") or "").strip()

    try:
        if account_name:
            kwargs = {"name": account_name}
            if token:
                kwargs["token"] = token
            return QiskitRuntimeService(**kwargs)

        if token:
            kwargs = {"token": token}
            if config.get("channel"):
                kwargs["channel"] = config["channel"]
            if config.get("instance"):
                kwargs["instance"] = config["instance"]
            return QiskitRuntimeService(**kwargs)

        # No explicit token: fall back to the default saved account.
        return QiskitRuntimeService()
    except Exception as exc:  # pragma: no cover - depends on local credentials
        raise RuntimeError(
            "Could not create QiskitRuntimeService. Save an IBM Quantum account "
            "or set QISKIT_IBM_TOKEN. See configs/ibm_provider.yaml for the "
            "exact commands."
        ) from exc


def select_backend(
    service: QiskitRuntimeService,
    config: dict,
    backend_name: str | None = None,
    min_qubits: int | None = None,
):
    """Return an explicit backend or the least-busy operational one."""
    name = backend_name or (config.get("backend") or "").strip()
    if name:
        return service.backend(name)
    return service.least_busy(
        min_num_qubits=max(int(config["min_qubits"]), min_qubits or 0),
        simulator=False,
        operational=True,
    )


def list_backends(service: QiskitRuntimeService, config: dict) -> list:
    """Return operational non-simulator backends with enough qubits."""
    return service.backends(
        min_num_qubits=int(config["min_qubits"]),
        simulator=False,
        operational=True,
    )


def best_valid_indices(returns, covariance, sector_indices) -> list[int]:
    """Indices of the valid equal-weight portfolio with the highest Sharpe ratio."""
    best, best_sharpe = None, -np.inf
    for combo in itertools.combinations(
        range(len(returns)), DEFAULT_CONSTRAINTS.num_to_select
    ):
        ok, _ = DEFAULT_CONSTRAINTS.is_valid(combo, sector_indices)
        if not ok:
            continue
        weights = np.zeros(len(returns))
        weights[list(combo)] = 1.0 / len(combo)
        ret = float(weights @ returns)
        vol = float(np.sqrt(max(weights @ covariance @ weights, 0.0)))
        sharpe = ret / vol if vol > 0 else 0.0
        if sharpe > best_sharpe:
            best, best_sharpe = list(combo), sharpe
    return best or []


def select_top_sharpe_indices(data, count: int) -> list[int]:
    """Return the indices of the ``count`` highest individual-Sharpe assets."""
    if count <= 0:
        raise ValueError("count must be a positive integer.")
    if count > data.n_assets:
        raise ValueError(
            f"Cannot select {count} assets from a {data.n_assets}-asset dataset."
        )
    returns = np.asarray(data.returns, dtype=float)
    volatilities = np.asarray(data.volatilities, dtype=float)
    sharpe = np.divide(
        returns,
        volatilities,
        out=np.full_like(returns, -np.inf),
        where=volatilities > 0,
    )
    order = np.argsort(-sharpe, kind="stable")
    return sorted(int(index) for index in order[:count])


def build_problem(config: dict):
    """Load data and build the Ising Hamiltonian + constrained XY ansatz."""
    dataset = config["dataset"]
    data = PortfolioData(
        os.path.join(config["data_dir"], f"{dataset}_stock_data.csv"),
        os.path.join(config["data_dir"], f"{dataset}_correlation_2021_2024.csv"),
    )
    dataset_num_assets = data.n_assets

    max_assets = int(config.get("max_assets") or 0)
    subset_indices = None
    if max_assets and max_assets < data.n_assets:
        if max_assets < DEFAULT_CONSTRAINTS.num_to_select:
            raise ValueError(
                f"--max-assets must be at least {DEFAULT_CONSTRAINTS.num_to_select} "
                f"because the portfolio selects {DEFAULT_CONSTRAINTS.num_to_select} "
                f"assets; got {max_assets}."
            )
        subset_indices = select_top_sharpe_indices(data, max_assets)
        data = data.subset(subset_indices)

    ising_op = build_manual_hamiltonian(
        data.returns,
        data.covariance,
        data.sector_indices,
        risk_factor=float(config["alpha"]),
    )
    use_dicke = str(config["initial_state"]).lower() == "dicke"
    configured_indices = list(config.get("initial_indices") or [])
    if subset_indices is not None and configured_indices:
        remap = {original: position for position, original in enumerate(subset_indices)}
        missing = [index for index in configured_indices if index not in remap]
        if missing:
            raise ValueError(
                "config initial_indices are not all in the --max-assets subset; "
                f"missing original indices: {missing}. Remove initial_indices or "
                "choose a larger --max-assets."
            )
        initial_indices = [remap[index] for index in configured_indices]
    else:
        initial_indices = configured_indices or None

    if (
        not use_dicke
        and initial_indices
        and len(initial_indices) != DEFAULT_CONSTRAINTS.num_to_select
    ):
        raise ValueError(
            f"initial_indices must contain exactly "
            f"{DEFAULT_CONSTRAINTS.num_to_select} indices, got "
            f"{len(initial_indices)}."
        )

    if not use_dicke and not initial_indices:
        initial_indices = best_valid_indices(
            data.returns, data.covariance, data.sector_indices
        )
        if not initial_indices:
            raise ValueError(
                f"No valid {DEFAULT_CONSTRAINTS.num_to_select}-asset portfolio "
                f"exists in the selected {data.n_assets}-asset universe under the "
                "sector constraint. Choose a larger --max-assets value or a "
                "different --dataset."
            )

    ansatz = build_xy_qaoa(
        ising_op,
        p_depth=int(config["depth"]),
        use_dicke=use_dicke,
        topology=str(config["mixer_topology"]).lower(),
        initial_indices=initial_indices,
    )
    subset_info = {
        "dataset_num_assets": dataset_num_assets,
        "max_assets": max_assets,
        "subset_indices": subset_indices,
    }
    return data, ising_op, ansatz, initial_indices, subset_info


def optimize_on_simulator(ising_op, ansatz, seed: int, maxiter: int):
    """Stage 1: find good QAOA angles on Aer (no queue, no cost)."""
    backend = AerSimulator()
    estimator = AerEstimator()
    objective = create_objective_function(
        ansatz, ising_op, estimator=estimator, backend=backend
    )
    rng = np.random.default_rng(seed)
    initial_params = rng.uniform(-np.pi, np.pi, ansatz.num_parameters)
    params, energy = optimize_circuit(
        objective, initial_params, method="COBYLA", maxiter=maxiter
    )
    return np.asarray(params, dtype=float), float(energy)


def _parse_params(value: str) -> list[float]:
    """Parse a comma-separated list of QAOA angles."""
    try:
        return [float(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected comma-separated floats, e.g. 0.7,0.4"
        ) from exc


def select_surrogate_indices(data, surrogate_assets: int) -> list[int]:
    """Pick the highest individual-Sharpe assets for the simulator surrogate."""
    if surrogate_assets <= 0:
        raise ValueError("--surrogate-assets must be a positive integer.")
    if surrogate_assets > 20:
        raise ValueError(
            "--surrogate-assets must be <= 20 so stage 1 never builds an Aer "
            "statevector for more than 20 qubits."
        )
    count = min(int(surrogate_assets), data.n_assets)
    return select_top_sharpe_indices(data, count)


def optimize_on_surrogate(
    data,
    config: dict,
    ansatz,
    surrogate_assets: int,
    initial_indices: list[int] | None = None,
):
    """Optimize angles on a high-Sharpe subset and reuse them on the full ansatz."""
    indices = select_surrogate_indices(data, surrogate_assets)
    sub_returns = data.returns[indices]
    sub_covariance = data.covariance[np.ix_(indices, indices)]
    remap = {original: position for position, original in enumerate(indices)}
    sub_sector_indices = {}
    for sector, members in data.sector_indices.items():
        mapped = [remap[index] for index in members if index in remap]
        if mapped:
            sub_sector_indices[sector] = mapped

    sub_ising = build_manual_hamiltonian(
        sub_returns,
        sub_covariance,
        sub_sector_indices,
        risk_factor=float(config["alpha"]),
    )
    use_dicke = str(config["initial_state"]).lower() == "dicke"
    if use_dicke:
        sub_initial_indices = None
    else:
        source_indices = initial_indices or []
        sub_configured = [remap[index] for index in source_indices if index in remap]
        if len(sub_configured) == DEFAULT_CONSTRAINTS.num_to_select:
            sub_initial_indices = sub_configured
        else:
            sub_initial_indices = best_valid_indices(
                sub_returns, sub_covariance, sub_sector_indices
            )
    sub_ansatz = build_xy_qaoa(
        sub_ising,
        p_depth=int(config["depth"]),
        use_dicke=use_dicke,
        topology=str(config["mixer_topology"]).lower(),
        initial_indices=sub_initial_indices,
    )
    params, energy = optimize_on_simulator(
        sub_ising,
        sub_ansatz,
        int(config["seed"]),
        int(config["sim_maxiter"]),
    )
    if len(params) != ansatz.num_parameters:
        raise ValueError(
            f"Surrogate optimized {len(params)} angles but the full ansatz expects "
            f"{ansatz.num_parameters}; keep the same depth/topology/initial state."
        )
    return indices, params, energy


def prepare_hardware_circuit(ansatz, backend, optimization_level: int):
    """Add measurements and transpile for the target backend (ISA circuit)."""
    measured = ansatz.copy()
    measured.measure_all()
    return transpile(
        measured,
        backend=backend,
        optimization_level=optimization_level,
    )


def sample_on_hardware(
    backend,
    isa_circuit,
    params,
    shots: int,
    data,
    config: dict,
) -> dict:
    """Stage 2: bind the optimized angles and sample on the real backend."""
    bound = isa_circuit.assign_parameters(
        dict(zip(isa_circuit.parameters, params))
    )
    sampler = SamplerV2(mode=backend)
    job = sampler.run([(bound,)], shots=shots)
    result = job.result()
    counts = result[0].data.meas.get_counts()

    best_bitstring_str = max(counts, key=counts.get)
    best_bits = [int(bit) for bit in best_bitstring_str[::-1]]
    metrics = evaluate_portfolio(
        best_bits,
        data.returns,
        data.covariance,
        data.tickers,
        data.sector_indices,
    )

    top_counts = dict(
        sorted(counts.items(), key=lambda item: item[1], reverse=True)[
            : int(config["top_counts"])
        ]
    )

    return {
        "backend": backend.name,
        "job_id": job.job_id(),
        "shots": shots,
        "hardware_best_bitstring": best_bitstring_str,
        "hardware_best_count": counts[best_bitstring_str],
        "hardware_best_probability": counts[best_bitstring_str] / shots,
        "is_valid": bool(metrics["valid"]),
        "return_pct": float(metrics["return_pct"]),
        "volatility_pct": float(metrics["volatility_pct"]),
        "sharpe": float(metrics["sharpe_ratio"]),
        "tickers": metrics["selected_tickers"],
        "issues": metrics["issues"],
        "top_counts": top_counts,
    }


def _jsonable(value):
    """Convert numpy / Path / tuple values into JSON-friendly objects."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return value


def save_results(record: dict, output_dir: str) -> tuple[str, str]:
    """Write a JSON record and a one-row CSV summary. Returns both paths."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(output_dir, f"hardware_run_{timestamp}.json")
    csv_path = os.path.join(output_dir, f"hardware_run_{timestamp}.csv")

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(_jsonable(record), handle, indent=2)

    flat = {
        key: (str(value) if isinstance(value, (list, dict)) else value)
        for key, value in record.items()
        if key != "top_counts"
    }
    pd.DataFrame([flat]).to_csv(csv_path, index=False)
    return json_path, csv_path


def _print_backends(backends) -> None:
    print(f"{'backend':<24} {'qubits':>7} {'pending':>9} {'status':<12}")
    print("-" * 56)
    for backend in sorted(backends, key=lambda b: b.name):
        try:
            status = backend.status()
            pending = getattr(status, "pending_jobs", "?")
            operational = getattr(status, "operational", "?")
            status_text = "operational" if operational else "offline"
        except Exception:
            pending, status_text = "?", "?"
        try:
            qubits = backend.num_qubits
        except Exception:
            qubits = "?"
        print(f"{backend.name:<24} {qubits:>7} {pending:>9} {status_text:<12}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a small QAOA sampling demo on real IBM quantum hardware."
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH,
                        help="Path to the IBM provider YAML config.")
    parser.add_argument("--backend", default=None,
                        help="Explicit backend name (default: least busy).")
    parser.add_argument("--shots", type=int, default=None,
                        help="Number of hardware shots (default: from config).")
    parser.add_argument("--alpha", type=float, default=None,
                        help="Risk factor (default: from config).")
    parser.add_argument("--depth", type=int, default=None,
                        help="QAOA depth p (default: from config).")
    parser.add_argument("--initial-state", choices=["dicke", "simple"], default=None,
                        help="Dicke state (accurate, deep) or simple state (shallow).")
    parser.add_argument("--topology", choices=["complete", "ring"], default=None,
                        help="XY mixer connectivity (complete or ring).")
    parser.add_argument("--seed", type=int, default=None,
                        help="Seed for the simulator optimization stage.")
    parser.add_argument("--maxiter", type=int, default=None,
                        help="COBYLA iterations for the simulator stage.")
    parser.add_argument("--output-dir", default=None,
                        help="Where to write the result JSON/CSV.")
    parser.add_argument("--data-dir", default=None,
                        help="Directory containing the stock and correlation CSVs.")
    parser.add_argument("--dataset", default=None,
                        choices=["qest", "nasdaq_baltic", "nyse"],
                        help="Dataset name used to resolve <dataset>_*.csv (default: config).")
    parser.add_argument("--max-assets", type=int, default=None,
                        help="Use only the top-N assets by individual Sharpe ratio "
                             "(0 = all assets; default: config).")
    parser.add_argument("--surrogate-assets", type=int, default=None,
                        help="Assets for surrogate angle optimization when >20 (0 disables).")
    parser.add_argument("--params", type=_parse_params, default=None,
                        help="Comma-separated QAOA angles; skips simulator optimization.")
    parser.add_argument("--list-backends", action="store_true",
                        help="List operational backends and exit.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate credentials, backend, and transpilation without submitting.")
    parser.add_argument("--no-sim-optimize", action="store_true",
                        help="Skip the simulator stage and use random angles.")
    parser.add_argument("--allow-deep-circuit", action="store_true",
                        help="Submit even when transpiled depth exceeds 2000 "
                             "(likely too noisy for a useful QPU result).")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    for key in ("shots", "alpha", "depth", "seed", "sim_maxiter", "output_dir"):
        cli_value = getattr(args, key if key != "sim_maxiter" else "maxiter", None)
        if cli_value is not None:
            config[key] = cli_value
    if args.output_dir is not None:
        config["output_dir"] = args.output_dir
    if args.data_dir is not None:
        config["data_dir"] = args.data_dir
    if args.dataset is not None:
        config["dataset"] = args.dataset
    if args.max_assets is not None:
        config["max_assets"] = args.max_assets
    if args.surrogate_assets is not None:
        config["surrogate_assets"] = args.surrogate_assets
    if args.initial_state is not None:
        config["initial_state"] = args.initial_state
    if args.topology is not None:
        config["mixer_topology"] = args.topology

    if args.list_backends:
        service = build_service(config)
        backends = list_backends(service, config)
        if not backends:
            print("No operational backends found with the requested qubit count.")
            return 1
        _print_backends(backends)
        return 0

    data, ising_op, ansatz, initial_indices, subset_info = build_problem(config)
    print(f"Problem: dataset={config['dataset']}, {data.n_assets} assets, "
          f"{ansatz.num_qubits} qubits, select 5, alpha={config['alpha']}, "
          f"depth p={config['depth']}, init={config['initial_state']}, "
          f"mixer={config['mixer_topology']}")
    if subset_info["subset_indices"] is not None:
        print(f"Subset: top {data.n_assets} of {subset_info['dataset_num_assets']} "
              f"assets by individual Sharpe: {data.tickers}")
    if initial_indices:
        print(f"Warm-start portfolio: {[data.tickers[i] for i in initial_indices]}")

    if str(config["initial_state"]).lower() == "dicke" and data.n_assets > 12:
        print(f"\nWARNING: initial_state=dicke with {data.n_assets} assets prepares an "
              "enormous state vector and transpiles into a very deep circuit. "
              "Use --initial-state simple for large universes.\n")

    if args.params is not None and len(args.params) != ansatz.num_parameters:
        parser.error(
            f"--params provides {len(args.params)} angles but the "
            f"{config['dataset']} ansatz ({ansatz.num_qubits} qubits, "
            f"p={config['depth']}) expects {ansatz.num_parameters}."
        )

    service = build_service(config)
    backend = select_backend(
        service, config, backend_name=args.backend, min_qubits=ansatz.num_qubits
    )
    if backend.num_qubits < ansatz.num_qubits:
        raise ValueError(
            f"Backend {backend.name} has {backend.num_qubits} qubits but the "
            f"{config['dataset']} ansatz needs {ansatz.num_qubits}. Choose a "
            "larger backend or a smaller dataset."
        )
    print(f"Backend: {backend.name} ({backend.num_qubits} qubits)")

    surrogate_assets_used = None
    if args.no_sim_optimize:
        rng = np.random.default_rng(int(config["seed"]))
        params = rng.uniform(-np.pi, np.pi, ansatz.num_parameters)
        sim_energy = None
        sim_params_source = "random"
        print("Skipping simulator optimization; using random angles.")
    elif args.params is not None:
        params = np.asarray(args.params, dtype=float)
        sim_energy = None
        sim_params_source = "cli"
        print(f"Using {len(params)} QAOA angles from --params; skipping simulator "
              "optimization.")
    elif data.n_assets > 20:
        surrogate_assets = int(config["surrogate_assets"])
        if surrogate_assets == 0:
            raise ValueError(
                f"Dataset '{config['dataset']}' has {data.n_assets} assets. Stage 1 "
                "cannot build an Aer statevector for more than 20 qubits, and "
                "--surrogate-assets 0 disables the surrogate. Use one of: "
                "--params to supply QAOA angles, --no-sim-optimize to use random "
                "angles, or --surrogate-assets N (N in 1..20)."
            )
        print(f"Stage 1/2: optimizing {ansatz.num_parameters} angles on a "
              f"{surrogate_assets}-asset surrogate (dataset has {data.n_assets} "
              f"assets, maxiter={config['sim_maxiter']})...")
        indices, params, sim_energy = optimize_on_surrogate(
            data,
            config,
            ansatz,
            surrogate_assets,
            initial_indices=initial_indices,
        )
        surrogate_assets_used = len(indices)
        sim_params_source = "surrogate"
        print(f"Surrogate simulator energy: {sim_energy:.6f}")
        print("\n" + "!" * 78)
        print("WARNING: these QAOA angles were optimized on a surrogate subset of")
        print(f"{surrogate_assets_used} assets ({[data.tickers[i] for i in indices]}),")
        print("not on the full universe. They are a heuristic for the QPU run.")
        print("!" * 78 + "\n")
    else:
        print(f"Stage 1/2: optimizing {ansatz.num_parameters} angles on Aer "
              f"(maxiter={config['sim_maxiter']})...")
        params, sim_energy = optimize_on_simulator(
            ising_op, ansatz, int(config["seed"]), int(config["sim_maxiter"])
        )
        sim_params_source = "simulator"
        print(f"Simulator energy: {sim_energy:.6f}")

    isa_circuit = prepare_hardware_circuit(
        ansatz, backend, int(config["optimization_level"])
    )
    print(f"Transpiled circuit: depth={isa_circuit.depth()}, "
          f"size={isa_circuit.size()}, ops={dict(isa_circuit.count_ops())}")
    depth = int(isa_circuit.depth())
    if depth > 1000:
        print("\nWARNING: transpiled depth exceeds 1000; QPU fidelity may be poor. "
              "Consider p=1, a ring mixer, optimization_level 3, or a smaller "
              "universe.\n")
    if depth > 2000 and not args.allow_deep_circuit:
        raise ValueError(
            f"Transpiled circuit depth is {depth}, which is too deep for a "
            "meaningful run on current IBM hardware (coherence time is on the "
            "order of hundreds of microseconds, while this circuit needs "
            "thousands of two-qubit gates). Use --max-assets N to shrink the "
            "universe (for example --max-assets 12), or pass --allow-deep-circuit "
            "to submit anyway."
        )

    if args.dry_run:
        print("Dry run complete: credentials, backend, and transpilation are valid. "
              "No job submitted.")
        return 0

    print(f"Stage 2/2: submitting {config['shots']} shots to {backend.name}...")
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "dataset": config["dataset"],
        "dataset_num_assets": int(subset_info["dataset_num_assets"]),
        "max_assets": int(subset_info["max_assets"]),
        "subset_indices": subset_info["subset_indices"],
        "num_assets": int(data.n_assets),
        "num_qubits": int(ansatz.num_qubits),
        "universe_tickers": data.tickers,
        "alpha": float(config["alpha"]),
        "depth": int(config["depth"]),
        "seed": int(config["seed"]),
        "sim_energy": sim_energy,
        "sim_params": params.tolist(),
        "sim_params_source": sim_params_source,
        "surrogate_assets": surrogate_assets_used,
        "num_parameters": ansatz.num_parameters,
        "transpiled_depth": int(isa_circuit.depth()),
        "transpiled_size": int(isa_circuit.size()),
    }
    record.update(
        sample_on_hardware(
            backend,
            isa_circuit,
            params,
            int(config["shots"]),
            data,
            config,
        )
    )

    json_path, csv_path = save_results(record, config["output_dir"])
    print("\nHardware result")
    print(f"  backend        : {record['backend']}")
    print(f"  job id         : {record['job_id']}")
    print(f"  best bitstring : {record['hardware_best_bitstring']} "
          f"({record['hardware_best_count']}/{record['shots']} shots)")
    print(f"  valid          : {record['is_valid']}")
    print(f"  tickers        : {record['tickers']}")
    print(f"  return / vol   : {record['return_pct']:.2f}% / {record['volatility_pct']:.2f}%")
    print(f"  sharpe         : {record['sharpe']:.3f}")
    print(f"  saved          : {json_path}")
    print(f"  saved          : {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
