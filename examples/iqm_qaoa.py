"""QAOA on a MaxCut instance for IQM (local fake backend by default).

Uses the IQM Qiskit adapter (``iqm.qiskit_iqm``) that ships with ``iqm-client``.
The optimization layer is plain Qiskit, so the same circuit works on IQM.

Usage:
    python examples/iqm_qaoa.py                  # local IQMFakeGarnet, no token
    python examples/iqm_qaoa.py --resonance      # IQM Resonance (needs .env)
    python examples/iqm_qaoa.py --resonance --quantum-computer garnet:mock
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make the repo root importable when running `python examples/iqm_qaoa.py`
# (works on Windows, Linux and macOS).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from dotenv import load_dotenv
from qiskit.circuit.library import QAOAAnsatz
from qiskit.primitives import StatevectorEstimator
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from scipy.optimize import minimize

from common.maxcut import EDGES, NUM_NODES, brute_force
from common.qiskit_ising import maxcut_hamiltonian

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REPS = 2
SHOTS = 2048


def optimize_locally(cost_operator, reps: int = REPS, seed: int = 42):
    """Tiny COBYLA loop over the QAOA angles (noiseless, local)."""
    ansatz = QAOAAnsatz(cost_operator=cost_operator, reps=reps)
    estimator = StatevectorEstimator()
    rng = np.random.default_rng(seed)
    x0 = rng.uniform(0.0, np.pi, ansatz.num_parameters)

    def objective(params: np.ndarray) -> float:
        pub = (ansatz, cost_operator, [params])
        evs = estimator.run([pub]).result()[0].data.evs
        return float(np.asarray(evs).ravel()[0])

    result = minimize(objective, x0, method="COBYLA", options={"maxiter": 200})
    return ansatz, result.x, float(result.fun)


def get_local_backend():
    from iqm.qiskit_iqm import IQMFakeGarnet

    return IQMFakeGarnet()


def get_resonance_backend(quantum_computer: str | None):
    from iqm.qiskit_iqm import IQMProvider

    url = os.getenv("IQM_SERVER_URL", "https://resonance.iqm.tech/")
    token = os.getenv("IQM_TOKEN")
    if not token:
        raise SystemExit("IQM_TOKEN is not set. Fill in .env or export it.")
    qc = quantum_computer or os.getenv("IQM_QUANTUM_COMPUTER", "garnet:mock")
    provider = IQMProvider(url=url, quantum_computer=qc, token=token)
    return provider.get_backend()


def cut_value(bitstring: str) -> float:
    """Measurement bitstrings are little-endian: rightmost char is qubit 0."""
    bits = tuple(int(c) for c in reversed(bitstring))
    return sum(w for i, j, w in EDGES if bits[i] != bits[j])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resonance", action="store_true", help="use IQM Resonance instead of local fake backend")
    parser.add_argument("--quantum-computer", default=None, help="IQM QC name (default: $IQM_QUANTUM_COMPUTER)")
    parser.add_argument("--shots", type=int, default=SHOTS)
    args = parser.parse_args()

    best_known, best_bits = brute_force()
    cost_operator, offset = maxcut_hamiltonian()
    print(f"QUBO/Ising cost operator: {cost_operator}")
    print(f"offset: {offset}")

    ansatz, params, energy = optimize_locally(cost_operator)
    print(f"Optimized energy: {energy:.4f}  (objective = energy + offset = {energy + offset:.4f})")
    print(f"Optimal angles: {np.round(params, 4)}")

    backend = get_resonance_backend(args.quantum_computer) if args.resonance else get_local_backend()
    print(f"Backend: {backend.name}")

    circuit = ansatz.assign_parameters(params)
    circuit.measure_all()
    pass_manager = generate_preset_pass_manager(optimization_level=1, backend=backend)
    isa_circuit = pass_manager.run(circuit)

    job = backend.run(isa_circuit, shots=args.shots)
    counts = job.result().get_counts()

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    print("\nTop samples (bitstring, count, cut value):")
    for bitstring, count in ranked[:5]:
        print(f"  {bitstring}  {count:5d}  cut={cut_value(bitstring):.1f}")

    best_sample = max(counts, key=counts.get)
    print(f"\nBest sampled: {best_sample}  cut={cut_value(best_sample):.1f}")
    print(f"Brute-force optimum: {best_bits}  cut={best_known:.1f}")


if __name__ == "__main__":
    main()
