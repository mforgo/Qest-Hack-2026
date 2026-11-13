from qiskit_optimization import QuadraticProgram
from qiskit_optimization.converters import QuadraticProgramToQubo
import itertools
from qiskit.quantum_info import SparsePauliOp

from src.data.constraints import DEFAULT_CONSTRAINTS

def build_manual_hamiltonian(returns, covariance, sector_indices, risk_factor=1.0, penalty_weight=10.0, constraints=DEFAULT_CONSTRAINTS):
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

    # 1. Objective: Minimize Risk (Covariance), matching the QP's risk_factor * x^T Cov x
    # Diagonal variance: risk_factor * Cov_ii * x_i = risk_factor * Cov_ii * (1 - Z_i) / 2
    for i in range(n_assets):
        w = risk_factor * covariance[i, i]
        if abs(w) > 1e-12:
            add_to_pauli(make_string([]), w * 0.5)
            add_to_pauli(make_string([i]), -w * 0.5)

    # Off-diagonal (full symmetric matrix): 2 * risk_factor * Cov_ij * x_i * x_j = risk_factor * Cov_ij / 2 * (I - Z_i)(I - Z_j)
    for i in range(n_assets):
        for j in range(i + 1, n_assets):
            if covariance[i, j] != 0:
                w = risk_factor * covariance[i, j] * 0.5
                add_to_pauli(make_string([]), w)           
                add_to_pauli(make_string([i]), -w)         
                add_to_pauli(make_string([j]), -w)         
                add_to_pauli(make_string([i, j]), w)       

    # 2. Objective: Maximize Return (Minimize negative return)
    for i in range(n_assets):
        w = -returns[i] * 0.5
        add_to_pauli(make_string([]), w)       
        add_to_pauli(make_string([i]), -w)     

    # 3. Sector penalty: penalty_weight * prod_{i in T} x_i with x_i = (1 - Z_i) / 2
    for violating in constraints.violation_combinations(sector_indices):
        n_violating = len(violating)
        base = penalty_weight / (2 ** n_violating)
        for subset_size in range(n_violating + 1):
            for subset in itertools.combinations(violating, subset_size):
                add_to_pauli(
                    make_string(sorted(subset)),
                    base * ((-1) ** subset_size),
                )

    # Remove any zero-weight terms to keep the circuit lean
    pauli_list = [(p_str, weight) for p_str, weight in pauli_dict.items() if abs(weight) > 1e-8]
    
    return SparsePauliOp.from_list(pauli_list)


def build_portfolio_optimization_problem(returns, covariance, sector_indices, risk_factor=1.0, constraints=DEFAULT_CONSTRAINTS):
    """
    Constructs the Quadratic Program for the Coop Pank Challenge.
    """
    qp = QuadraticProgram(name="coop_pank_portfolio")
    n_assets = len(returns)
    
    # Add binary variables for each stock (1 = select, 0 = don't select)
    for i in range(n_assets):
        qp.binary_var(name=f"x_{i}")
        
    # Standard Objective: Minimize (alpha * x^T * Cov * x) - (mu^T * x)
    # The linear component is simply -returns, uncoupled from the risk_factor.
    linear_comp = {f"x_{i}": -returns[i] for i in range(n_assets)}
    quadratic_comp = {}
    for i in range(n_assets):
        for j in range(n_assets):
            if covariance[i, j] != 0:
                quadratic_comp[(f"x_{i}", f"x_{j}")] = risk_factor * covariance[i, j]
                
    qp.minimize(linear=linear_comp, quadratic=quadratic_comp)
    
    # Constraint 1: Select exactly num_to_select stocks
    linear_constraint_select = {f"x_{i}": 1 for i in range(n_assets)}
    qp.linear_constraint(linear=linear_constraint_select, sense="==", rhs=constraints.num_to_select, name="select_k")
    
    # Constraint 2: Maximum max_per_sector stocks per sector
    for sector, indices in constraints.binding_sectors(sector_indices).items():
        sector_const = {f"x_{i}": 1 for i in indices}
        qp.linear_constraint(linear=sector_const, sense="<=", rhs=constraints.max_per_sector, name=f"max_{constraints.max_per_sector}_{sector.replace(' ', '_')}")
        
    return qp

def get_qubo_and_ising(qp: QuadraticProgram, penalty_weight=None):
    """
    Converts the QuadraticProgram containing constraints into an unconstrained QUBO, 
    and then into a SparsePauliOp (Ising Hamiltonian) for Qiskit Runtime.
    """
    conv = QuadraticProgramToQubo(penalty=penalty_weight)
    qubo = conv.convert(qp)
    
    ising_op, offset = qubo.to_ising()
    
    return qubo, ising_op, offset