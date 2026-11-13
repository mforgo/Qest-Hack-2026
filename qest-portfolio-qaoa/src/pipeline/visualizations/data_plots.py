import itertools
import os

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from src.data.constraints import DEFAULT_CONSTRAINTS
from src.data.loader import PortfolioData

from ._common import save_figure


def load_portfolio_data(data_dir="data/raw"):
    return PortfolioData(
        os.path.join(data_dir, "qest_stock_data.csv"),
        os.path.join(data_dir, "qest_correlation_2021_2024.csv"),
    )


def portfolio_metrics(indices, returns, covariance):
    """Equal-weight metrics for a set of asset indices."""
    indices = list(indices)
    if not indices:
        return 0.0, 0.0, 0.0
    weights = np.zeros(len(returns))
    weights[indices] = 1.0 / len(indices)
    ret = float(weights @ returns)
    vol = float(np.sqrt(max(weights @ covariance @ weights, 0.0)))
    sharpe = ret / vol if vol > 0 else 0.0
    return ret, vol, sharpe


def enumerate_valid_portfolios(returns, covariance, sector_indices,
                               constraints=DEFAULT_CONSTRAINTS):
    """All feasible equal-weight portfolios (exact-k + per-sector cap)."""
    rows = []
    for combo in itertools.combinations(range(len(returns)), constraints.num_to_select):
        ok, _ = constraints.is_valid(combo, sector_indices)
        if not ok:
            continue
        ret, vol, sharpe = portfolio_metrics(combo, returns, covariance)
        rows.append({"indices": combo, "return": ret, "vol": vol, "sharpe": sharpe})
    return rows


def plot_correlation_heatmap(data, output_dir):
    corr = data.df_corr.loc[data.tickers, data.tickers]
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0,
                vmin=-1, vmax=1, square=True, linewidths=0.5, ax=ax)
    ax.set_title("Asset Correlation Matrix (2021-2024)", fontsize=14)
    return save_figure(fig, output_dir, "05_correlation_heatmap.png")


def plot_covariance_heatmap(data, output_dir):
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(data.covariance, xticklabels=data.tickers, yticklabels=data.tickers,
                cmap="viridis", square=True, ax=ax)
    ax.set_title("Asset Covariance Matrix (annualized)", fontsize=14)
    return save_figure(fig, output_dir, "06_covariance_heatmap.png")


def plot_asset_risk_return(data, output_dir):
    sectors = list(data.sector_indices)
    palette = dict(zip(sectors, sns.color_palette("deep", len(sectors))))
    fig, ax = plt.subplots(figsize=(10, 8))
    for sector, idxs in data.sector_indices.items():
        ax.scatter(data.volatilities[idxs] * 100, data.returns[idxs] * 100,
                   s=220, color=palette[sector], edgecolor="white",
                   linewidths=1.5, label=sector, zorder=3)
    for i, ticker in enumerate(data.tickers):
        ax.annotate(ticker, (data.volatilities[i] * 100, data.returns[i] * 100),
                    xytext=(6, 6), textcoords="offset points", fontsize=9)
    ew_ret, ew_vol, _ = portfolio_metrics(range(len(data.tickers)),
                                          data.returns, data.covariance)
    ax.scatter(ew_vol * 100, ew_ret * 100, marker="*", s=450, color="black",
               edgecolor="white", label="Equal-weight (all 10)", zorder=4)
    ax.set_xlabel("Volatility / Risk (%)", fontsize=12)
    ax.set_ylabel("Expected Return (%)", fontsize=12)
    ax.set_title("Individual Assets: Risk vs Return", fontsize=14)
    ax.legend()
    ax.grid(alpha=0.3)
    return save_figure(fig, output_dir, "07_asset_risk_return.png")


def plot_sector_exposure(data, output_dir):
    counts = {sector: len(idxs) for sector, idxs in data.sector_indices.items()}
    limit = DEFAULT_CONSTRAINTS.max_per_sector
    colors = ["#d62728" if c > limit else "#1f77b4" for c in counts.values()]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(list(counts.keys()), list(counts.values()), color=colors)
    ax.axhline(limit, color="black", linestyle="--",
               label=f"Max selectable per sector = {limit}")
    for i, count in enumerate(counts.values()):
        ax.text(i, count + 0.05, str(count), ha="center", fontsize=11)
    binding = [s for s, c in counts.items() if c > limit]
    ax.set_title("Sector Sizes (red = binding constraint: must drop >= 1)", fontsize=14)
    ax.set_ylabel("Number of stocks")
    ax.legend()
    print(f"Binding sectors: {binding}")
    return save_figure(fig, output_dir, "08_sector_exposure.png")


def plot_portfolio_frontier(data, output_dir, results_csv=None, risk_factor=2.0):
    rows = enumerate_valid_portfolios(data.returns, data.covariance, data.sector_indices)
    rets = np.array([r["return"] for r in rows]) * 100
    vols = np.array([r["vol"] for r in rows]) * 100
    sharpes = np.array([r["sharpe"] for r in rows])

    fig, ax = plt.subplots(figsize=(11, 8))
    sc = ax.scatter(vols, rets, c=sharpes, cmap="viridis", s=70, alpha=0.85,
                    edgecolor="white", linewidths=0.5,
                    label=f"Valid portfolios ({len(rows)})")
    fig.colorbar(sc, ax=ax, label="Sharpe ratio")

    def highlight(idx, marker, label, color):
        ax.scatter(vols[idx], rets[idx], marker=marker, s=420, color=color,
                   edgecolor="black", linewidths=1.5, label=label, zorder=5)

    highlight(int(np.argmax(sharpes)), "*", "Max Sharpe", "gold")
    highlight(int(np.argmin(vols)), "D", "Min risk", "tab:blue")
    highlight(int(np.argmax(rets)), "s", "Max return", "tab:green")

    try:
        from src.problem.classical_solver import solve_exact_classical
        from src.problem.qubo_builder import build_portfolio_optimization_problem
        qp = build_portfolio_optimization_problem(
            data.returns, data.covariance, data.sector_indices, risk_factor=risk_factor)
        result = solve_exact_classical(qp)
        bits = np.round(result.x).astype(int)
        selected = np.where(bits == 1)[0]
        c_ret, c_vol, _ = portfolio_metrics(selected, data.returns, data.covariance)
        ax.scatter(c_vol * 100, c_ret * 100, marker="P", s=420, color="red",
                   edgecolor="black", linewidths=1.5,
                   label="Classical QP optimum", zorder=6)
        print(f"Classical optimum: {[data.tickers[i] for i in selected]} "
              f"(return {c_ret * 100:.2f}%, vol {c_vol * 100:.2f}%)")
    except Exception as exc:  # keep the plot even if the solver is unavailable
        print(f"Skipping classical optimum overlay: {exc}")

    if results_csv:
        import pandas as pd
        df = pd.read_csv(results_csv)
        if {"return_pct", "volatility_pct"}.issubset(df.columns):
            ax.scatter(df["volatility_pct"], df["return_pct"], marker="x", s=120,
                       color="black", label="QAOA runs", zorder=7)

    ax.set_xlabel("Volatility / Risk (%)", fontsize=12)
    ax.set_ylabel("Expected Return (%)", fontsize=12)
    ax.set_title("Feasible Portfolio Universe (select 5, max 2 per sector)", fontsize=14)
    ax.legend(loc="best")
    ax.grid(alpha=0.3)
    return save_figure(fig, output_dir, "09_portfolio_frontier.png")


def plot_risk_return_contribution(data, output_dir):
    rows = enumerate_valid_portfolios(data.returns, data.covariance, data.sector_indices)
    best = max(rows, key=lambda r: r["sharpe"])
    indices = list(best["indices"])
    weights = np.zeros(len(data.tickers))
    weights[indices] = 1.0 / len(indices)

    port_vol = float(np.sqrt(max(weights @ data.covariance @ weights, 0.0)))
    return_contrib = weights * data.returns * 100
    if port_vol > 0:
        risk_contrib = weights * (data.covariance @ weights) / port_vol * 100
    else:
        risk_contrib = np.zeros_like(weights)

    order = np.argsort(return_contrib)[::-1]
    labels = [data.tickers[i] for i in order]

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    axes[0].bar(labels, return_contrib[order], color="#2ca02c")
    axes[0].set_title("Return Contribution (max-Sharpe portfolio)", fontsize=13)
    axes[0].set_ylabel("Contribution to portfolio return (%)")
    axes[1].bar(labels, risk_contrib[order], color="#d62728")
    axes[1].set_title("Risk Contribution (max-Sharpe portfolio)", fontsize=13)
    axes[1].set_ylabel("Contribution to portfolio volatility (%)")
    for ax in axes:
        ax.tick_params(axis="x", rotation=45)
        ax.grid(axis="y", alpha=0.3)
    return save_figure(fig, output_dir, "10_risk_return_contribution.png")
