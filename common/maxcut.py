"""A tiny weighted MaxCut instance plus pure-Python helpers.

No Qiskit / IQM imports here on purpose, so both environments can share it.
"""

from __future__ import annotations

import itertools
from typing import Iterable

# Small weighted MaxCut instance: a triangle (0,1,2) plus a pendant node (3).
EDGES: list[tuple[int, int, float]] = [
    (0, 1, 1.0),
    (1, 2, 1.0),
    (0, 2, 1.0),
    (2, 3, 1.0),
]
NUM_NODES: int = 4


def brute_force(
    edges: Iterable[tuple[int, int, float]] = EDGES,
    num_nodes: int = NUM_NODES,
) -> tuple[float, tuple[int, ...]]:
    """Exhaustively find the optimal MaxCut value and one optimal bitstring."""
    edges = list(edges)
    best_value = float("-inf")
    best_bits: tuple[int, ...] = ()
    for bits in itertools.product((0, 1), repeat=num_nodes):
        value = sum(w for i, j, w in edges if bits[i] != bits[j])
        if value > best_value:
            best_value, best_bits = value, bits
    return best_value, best_bits


def maxcut_qubo(
    edges: Iterable[tuple[int, int, float]] = EDGES,
) -> tuple[dict[int, float], dict[tuple[int, int], float]]:
    """Return QUBO coefficients ``(linear, quadratic)`` for MaxCut.

    Maximizing ``sum w * (x_i XOR x_j)`` is equivalent to minimizing
    ``sum w * (-x_i - x_j + 2 x_i x_j)`` with ``x in {0, 1}``.
    """
    linear: dict[int, float] = {}
    quadratic: dict[tuple[int, int], float] = {}
    for i, j, w in edges:
        linear[i] = linear.get(i, 0.0) - w
        linear[j] = linear.get(j, 0.0) - w
        key = (min(i, j), max(i, j))
        quadratic[key] = quadratic.get(key, 0.0) + 2.0 * w
    return linear, quadratic


def evaluate_qubo(
    bits: Iterable[int],
    linear: dict[int, float],
    quadratic: dict[tuple[int, int], float],
) -> float:
    """Evaluate the QUBO objective for a given bitstring."""
    bits = list(bits)
    value = sum(coeff * bits[i] for i, coeff in linear.items())
    value += sum(coeff * bits[i] * bits[j] for (i, j), coeff in quadratic.items())
    return value
