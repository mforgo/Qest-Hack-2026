import numpy as np
from qiskit.circuit.library import QAOAAnsatz
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp

from src.data.constraints import DEFAULT_CONSTRAINTS

def build_dicke_state(num_qubits, k):
    """
    Builds a pure Dicke state: an equal superposition of all states with exactly k ones.
    Perfect for simulators, though deep for real QPUs.
    """
    dim = 2 ** num_qubits
    state_array = np.zeros(dim)
    
    # Find all binary combinations with exactly k ones
    count = 0
    for i in range(dim):
        if bin(i).count("1") == k:
            state_array[i] = 1.0
            count += 1
            
    # Normalize the amplitudes
    state_array = state_array / np.sqrt(count)
    
    qc = QuantumCircuit(num_qubits)
    qc.prepare_state(state_array) # Qiskit automatically synthesizes the initialization gates
    return qc

def build_simple_valid_state(num_qubits, k, indices=None):
    """
    A shallow hardware-friendly alternative to Dicke states for noisy IBM QPUs. 
    Starts in a single valid state (e.g. 1111100000), allowing the XY-mixer to spread it out.
    """
    qc = QuantumCircuit(num_qubits)
    positions = list(range(k)) if indices is None else list(indices)
    if len(positions) != k:
        raise ValueError(f"Expected {k} initial indices, got {len(positions)}")
    for i in positions:
        qc.x(i)
    return qc

def build_xy_mixer(num_qubits, topology="complete"):
    """
    Builds the XY Mixer operator: 0.5 * sum(X_i X_j + Y_i Y_j)
    """
    pauli_list = []
    
    for i in range(num_qubits):
        for j in range(i + 1, num_qubits):
            if topology == "ring" and (j - i != 1) and not (i == 0 and j == num_qubits - 1):
                continue # Ring topology only connects adjacent qubits for lower circuit depth
                
            chars_x = ['I'] * num_qubits
            chars_x[num_qubits - 1 - i] = 'X'
            chars_x[num_qubits - 1 - j] = 'X'
            
            chars_y = ['I'] * num_qubits
            chars_y[num_qubits - 1 - i] = 'Y'
            chars_y[num_qubits - 1 - j] = 'Y'
            
            pauli_list.append(("".join(chars_x), 0.5))
            pauli_list.append(("".join(chars_y), 0.5))
            
    return SparsePauliOp.from_list(pauli_list)

def build_xy_qaoa(ising_op, p_depth=1, use_dicke=True, topology="complete",
                  initial_indices=None, constraints=DEFAULT_CONSTRAINTS):
    """
    Assembles the constrained XY-Mixer QAOA.
    """
    num_qubits = ising_op.num_qubits
    
    # 1. Initialization (Constrained to num_to_select stocks)
    if use_dicke:
        initial_state = build_dicke_state(num_qubits, k=constraints.num_to_select)
    else:
        initial_state = build_simple_valid_state(
            num_qubits, k=constraints.num_to_select, indices=initial_indices
        )
        
    # 2. Mixer (Preserves exactly 5 stocks)
    mixer_op = build_xy_mixer(num_qubits, topology=topology)
    
    # 3. Assemble
    ansatz = QAOAAnsatz(
        cost_operator=ising_op,
        reps=p_depth,
        initial_state=initial_state,
        mixer_operator=mixer_op
    )
    
    return ansatz

def build_standard_qaoa(ising_op, p_depth=1):
    """
    Builds the standard QAOA circuit starting from a uniform superposition.
    """
    # QAOAAnsatz automatically generates the cost and mixer operators
    ansatz = QAOAAnsatz(cost_operator=ising_op, reps=p_depth)
    return ansatz

def build_warm_started_qaoa(ising_op, relaxed_probabilities, p_depth=1):
    """
    Builds a Warm-Started QAOA circuit.
    Instead of Hadamard gates, applies Ry rotations based on classical probabilities.
    
    Args:
        ising_op (SparsePauliOp): The Hamiltonian.
        relaxed_probabilities (np.ndarray): Continuous solution from SLSQP (0 to 1).
        p_depth (int): QAOA depth.
    """
    num_qubits = ising_op.num_qubits
    
    # Ensure probabilities map only to the stock qubits, not slack variables
    # (assuming stock qubits are the first N qubits)
    stock_probs = relaxed_probabilities[:num_qubits] 
    
    # 1. Create the initial state circuit using Ry rotations
    # theta = 2 * arcsin(sqrt(probability))
    initial_state = QuantumCircuit(num_qubits)
    for i, prob in enumerate(stock_probs):
        # Clip probability to [0, 1] to avoid math domain errors
        prob = np.clip(prob, 0.0, 1.0)
        theta = 2 * np.arcsin(np.sqrt(prob))
        initial_state.ry(theta, i)
        
    # 2. Build the QAOA circuit injecting the custom initial state
    ansatz = QAOAAnsatz(
        cost_operator=ising_op, 
        reps=p_depth,
        initial_state=initial_state
    )
    
    return ansatz