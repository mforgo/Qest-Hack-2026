import os

import matplotlib

matplotlib.use("Agg")  # headless-safe: avoid Tk backend shutdown crashes

import pandas as pd

from . import data_plots, quantum_plots, results_plots


def generate_report(data_dir="data/raw", output_dir="results/visualisations",
                    results_csv=None, do_data=True, do_results=True, do_quantum=True,
                    include_network=True, include_landscape=False,
                    grid_points=20, maxiter=60):
    """
    Generate the extended visualization suite.

    Args:
        data_dir: Directory with the raw stock/correlation CSVs.
        output_dir: Directory to write PNGs into.
        results_csv: Explicit results CSV; if None the richest log is auto-selected.
        do_data: Include data-level plots (heatmaps, frontier, contributions).
        do_results: Include results-level plots (depth curves, selection heatmap, ...).
        do_quantum: Include circuit diagram and sampled bitstring distribution.
        include_network: Include the correlation network (from visualize_results).
        include_landscape: Include the heavy 3D QAOA landscape.
        grid_points: Landscape resolution per axis.
        maxiter: COBYLA iterations for the sampled-distribution plot.

    Returns:
        list[str]: Paths of the generated PNGs.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = []

    data = None
    if do_data or do_quantum or include_network or include_landscape:
        data = data_plots.load_portfolio_data(data_dir)

    resolved_csv = results_plots.resolve_results_csv(results_csv) if (do_data or do_results) else None

    if do_data:
        for fn in (data_plots.plot_correlation_heatmap,
                   data_plots.plot_covariance_heatmap,
                   data_plots.plot_asset_risk_return,
                   data_plots.plot_sector_exposure):
            paths.append(fn(data, output_dir))
        paths.append(data_plots.plot_portfolio_frontier(
            data, output_dir, results_csv=resolved_csv))
        paths.append(data_plots.plot_risk_return_contribution(data, output_dir))

    if do_results:
        if resolved_csv:
            print(f"Using results CSV: {resolved_csv}")
            df = results_plots.prepare_results_df(pd.read_csv(resolved_csv))
            paths.extend(results_plots.generate_results_plots(df, output_dir))
        else:
            print("No results CSV found; skipping results plots.")

    if do_quantum:
        paths.append(quantum_plots.plot_ansatz_circuit(data, output_dir))
        paths.append(quantum_plots.plot_sampled_distribution(
            data, output_dir, maxiter=maxiter))

    if include_network:
        from src.pipeline.visualize_results import plot_correlation_network
        paths.append(plot_correlation_network(data_dir=data_dir, output_dir=output_dir))

    if include_landscape:
        from src.pipeline.visualize_results import plot_qaoa_landscape
        paths.append(plot_qaoa_landscape(grid_points=grid_points, data_dir=data_dir,
                                         output_dir=output_dir))

    print(f"\nGenerated {len(paths)} visualizations in {output_dir}")
    return paths
