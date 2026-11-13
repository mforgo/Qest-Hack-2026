import os

import matplotlib.pyplot as plt
import numpy as np
from qiskit import transpile
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import EstimatorV2 as AerEstimator
from qiskit_aer.primitives import SamplerV2 as AerSampler

from src.data.constraints import DEFAULT_CONSTRAINTS
from src.problem.qubo_builder import build_manual_hamiltonian
from src.quantum.ansatzes import build_xy_qaoa
from src.quantum.execution import create_objective_function, optimize_circuit

from ._common import save_figure


def _build_problem(data, risk_factor):
    ising_op = build_manual_hamiltonian(
        data.returns, data.covariance, data.sector_indices, risk_factor=risk_factor)
    ansatz = build_xy_qaoa(ising_op, p_depth=1, use_dicke=True)
    return ising_op, ansatz


def plot_ansatz_circuit(data, output_dir, risk_factor=2.0):
    """High-level p=1 QAOA ansatz diagram (initial state + cost + mixer blocks)."""
    _, ansatz = _build_problem(data, risk_factor)
    circuit = ansatz.decompose(reps=1)
    fig = circuit.draw("mpl", fold=60, scale=0.6)
    fig.suptitle("QAOA Ansatz (p=1): Dicke init -> Cost(gamma) -> XY mixer(beta)",
                 fontsize=13)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "17_ansatz_circuit.png")
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")
    return path


def plot_sampled_distribution(data, output_dir, risk_factor=2.0,
                              maxiter=60, shots=4096, seed=42, top=15):
    """Optimize p=1 QAOA briefly, sample, and plot the most frequent bitstrings."""
    ising_op, ansatz = _build_problem(data, risk_factor)
    backend = AerSimulator()
    estimator = AerEstimator()
    sampler = AerSampler()

    objective = create_objective_function(ansatz, ising_op,
                                          estimator=estimator, backend=backend)
    rng = np.random.default_rng(seed)
    init = rng.uniform(-np.pi, np.pi, ansatz.num_parameters)
    opt_params, energy = optimize_circuit(objective, init, method="COBYLA",
                                          maxiter=maxiter)

    measured = ansatz.copy()
    measured.measure_all()
    transpiled = transpile(measured, backend=backend, optimization_level=1)
    bound = transpiled.assign_parameters(dict(zip(ansatz.parameters, opt_params)))
    counts = sampler.run([(bound,)], shots=shots).result()[0].data.meas.get_counts()

    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top]
    labels, freqs, valid_flags = [], [], []
    for bitstring, count in items:
        # Qiskit prints qubit n-1 first; reverse so bit i == stock i.
        bits = [int(c) for c in reversed(bitstring)]
        selected = [i for i, bit in enumerate(bits) if bit == 1]
        ok, _ = DEFAULT_CONSTRAINTS.is_valid(selected, data.sector_indices)
        labels.append(bitstring)
        freqs.append(count / shots)
        valid_flags.append(ok)

    colors = ["#2ca02c" if ok else "#d62728" for ok in valid_flags]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(range(len(labels)), freqs, color=colors)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Sampling probability")
    ax.set_title(f"QAOA Sampled Bitstrings (p=1, energy={energy:.4f})\n"
                 "green = valid, red = constraint-violating", fontsize=13)
    ax.grid(axis="y", alpha=0.3)
    return save_figure(fig, output_dir, "18_sampled_distribution.png")
