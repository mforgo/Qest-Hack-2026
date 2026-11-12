from qiskit_optimization import QuadraticProgram
from qiskit_optimization.converters import QuadraticProgramToQubo
from qiskit.quantum_info import SparsePauliOp

from qiskit.quantum_info import SparsePauliOp

def build_manual_hamiltonian(returns, covariance, sector_indices, penalty_weight=10.0, sector_tax=2.0):
    n_assets = len(returns)
    pauli_dict = {}
    
    def add_to_pauli(pauli_str, weight):
        if pauli_str in pauli_dict:
            pauli_dict[pauli_str] += weight
        else:
            pauli_dict[pauli_str] = weight

    def make_string(z_indices):
        chars = ['I'] * n_assets
        for idx in z_indices:
            chars[n_assets - 1 - idx] = 'Z'
        return "".join(chars)

    # 1. Objective: Minimize Risk (Covariance)
    for i in range(n_assets):
        for j in range(i + 1, n_assets):
            if covariance[i, j] != 0:
                w = covariance[i, j] * 0.25
                add_to_pauli(make_string([]), w)           
                add_to_pauli(make_string([i]), -w)         
                add_to_pauli(make_string([j]), -w)         
                add_to_pauli(make_string([i, j]), w)       

    # 2. Objective: Maximize Return
    for i in range(n_assets):
        w = -returns[i] * 0.5
        add_to_pauli(make_string([]), w)       
        add_to_pauli(make_string([i]), -w)     

    # 3. Penalty: Exactly 5 stocks
    add_to_pauli(make_string([]), 2.5 * penalty_weight)  
    for i in range(n_assets):
        for j in range(i + 1, n_assets):
            add_to_pauli(make_string([i, j]), 0.5 * penalty_weight) 
            
    # 4. General Sector Penalty (Heuristic)
    # Dynamically apply a tax to any pair of stocks within the same oversized sector
    for sector_name, indices in sector_indices.items():
        if len(indices) > 2:
            # Add penalty sector_tax * x_i * x_j
            # x_i * x_j = 0.25 * (I - Z_i - Z_j + Z_i Z_j)
            w = sector_tax * 0.25
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    idx_i = indices[i]
                    idx_j = indices[j]
                    add_to_pauli(make_string([]), w)
                    add_to_pauli(make_string([idx_i]), -w)
                    add_to_pauli(make_string([idx_j]), -w)
                    add_to_pauli(make_string([idx_i, idx_j]), w)
            
    # Remove any zero-weight terms to keep the circuit fast
    pauli_list = [(p_str, weight) for p_str, weight in pauli_dict.items() if abs(weight) > 1e-8]
    
    return SparsePauliOp.from_list(pauli_list)


def build_portfolio_optimization_problem(returns, covariance, sector_indices, risk_factor=0.5):
    """
    Constructs the Quadratic Program for the Coop Pank Challenge.
    
    Args:
        returns (np.ndarray): Expected returns (mu).
        covariance (np.ndarray): Covariance matrix (Sigma).
        sector_indices (dict): Dictionary mapping sector names to lists of stock indices.
        risk_factor (float): Trade-off between risk and return. 
                             High = risk averse, Low = yield seeking.
    
    Returns:
        QuadraticProgram: The optimization problem.
    """
    qp = QuadraticProgram(name="coop_pank_portfolio")
    n_assets = len(returns)
    
    # Add binary variables for each stock (1 = select, 0 = don't select)
    for i in range(n_assets):
        qp.binary_var(name=f"x_{i}")
        
    # Set Objective: Minimize (risk_factor * x^T * Cov * x) - ((1 - risk_factor) * mu^T * x)
    # Note: Qiskit minimizes by default.
    linear_comp = {f"x_{i}": -(1.0 - risk_factor) * returns[i] for i in range(n_assets)}
    quadratic_comp = {}
    for i in range(n_assets):
        for j in range(n_assets):
            if covariance[i, j] != 0:
                quadratic_comp[(f"x_{i}", f"x_{j}")] = risk_factor * covariance[i, j]
                
    qp.minimize(linear=linear_comp, quadratic=quadratic_comp)
    
    # Constraint 1: Select exactly 5 stocks
    linear_constraint_5 = {f"x_{i}": 1 for i in range(n_assets)}
    qp.linear_constraint(linear=linear_constraint_5, sense="==", rhs=5, name="select_5")
    
    # Constraint 2: Maximum 2 stocks per sector
    for sector, indices in sector_indices.items():
        if len(indices) <= 2:
            continue # Trivial constraint: skip it to save qubits!
            
        sector_const = {f"x_{i}": 1 for i in indices}
        qp.linear_constraint(linear=sector_const, sense="<=", rhs=2, name=f"max_2_{sector.replace(' ', '_')}")
        
    return qp

def get_qubo_and_ising(qp: QuadraticProgram, penalty_weight=None):
    """
    Converts the QuadraticProgram containing constraints into an unconstrained QUBO, 
    and then into a SparsePauliOp (Ising Hamiltonian) for Qiskit Runtime.
    """
    # Converter automatically handles slack variables for the inequality constraints (<= 2)
    # and penalty terms for the equality constraint (== 5).
    conv = QuadraticProgramToQubo(penalty=penalty_weight)
    qubo = conv.convert(qp)
    
    # Convert QUBO to Ising Hamiltonian (SparsePauliOp) and an offset constant
    ising_op, offset = qubo.to_ising()
    
    return qubo, ising_op, offset