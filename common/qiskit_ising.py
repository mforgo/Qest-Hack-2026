"""Convert a QUBO into an Ising cost Hamiltonian (``SparsePauliOp``).

Uses the substitution ``x_i = (1 - Z_i) / 2`` where the Pauli ``Z`` has
eigenvalues ``+1`` for ``x=0`` and ``-1`` for ``x=1``.

This module imports Qiskit, which is available in *both* environments.
"""

from __future__ import annotations

from qiskit.quantum_info import SparsePauliOp

from .maxcut import EDGES, NUM_NODES, maxcut_qubo


def qubo_to_ising(
    linear: dict[int, float],
    quadratic: dict[tuple[int, int], float],
    num_nodes: int,
) -> tuple[SparsePauliOp, float]:
    """Return ``(cost_hamiltonian, offset)`` for a minimization QUBO.

    For every bitstring ``x`` the relation ``<x|H|x> + offset`` equals the
    QUBO objective value (see ``common.maxcut.evaluate_qubo``).
    """
    z_coeff: dict[int, float] = {i: 0.0 for i in range(num_nodes)}
    zz_coeff: dict[tuple[int, int], float] = {}
    offset = 0.0

    # linear terms: c_i * (1 - Z_i) / 2
    for i, c in linear.items():
        offset += c / 2.0
        z_coeff[i] -= c / 2.0

    # quadratic terms: Q_ij * (1 - Z_i)(1 - Z_j) / 4
    for (i, j), q in quadratic.items():
        offset += q / 4.0
        z_coeff[i] -= q / 4.0
        z_coeff[j] -= q / 4.0
        zz_coeff[(i, j)] = zz_coeff.get((i, j), 0.0) + q / 4.0

    terms: list[tuple[str, float]] = []

    def label(qubits: list[int]) -> str:
        # Qiskit uses little-endian labels: index 0 is the highest qubit.
        chars = ["I"] * num_nodes
        for q in qubits:
            chars[num_nodes - 1 - q] = "Z"
        return "".join(chars)

    for i, coeff in z_coeff.items():
        if abs(coeff) > 1e-12:
            terms.append((label([i]), coeff))
    for (i, j), coeff in zz_coeff.items():
        if abs(coeff) > 1e-12:
            terms.append((label([i, j]), coeff))

    if not terms:
        terms.append(("I" * num_nodes, 0.0))

    return SparsePauliOp.from_list(terms), offset


def maxcut_hamiltonian(
    edges=EDGES,
    num_nodes: int = NUM_NODES,
) -> tuple[SparsePauliOp, float]:
    """Convenience wrapper: MaxCut edges -> Ising cost Hamiltonian + offset."""
    linear, quadratic = maxcut_qubo(edges)
    return qubo_to_ising(linear, quadratic, num_nodes)
