import os
import glob
import ast
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

SUPPORTED_DATASETS = ("qest", "nasdaq_baltic", "nyse")


def _dataset_paths(data_dir, dataset):
    stock_path = os.path.join(data_dir, f"{dataset}_stock_data.csv")
    corr_path = os.path.join(data_dir, f"{dataset}_correlation_2021_2024.csv")
    missing = [path for path in (stock_path, corr_path) if not os.path.exists(path)]
    if missing:
        raise FileNotFoundError(
            f"Missing data file(s): {', '.join(missing)}. "
            f"Supported datasets: {', '.join(SUPPORTED_DATASETS)} "
            f"(looked in {data_dir})."
        )
    return stock_path, corr_path


def generate_all_plots(csv_path=None, output_dir="results/visualisations"):
    # 1. Setup output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. Auto-detect the latest results CSV if not provided
    if csv_path is None:
        list_of_files = glob.glob('results/logs/*.csv')
        if not list_of_files:
            list_of_files = glob.glob('*.csv') # Fallback to root directory
            if not list_of_files:
                raise FileNotFoundError("No CSV files found in results/logs/ or the root directory.")
        csv_path = max(list_of_files, key=os.path.getctime)
        
    print(f"Loading data from: {csv_path}")
    df = pd.read_csv(csv_path)
    
    # 3. Create a clean label for each run
    if 'philosophy' in df.columns:
        df['Run_ID'] = df['philosophy'] + ' (D' + df['depth'].astype(str) + ' S' + df['seed'].astype(str) + ')'
    else:
        df['Run_ID'] = 'D' + df['depth'].astype(str) + ' S' + df['seed'].astype(str)
        
    sns.set_theme(style="whitegrid")

    # --- Plot 1: Risk vs Return ---
    plt.figure(figsize=(10, 8))
    sns.scatterplot(data=df, x='volatility_pct', y='return_pct', hue='Run_ID', s=300, palette='deep')
    plt.title('Risk vs Return (Financial Performance)', fontsize=14)
    plt.xlabel('Volatility / Risk (%)', fontsize=12)
    plt.ylabel('Expected Return (%)', fontsize=12)
    plt.axhline(0, color='black', linewidth=1, linestyle='--')
    plt.legend(title='Run Config', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '01_risk_vs_return.png'), dpi=300)
    plt.close()
    
    # --- Plot 2: QAOA Final Energy ---
    plt.figure(figsize=(10, 8))
    sns.barplot(data=df, x='Run_ID', y='final_energy', hue='Run_ID', palette='coolwarm', legend=False)
    plt.title('QAOA Final Energy (Lower is Better)', fontsize=14)
    plt.xlabel('Run Configuration', fontsize=12)
    plt.ylabel('Hamiltonian Energy', fontsize=12)
    plt.axhline(-0.16788, color='green', linestyle='--', label='Classical Exact (-0.167)')
    plt.xticks(rotation=45, ha='right')
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '02_qaoa_energy.png'), dpi=300)
    plt.close()
    
    # --- Plot 3: Sharpe Ratio ---
    plt.figure(figsize=(10, 8))
    sns.barplot(data=df, x='Run_ID', y='sharpe', hue='Run_ID', palette='viridis', legend=False)
    plt.title('Sharpe Ratio (Higher is Better)', fontsize=14)
    plt.xlabel('Run Configuration', fontsize=12)
    plt.ylabel('Sharpe Ratio', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '03_sharpe_ratio.png'), dpi=300)
    plt.close()
    
    # --- Plot 4: Ticker Selection Frequency ---
    plt.figure(figsize=(10, 8))
    all_tickers = df['tickers'].apply(ast.literal_eval).explode()
    
    try:
        sns.countplot(y=all_tickers, order=all_tickers.value_counts().index, hue=all_tickers, palette='magma', legend=False)
    except Exception:
        sns.countplot(y=all_tickers, order=all_tickers.value_counts().index, palette='magma')
        
    plt.title('Most Frequently Selected Assets', fontsize=14)
    plt.xlabel('Selection Count', fontsize=12)
    plt.ylabel('Stock Ticker', fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '04_ticker_frequency.png'), dpi=300)
    plt.close()

    print(f"Successfully saved 4 high-res visualization plots to ./{output_dir}/")


def plot_qaoa_landscape(grid_points=20, risk_factor=2.0, data_dir="data/raw",
                        output_dir="results/visualisations", backend=None, estimator=None,
                        dataset="qest", allow_large=False):
    """
    Renders the p=1 QAOA energy landscape over the (beta, gamma) parameter grid.

    Args:
        grid_points (int): Resolution per axis; evaluates grid_points**2 circuits.
        risk_factor (float): Alpha weighting risk vs return in the Hamiltonian.
        data_dir (str): Directory containing the raw stock/correlation CSVs.
        output_dir (str): Directory to write the PNG into.
        backend, estimator: Optional pre-built Qiskit primitives (created if None).
        dataset (str): Name of the dataset to load (qest, nasdaq_baltic, nyse).
        allow_large (bool): Allow datasets with more than 12 assets, for which
            statevector simulation is impractical.

    Returns:
        str: Path to the saved PNG.
    """
    import numpy as np
    from qiskit import transpile
    from qiskit_aer import AerSimulator
    from qiskit_aer.primitives import EstimatorV2 as AerEstimator
    from src.data.loader import PortfolioData
    from src.problem.qubo_builder import build_manual_hamiltonian
    from src.quantum.ansatzes import build_xy_qaoa

    if grid_points < 2:
        raise ValueError("grid_points must be >= 2")

    os.makedirs(output_dir, exist_ok=True)

    print("Loading data & building Hamiltonian...")
    stock_path, corr_path = _dataset_paths(data_dir, dataset)
    data = PortfolioData(stock_path, corr_path)
    if data.n_assets > 12 and not allow_large:
        raise ValueError(
            f"Dataset '{dataset}' has {data.n_assets} assets; statevector "
            "simulation grows as 2^n and would be impractical. "
            "Pass allow_large=True to override."
        )
    returns, covariance, sector_indices, _ = data.get_formulation_data()

    ising_op = build_manual_hamiltonian(returns, covariance, sector_indices, risk_factor=risk_factor)
    ansatz = build_xy_qaoa(ising_op, p_depth=1, use_dicke=True)
    if ansatz.num_parameters != 2:
        raise ValueError(f"Expected a p=1 ansatz with 2 parameters, got {ansatz.num_parameters}")

    if backend is None:
        backend = AerSimulator()
    if estimator is None:
        estimator = AerEstimator()
    transpiled_ansatz = transpile(ansatz, backend=backend, optimization_level=1)

    beta_range = np.linspace(-np.pi, np.pi, grid_points)
    gamma_range = np.linspace(-np.pi, np.pi, grid_points)
    B, G = np.meshgrid(beta_range, gamma_range)
    Z = np.zeros_like(B)

    print(f"Evaluating {grid_points ** 2} quantum circuits. This may take a minute...")
    for i in range(grid_points):
        for j in range(grid_points):
            params = [B[i, j], G[i, j]]
            job = estimator.run(pubs=[(transpiled_ansatz, ising_op, params)])
            Z[i, j] = job.result()[0].data.evs

    print("Plotting 3D landscape...")
    with plt.style.context('dark_background'):
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')
        surf = ax.plot_surface(B, G, Z, cmap='magma', edgecolor='none', alpha=0.9)
        fig.colorbar(surf, shrink=0.5, aspect=10, pad=0.1, label='Energy (Cost)')
        ax.set_title('QAOA Energy Landscape (Depth 1)\nCoop Pank Portfolio Optimization',
                     fontsize=16, pad=20)
        ax.set_xlabel(r'Beta ($\beta$)', fontsize=12)
        ax.set_ylabel(r'Gamma ($\gamma$)', fontsize=12)
        ax.set_zlabel('Hamiltonian Energy', fontsize=12)
        ax.view_init(elev=30, azim=45)
        plt.tight_layout()
        out_path = os.path.join(output_dir, 'qaoa_3d_landscape.png')
        plt.savefig(out_path, dpi=300)
        plt.close(fig)
    print(f"Saved to {out_path}")
    return out_path


def plot_correlation_network(threshold=0.3, data_dir="data/raw",
                             output_dir="results/visualisations", dataset="qest"):
    """
    Renders the asset correlation network, with nodes colored by sector.

    Edges are drawn for |correlation| > threshold and weighted by its magnitude.
    Sector membership is derived from the data (not hardcoded).

    Args:
        threshold (float): Minimum absolute correlation to draw an edge.
        data_dir (str): Directory containing the raw stock/correlation CSVs.
        output_dir (str): Directory to write the PNG into.
        dataset (str): Name of the dataset to load (qest, nasdaq_baltic, nyse).

    Returns:
        str: Path to the saved PNG.
    """
    import networkx as nx
    import matplotlib.patches as mpatches
    from src.data.loader import PortfolioData

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")

    os.makedirs(output_dir, exist_ok=True)

    stock_path, corr_path = _dataset_paths(data_dir, dataset)
    data = PortfolioData(stock_path, corr_path)
    tickers = data.tickers
    df_corr = data.df_corr

    node_sector = {}
    for sector, idxs in data.sector_indices.items():
        for i in idxs:
            node_sector[tickers[i]] = sector

    palette = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#c2c2f0', '#ffb3e6']
    sector_color = {s: palette[k % len(palette)] for k, s in enumerate(data.sector_indices)}

    G = nx.Graph()
    G.add_nodes_from(tickers)
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            t1, t2 = tickers[i], tickers[j]
            corr = float(df_corr.loc[t1, t2])
            if abs(corr) > threshold:
                G.add_edge(t1, t2, weight=abs(corr))

    node_colors = [sector_color.get(node_sector.get(n), '#cccccc') for n in G.nodes()]

    print(f"Correlation network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges "
          f"(|corr| > {threshold})")
    with plt.style.context('dark_background'):
        fig = plt.figure(figsize=(12, 10))
        pos = nx.spring_layout(G, k=0.5, seed=42)
        edges = G.edges()
        weights = [G[u][v]['weight'] * 4 for u, v in edges]

        nx.draw_networkx_nodes(G, pos, node_size=3000, node_color=node_colors,
                               edgecolors='white', linewidths=2)
        nx.draw_networkx_edges(G, pos, edgelist=edges, width=weights,
                               edge_color='gray', alpha=0.7)
        nx.draw_networkx_labels(G, pos, font_size=10, font_family='sans-serif',
                                font_color='black', font_weight='bold')

        plt.title('Baltic Market Correlation Network\n(Thicker lines = Higher Correlation)',
                  fontsize=18, pad=20)
        plt.axis('off')

        sectors_present = [s for s in data.sector_indices
                           if any(node_sector.get(n) == s for n in G.nodes())]
        handles = [mpatches.Patch(color=sector_color[s], label=s) for s in sectors_present]
        plt.legend(handles=handles, loc='upper left', fontsize=12)

        plt.tight_layout()
        out_path = os.path.join(output_dir, 'market_correlation_network.png')
        plt.savefig(out_path, dpi=300)
        plt.close(fig)
    print(f"Saved to {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate QAOA result and market visualizations.")
    parser.add_argument("--file", type=str, default=None,
                        help="Path to a specific results CSV to visualize.")
    parser.add_argument("--landscape", action="store_true",
                        help="Generate the 3D QAOA energy landscape (slow: grid_points^2 circuits).")
    parser.add_argument("--network", action="store_true",
                        help="Generate the market correlation network.")
    parser.add_argument("--grid-points", type=int, default=20,
                        help="Landscape resolution per axis (default: 20).")
    parser.add_argument("--threshold", type=float, default=0.3,
                        help="Minimum |correlation| for network edges (default: 0.3).")
    parser.add_argument("--data-dir", type=str, default="data/raw",
                        help="Directory containing the raw data CSVs.")
    parser.add_argument("--dataset", type=str, default="qest",
                        choices=SUPPORTED_DATASETS,
                        help="Dataset to load from --data-dir (default: qest).")
    parser.add_argument("--output-dir", type=str, default="results/visualisations",
                        help="Directory to write PNGs into.")
    args = parser.parse_args()

    ran = False
    if args.landscape:
        plot_qaoa_landscape(grid_points=args.grid_points, data_dir=args.data_dir,
                            output_dir=args.output_dir, dataset=args.dataset)
        ran = True
    if args.network:
        plot_correlation_network(threshold=args.threshold, data_dir=args.data_dir,
                                 output_dir=args.output_dir, dataset=args.dataset)
        ran = True
    if not ran:
        generate_all_plots(csv_path=args.file, output_dir=args.output_dir)