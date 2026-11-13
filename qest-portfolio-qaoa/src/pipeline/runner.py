import argparse
import os

import numpy as np
import pandas as pd
from src.data.loader import PortfolioData
from src.problem.classical_solver import solve_exact_classical, solve_continuous_relaxation
from src.quantum.ansatzes import build_standard_qaoa, build_warm_started_qaoa, build_xy_qaoa
from src.quantum.execution import create_objective_function, optimize_circuit
from src.pipeline.evaluator import evaluate_portfolio
from src.problem.qubo_builder import (
    build_portfolio_optimization_problem,
    build_manual_hamiltonian
)
from qiskit_aer.primitives import SamplerV2 as AerSampler, EstimatorV2 as AerEstimator
import warnings
from scipy.sparse import SparseEfficiencyWarning
from qiskit import transpile
from qiskit_aer import AerSimulator


ALL_PHILOSOPHIES = {
    "Gambling": 0.0,
    "Neutral": 2.0,
    "Safe": 5.0,
}


def run_grid_search(philosophies=None, depths=None, seeds=None,
                    ansatz_types=None, maxiter=1000, output_dir="results/logs",
                    data_dir="data/raw", dataset="qest", allow_large_dataset=False):
    #Hide SciPy sparse matrix conversion warnings during local simulation
    warnings.simplefilter('ignore', SparseEfficiencyWarning)

    # 1. Investor philosophies (alpha/risk_factor) and grid definitions
    if philosophies is None:
        philosophies = {"Neutral": 2.0}
    if depths is None:
        depths = list(range(1, 6))
    if seeds is None:
        seeds = [42]
    if ansatz_types is None:
        ansatz_types = ["xy_mixer"]

    os.makedirs(output_dir, exist_ok=True)

    print("Loading data...")
    data = PortfolioData(
        os.path.join(data_dir, f"{dataset}_stock_data.csv"),
        os.path.join(data_dir, f"{dataset}_correlation_2021_2024.csv"),
    )
    if data.n_assets > 24 and not allow_large_dataset:
        raise ValueError(
            f"Dataset '{dataset}' has {data.n_assets} assets. The simulator grid "
            "search relies on exact diagonalization and Aer statevector simulation, "
            "whose cost grows as 2^n with the number of qubits, so it is limited to "
            "24 assets. Use --dataset qest, select a smaller subset, run the hardware "
            "runner for larger universes, or pass --allow-large-dataset to override."
        )

    returns, covariance, sector_indices, tickers = data.get_formulation_data()

    print(f"Grid: philosophies={list(philosophies)}, depths={depths}, "
          f"seeds={seeds}, ansatz={ansatz_types}, maxiter={maxiter}")
    print(f"Data: {dataset}, {data.n_assets} assets, {data.n_assets} qubits")

    results_log = []

    # Create Aer backend and primitives once for the whole grid search
    backend = AerSimulator()
    sampler = AerSampler()
    estimator = AerEstimator()

    # 2. Main loop over philosophies
    for phil_name, alpha in philosophies.items():
        print(f"\n==================================================")
        print(f"   Executing Philosophy: {phil_name} (Alpha = {alpha})")
        print(f"==================================================")

        # Build Formulations with the current alpha
        qp = build_portfolio_optimization_problem(returns, covariance, sector_indices, risk_factor=alpha)
        
        ising_op = build_manual_hamiltonian(
            returns, 
            covariance, 
            sector_indices=sector_indices,
            risk_factor=alpha, 
            penalty_weight=10.0,
        ) 
        
        offset = 0.0
        
        # 3. Classical Baselines
        print(f"Computing classical baselines for {phil_name}...")
        exact_res = solve_exact_classical(qp)
        relaxed_probs = solve_continuous_relaxation(qp)
        
        # Extract the classical optimal tickers
        num_assets = len(tickers)
        # Using > 0.5 instead of == 1 to avoid floating point precision issues
        classical_indices = np.where(np.array(exact_res.x[:num_assets]) > 0.5)[0] 
        classical_tickers = [tickers[i] for i in classical_indices]
        
        print(f"Exact Classical Energy: {exact_res.fval}")
        print(f"Exact Classical Solution: {exact_res.x[:num_assets]}")
        print(f"Exact Classical Tickers: {classical_tickers}")
        
        # 3. Standard Execution Loop
        for atype in ansatz_types:
            for p in depths:
                if atype == "standard":
                    ansatz = build_standard_qaoa(ising_op, p_depth=p)
                elif atype == "warm_start":
                    ansatz = build_warm_started_qaoa(ising_op, relaxed_probs, p_depth=p)
                elif atype == "xy_mixer":
                    ansatz = build_xy_qaoa(ising_op, p_depth=p, use_dicke=True)
                else:
                    raise ValueError(f"Unknown ansatz type: {atype}")

                objective = create_objective_function(ansatz, ising_op, estimator=estimator, backend=backend)

                measured = ansatz.copy()
                measured.measure_all()
                transpiled_measured = transpile(measured, backend=backend, optimization_level=1)

                for seed in seeds:
                    print(f"\n--- Running: {atype} | p={p} | seed={seed} ---")

                    np.random.seed(seed)
                    initial_params = np.random.uniform(-np.pi, np.pi, ansatz.num_parameters)

                    opt_params, final_energy = optimize_circuit(
                        objective, initial_params, method='COBYLA', maxiter=maxiter
                    )

                    param_bind = dict(zip(ansatz.parameters, opt_params))
                    bound_circuit = transpiled_measured.assign_parameters(param_bind)

                    job = sampler.run([(bound_circuit,)])
                    sampler_res = job.result()[0]

                    counts = sampler_res.data.meas.get_counts()
                    best_bitstring_str = max(counts, key=counts.get)
                    best_bitstring = [int(b) for b in best_bitstring_str[::-1]]

                    metrics = evaluate_portfolio(best_bitstring, returns, covariance, tickers, sector_indices)

                    results_log.append({
                        "dataset": dataset,
                        "num_assets": data.n_assets,
                        "philosophy": phil_name,
                        "alpha": alpha,
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

    # 4. Save aggregated results
    df_results = pd.DataFrame(results_log)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"philosophy_search_results_{timestamp}.csv")
    df_results.to_csv(filepath, index=False)
    print(f"\nSearch complete. Saved to {filepath}") 

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the QAOA portfolio grid search on the Aer simulator."
    )
    parser.add_argument("--full", action="store_true",
                        help="All philosophies, depths 1-5, seeds 42/123/999.")
    parser.add_argument("--quick", action="store_true",
                        help="Neutral only, depths 1-5, seed 42 (default).")
    parser.add_argument("--philosophies", nargs="+", choices=list(ALL_PHILOSOPHIES),
                        help="Subset of philosophies to run.")
    parser.add_argument("--depths", nargs="+", type=int,
                        help="QAOA depths to run (default: 1 2 3 4 5).")
    parser.add_argument("--seeds", nargs="+", type=int,
                        help="Random seeds (default: 42).")
    parser.add_argument("--ansatz", nargs="+",
                        choices=["standard", "warm_start", "xy_mixer"],
                        help="Ansatz types to run (default: xy_mixer).")
    parser.add_argument("--maxiter", type=int, default=1000,
                        help="COBYLA max iterations per run (default: 1000).")
    parser.add_argument("--output-dir", default="results/logs",
                        help="Directory for the results CSV.")
    parser.add_argument("--data-dir", default="data/raw",
                        help="Directory containing the stock and correlation CSVs.")
    parser.add_argument("--dataset", default="qest",
                        choices=["qest", "nasdaq_baltic", "nyse"],
                        help="Dataset name used to resolve <dataset>_*.csv (default: qest).")
    parser.add_argument("--allow-large-dataset", action="store_true",
                        help="Bypass the >24 asset simulator safety limit.")
    args = parser.parse_args(argv)

    if args.full and args.quick:
        parser.error("--full and --quick are mutually exclusive")

    if args.full:
        philosophies = dict(ALL_PHILOSOPHIES)
        depths = [1, 2, 3, 4, 5]
        seeds = [42, 123, 999]
        ansatz_types = ["xy_mixer"]
    else:
        selected = args.philosophies or ["Neutral"]
        philosophies = {name: ALL_PHILOSOPHIES[name] for name in selected}
        depths = args.depths or [1, 2, 3, 4, 5]
        seeds = args.seeds or [42]
        ansatz_types = args.ansatz or ["xy_mixer"]

    run_grid_search(
        philosophies=philosophies,
        depths=depths,
        seeds=seeds,
        ansatz_types=ansatz_types,
        maxiter=args.maxiter,
        output_dir=args.output_dir,
        data_dir=args.data_dir,
        dataset=args.dataset,
        allow_large_dataset=args.allow_large_dataset,
    )


if __name__ == "__main__":
    main()