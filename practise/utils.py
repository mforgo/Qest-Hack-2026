import numpy as np

from qiskit.quantum_info import SparsePauliOp
from qiskit.circuit.library import QAOAAnsatz
from qiskit_ibm_runtime.executor_sampler import Sampler
from qiskit_ibm_runtime.executor_estimator import Estimator
from qiskit_aer import AerSimulator
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager


def compute_exact_sols(hamiltonian: SparsePauliOp) -> tuple[float, list[str]]:
    """
    Computes the solutions to the input hamiltonian classically by 
    diagonalizing the matrix representation of the Hamiltonian.

    Args:
        hamiltonian (SparsePauliOp): Hamiltonian to diagonalize expressed as a sum of Pauli operators.

    Returns:
        tuple[float, list[str]]:
            - Computed minimum cost (float)
            - List of binary solutions associated to the minimal cost.
    """
    # Transforms the hamiltonian into a matrix
    hamiltonian_mat = np.array(hamiltonian.to_matrix())
    # Diagonalize the matrix to extract the eigenvalues and eigenvectors
    eigenvals, eigenvects = np.linalg.eig(hamiltonian_mat)

    # Smallest eigenvalues indices
    min_eigenval = np.where(eigenvals == np.min(eigenvals))[0]
    # Minimum solutions associated to the smallest eigenvalues
    binary_sols = [bin(idx).lstrip("-0b").zfill(hamiltonian.num_qubits) for idx in min_eigenval]

    # Cost and binary chains associated to each best solution
    return eigenvals[min_eigenval][0].real, binary_sols


def compute_score(
    params: np.ndarray, num_layers: int, hamiltonian: SparsePauliOp) -> tuple[float, float]:
    """
    Computes the score associated to the input optimal parameters, given a quantum circuit with a specified number of
    layers.

    Args:
        params (np.ndarray): Optimal parameters found during the classical optimization.
        num_layers (int): Number of layers needed to build the QAOA circuit.
        hamiltonian (SparsePauliOp): Problem Hamiltonian (cost function).

    Returns:
        tuple[float, float]: Optimal cost and score (percentage) of the solution found
    """
    # QAOA circuit instanciation
    circuit = QAOAAnsatz(hamiltonian, reps=num_layers)
    # Compute the exact solutions to compare with experimentl solutions at the end
    _, binary_sols = compute_exact_sols(hamiltonian)

    # Generate the probability distribution with the input optimal parameters
    backend = AerSimulator()
    sampler = Sampler(mode=backend)
    sampler.options.default_shots = 1e5
    circuit_copy = circuit.decompose(reps=2).copy()
    circuit_copy.measure_all()
    data = sampler.run([(circuit_copy, params)]).result()[0].data.meas
    counts = data.get_counts()
    num_shots = data.num_shots

    # Compute the score (percentage of good solutions found over the number of times the circuit was executed i.e
    # number of shots)
    score = 0
    for sol in binary_sols:
        if sol in counts:
            score += counts[sol]
    score /= num_shots
    score *= 100.0

    # Compute the average value (count) when using the input optimal parameters
    estimator = Estimator(mode=backend)
    estimator.options.default_precision = 0.01
    pm = generate_preset_pass_manager(backend=estimator._backend, optimization_level=1)
    isa_psi = pm.run(circuit)
    isa_observables = hamiltonian.apply_layout(isa_psi.layout)
    cost = estimator.run([(isa_psi, isa_observables, params)]).result()[0].data.evs

    print("Optimal cost : ", cost)
    print("Score : ", score)

    return cost, score


def save_res(filename: str, params: np.ndarray, num_layers: int, hamiltonian: SparsePauliOp):
    """
    Saves the optimal parameters found for the QAOA circuit, as well as its circuit configuration.
    The saved file must be handed to the judges.

    Args:
        filename (str): Filename for the saved file. Use a meaningful name for your submission.
        params (np.ndarray): Optimal parameters.
        num_layers (int): Number of circuit layers to build the right QAOA circuit instance.
        hamiltonian (SparsePauliOp): problem Hamiltonian expressed as a sum of Pauli operators.
    """
    np.savez(file=filename, params=params, num_layers=num_layers, hamiltonian=hamiltonian)


def read_res(filename: str):
    """
    Reads the information saved with the function above.

    Args:
        filename (str): Name of a saved file.

    Returns:
        tuple[float, int, SparsePauliOp]: Previously saved optimal parameters, number of layers in the QAOA circuit and
                                          problem Hamiltonian
    """
    file = np.load(filename)
    params = file["params"]
    num_layers = file["num_layers"]
    hamiltonian = file["hamiltonian"]

    return params, num_layers, hamiltonian