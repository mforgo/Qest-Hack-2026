import numpy as np
from scipy.optimize import minimize
from qiskit import transpile
from qiskit_aer.primitives import EstimatorV2 as AerEstimator # C++ backend
from qiskit_aer import AerSimulator

def create_objective_function(ansatz, ising_op, estimator=None, backend=None):
    if estimator is None:
        estimator = AerEstimator()
    if backend is None:
        backend = AerSimulator()

    # Tell the transpiler to unroll everything down to standard C++ Aer gates
    transpiled_ansatz = transpile(ansatz, backend=backend, optimization_level=1)
        
    iteration = [0]
    
    def objective(params):
        pub = (transpiled_ansatz, ising_op, params)
        job = estimator.run(pubs=[pub])
        result = job.result()[0]
        energy = result.data.evs
        
        iteration[0] += 1
        if iteration[0] % 10 == 0:
            print(f"  -> Iteration {iteration[0]:03d}: Energy = {energy:.4f}")
            
        return energy
        
    return objective


def optimize_circuit(objective_func, initial_params, method='COBYLA', maxiter=1000):
    """
    Runs the classical optimization loop.
    """
    res = minimize(
        objective_func, 
        x0=initial_params, 
        method=method,
        options={'maxiter': maxiter, 'disp': False}
    )
    return res.x, res.fun