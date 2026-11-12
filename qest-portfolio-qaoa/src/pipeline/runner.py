import numpy as np
import pandas as pd
import json
from src.data.loader import PortfolioData
from src.problem.classical_solver import solve_exact_classical, solve_continuous_relaxation
from src.quantum.ansatzes import build_standard_qaoa, build_warm_started_qaoa, build_xy_qaoa
from src.quantum.execution import create_objective_function, optimize_circuit
from src.pipeline.evaluator import evaluate_portfolio
from src.problem.qubo_builder import (
    build_portfolio_optimization_problem, 
    get_qubo_and_ising,
    build_manual_hamiltonian
)
from src.problem.qubo_builder import build_portfolio_optimization_problem, get_qubo_and_ising
from qiskit_aer.primitives import SamplerV2 as AerSampler
import warnings
from scipy.sparse import SparseEfficiencyWarning
from qiskit import transpile
from qiskit_aer import AerSimulator


def run_grid_search():
    # Hide SciPy sparse matrix conversion warnings during local simulation
    warnings.simplefilter('ignore', SparseEfficiencyWarning)

    # 1. Load Data
    print("Loading data...")
    data = PortfolioData("data/raw/qest_stock_data.csv", "data/raw/qest_correlation_2021_2024.csv")
    returns, covariance, sector_indices, tickers = data.get_formulation_data()
    
    # 2. Build Formulations
    print("Building classical QP and manual Ising Hamiltonian...")

   # We still need the QP for the classical exact solver and continuous relaxation
    qp = build_portfolio_optimization_problem(returns, covariance, sector_indices, risk_factor=0.5)
    
    # Pass the sector_indices into the manual builder
    ising_op = build_manual_hamiltonian(
        returns, 
        covariance, 
        sector_indices=sector_indices, 
        penalty_weight=10.0,
        sector_tax=2.0
    ) 
    
    # The manual Hamiltonian includes the Identity (II...I) term directly inside 
    # the SparsePauliOp, so the Estimator will calculate the offset for us.
    offset = 0.0
    
    # 3. Get Classical Baselines
    print("Computing classical baselines...")
    exact_res = solve_exact_classical(qp)
    relaxed_probs = solve_continuous_relaxation(qp)
    
    print(f"Exact Classical Energy: {exact_res.fval}")
    print(f"Exact Classical Solution: {exact_res.x[:10]}")
    
    # 4. Grid Search Definitions
    depths = [1, 2] # Keep it shallow for local testing
    seeds = [42, 1337]
    ansatz_types = ["xy_mixer"]
    
    results_log = []
    
    # 5. Execution Loop
    for atype in ansatz_types:
        for p in depths:
            for seed in seeds:
                print(f"\n--- Running: {atype} | p={p} | seed={seed} ---")
                
                # Build Ansatz
                if atype == "standard":
                    ansatz = build_standard_qaoa(ising_op, p_depth=p)
                elif atype == "warm_start":
                    ansatz = build_warm_started_qaoa(ising_op, relaxed_probs, p_depth=p)
                elif atype == "xy_mixer":
                    ansatz = build_xy_qaoa(ising_op, p_depth=p, use_dicke=True) 
                    
                # Initialize random parameters (Beta and Gamma angles)
                np.random.seed(seed)
                initial_params = np.random.uniform(-np.pi, np.pi, ansatz.num_parameters)
                
                # Create objective and optimize
                obj_func = create_objective_function(ansatz, ising_op)
                opt_params, final_energy = optimize_circuit(obj_func, initial_params, method='COBYLA')
                
                # Sample the final optimized circuit to get the best bitstrings
                bound_circuit = ansatz.assign_parameters(opt_params)
                bound_circuit.measure_all()

                # Transpile the bound circuit for the Aer Sampler
                backend = AerSimulator()
                transpiled_bound_circuit = transpile(bound_circuit, backend=backend, optimization_level=1)
                
                sampler = AerSampler()
                job = sampler.run([(transpiled_bound_circuit,)])
                sampler_res = job.result()[0]
                
                # Extract the most probable bitstring
                counts = sampler_res.data.meas.get_counts()
                best_bitstring_str = max(counts, key=counts.get)
                # Reverse bitstring because Qiskit uses little-endian ordering
                best_bitstring = [int(b) for b in best_bitstring_str[::-1]] 
                
                # Evaluate financially
                metrics = evaluate_portfolio(best_bitstring, returns, covariance, tickers, sector_indices)
                
                # Log
                results_log.append({
                    "ansatz": atype,
                    "depth": p,
                    "seed": seed,
                    "final_energy": final_energy + offset,
                    "is_valid": metrics["valid"],
                    "return_pct": metrics["return_pct"],
                    "volatility_pct": metrics["volatility_pct"],
                    "sharpe": metrics["sharpe_ratio"],
                    "tickers": metrics["selected_tickers"]
                })
                
                print(f"Result: Valid={metrics['valid']} | Sharpe={metrics['sharpe_ratio']:.3f} | {metrics['selected_tickers']}")

    # 6. Save results
    df_results = pd.DataFrame(results_log)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    df_results.to_csv(f"results/logs/grid_search_results_{timestamp}.csv", index=False)
    print(f"\nGrid search complete. Saved to results/logs/grid_search_results_{timestamp}.csv") 

if __name__ == "__main__":
    run_grid_search()