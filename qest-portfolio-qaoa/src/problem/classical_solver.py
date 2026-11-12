from qiskit_optimization import QuadraticProgram
from qiskit_optimization.algorithms import MinimumEigenOptimizer, SlsqpOptimizer
from qiskit_algorithms import NumPyMinimumEigensolver

def solve_exact_classical(qp: QuadraticProgram):
    """
    Solves the QuadraticProgram exactly using classical matrix diagonalization.
    This provides the absolute ground truth (optimal portfolio and target energy) 
    to benchmark our QAOA results against.
    
    Args:
        qp (QuadraticProgram): The formulated portfolio problem.
        
    Returns:
        OptimizationResult: Contains the exact bitstring and minimum energy.
    """
    # NumPyMinimumEigensolver computes the exact ground state of the Hamiltonian
    exact_mes = NumPyMinimumEigensolver()
    exact_optimizer = MinimumEigenOptimizer(exact_mes)
    
    # Solve the problem
    result = exact_optimizer.solve(qp)
    return result


def solve_continuous_relaxation(qp: QuadraticProgram):
    """
    Relaxes the binary constraints (x in {0, 1}) to continuous bounds (0 <= x <= 1).
    This provides the classical probability distribution needed to set the initial 
    Ry rotation angles for Warm-Started QAOA.
    
    Args:
        qp (QuadraticProgram): The original binary portfolio problem.
        
    Returns:
        np.ndarray: An array of continuous values between 0 and 1 for each asset.
    """
    # Create a new relaxed problem
    relaxed_qp = QuadraticProgram(name="relaxed_coop_pank")
    
    # Copy variables but make them continuous between 0 and 1
    for var in qp.variables:
        relaxed_qp.continuous_var(lowerbound=0, upperbound=1, name=var.name)
        
    # Copy objective
    relaxed_qp.objective.sense = qp.objective.sense
    relaxed_qp.objective.constant = qp.objective.constant
    relaxed_qp.objective.linear = qp.objective.linear.to_dict()
    relaxed_qp.objective.quadratic = qp.objective.quadratic.to_dict()
    
    # Copy constraints
    for constraint in qp.linear_constraints:
        relaxed_qp.linear_constraint(
            linear=constraint.linear.to_dict(),
            sense=constraint.sense,
            rhs=constraint.rhs,
            name=constraint.name
        )
        
    # Solve using Sequential Least SQuares Programming (SLSQP)
    slsqp = SlsqpOptimizer()
    relaxed_result = slsqp.solve(relaxed_qp)
    
    return relaxed_result.x