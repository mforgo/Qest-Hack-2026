"""QAOA on a MaxCut instance for IBM Quantum (or local simulation).

Recommended 2026 IBM path:
    qiskit-addon-opt-mapper (model -> QUBO -> Ising)
    qiskit.circuit.library.QAOAAnsatz
    qiskit primitives (StatevectorEstimator/Sampler) or qiskit-ibm-runtime SamplerV2

Usage:
    python examples/ibm_qaoa.py                 # local noiseless simulation
    python examples/ibm_qaoa.py --hardware      # real IBM backend (needs .env)
    python examples/ibm_qaoa.py --hardware --backend ibm_brisbane
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the repo root importable when running `python examples/ibm_qaoa.py`
# (works on Windows, Linux and macOS).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import rustworkx as rx
from dotenv import load_dotenv
from qiskit.circuit.library import QAOAAnsatz
from qiskit.primitives import StatevectorEstimator, StatevectorSampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_addon_opt_mapper.applications import Maxcut
from qiskit_addon_opt_mapper.converters import OptimizationProblemToQubo
from qiskit_addon_opt_mapper.translators import to_ising
from scipy.optimize import minimize

from common.maxcut import EDGES, NUM_NODES, brute_force

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REPS = 2
SHOTS = 4096


def build_cost_operator():
    """MaxCut graph -> optimization problem -> QUBO -> Ising Hamiltonian."""
    graph = rx.PyGraph()
    graph.add_nodes_from(range(NUM_NODES))
    graph.add_edges_from([(i, j, w) for i, j, w in EDGES])
    problem = Maxcut(graph).to_optimization_problem()
    qubo = OptimizationProblemToQubo().convert(problem)
    return to_ising(qubo)  # (SparsePauliOp, offset)


def optimize_locally(cost_operator, reps: int = REPS, seed: int = 42):
    """Tiny COBYLA loop over the QAOA angles using the noiseless estimator."""
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


def measured_circuit(ansatz, params):
    circuit = ansatz.assign_parameters(params)
    circuit.measure_all()
    return circuit


def sample_locally(circuit, shots: int = SHOTS) -> dict[str, int]:
    sampler = StatevectorSampler(seed=1234)
    result = sampler.run([circuit], shots=shots).result()[0]
    return result.data.meas.get_counts()


def sample_hardware(circuit, backend_name: str | None, shots: int = SHOTS) -> dict[str, int]:
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    service = QiskitRuntimeService()  # reads saved account or QISKIT_IBM_* env vars
    if backend_name:
        backend = service.backend(backend_name)
    else:
        backend = service.least_busy(operational=True, simulator=False)

    pass_manager = generate_preset_pass_manager(optimization_level=3, backend=backend)
    isa_circuit = pass_manager.run(circuit)

    sampler = SamplerV2(mode=backend)
    result = sampler.run([isa_circuit], shots=shots).result()[0]
    return result.data.meas.get_counts()


def cut_value(bitstring: str) -> float:
    """Measurement bitstrings are little-endian: rightmost char is qubit 0."""
    bits = tuple(int(c) for c in reversed(bitstring))
    return sum(w for i, j, w in EDGES if bits[i] != bits[j])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hardware", action="store_true", help="run on real IBM hardware")
    parser.add_argument("--backend", default=None, help="IBM backend name (default: least busy)")
    parser.add_argument("--shots", type=int, default=SHOTS)
    args = parser.parse_args()

    best_known, best_bits = brute_force()
    cost_operator, offset = build_cost_operator()
    print(f"QUBO/Ising cost operator: {cost_operator}")
    print(f"offset: {offset}")

    ansatz, params, energy = optimize_locally(cost_operator)
    print(f"Optimized energy: {energy:.4f}  (objective = energy + offset = {energy + offset:.4f})")
    print(f"Optimal angles: {np.round(params, 4)}")

    circuit = measured_circuit(ansatz, params)
    counts = sample_hardware(circuit, args.backend, args.shots) if args.hardware else sample_locally(circuit, args.shots)

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    print("\nTop samples (bitstring, count, cut value):")
    for bitstring, count in ranked[:5]:
        print(f"  {bitstring}  {count:5d}  cut={cut_value(bitstring):.1f}")

    best_sample = max(counts, key=counts.get)
    print(f"\nBest sampled: {best_sample}  cut={cut_value(best_sample):.1f}")
    print(f"Brute-force optimum: {best_bits}  cut={best_known:.1f}")


if __name__ == "__main__":
    main()
