import ast
import glob

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from ._common import save_figure


def resolve_results_csv(csv_path=None):
    """Use an explicit CSV, else the richest (most rows) results log."""
    if csv_path:
        return csv_path
    files = glob.glob("results/logs/*.csv") or glob.glob("*.csv")
    if not files:
        return None
    return max(files, key=lambda f: len(pd.read_csv(f)))


def prepare_results_df(df):
    df = df.copy()
    if "is_valid" in df.columns:
        df["valid"] = df["is_valid"].astype(str).str.lower().eq("true")
    if "philosophy" in df.columns:
        df["run_group"] = df["philosophy"].astype(str)
    elif "ansatz" in df.columns:
        df["run_group"] = df["ansatz"].astype(str)
    else:
        df["run_group"] = "run"
    return df


def plot_depth_vs_energy(df, output_dir):
    if not {"depth", "final_energy"}.issubset(df.columns):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.lineplot(data=df, x="depth", y="final_energy", hue="run_group",
                 marker="o", errorbar="sd", ax=ax)
    ax.set_title("QAOA Final Energy vs Circuit Depth (lower is better)", fontsize=14)
    ax.set_xlabel("Circuit depth p")
    ax.set_ylabel("Final energy")
    ax.grid(alpha=0.3)
    return save_figure(fig, output_dir, "11_depth_vs_energy.png")


def plot_depth_vs_valid_rate(df, output_dir):
    if not {"depth", "valid"}.issubset(df.columns):
        return None
    rate = df.groupby(["depth", "run_group"], as_index=False)["valid"].mean()
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=rate, x="depth", y="valid", hue="run_group", ax=ax)
    ax.set_ylim(0, 1.05)
    ax.set_title("Constraint Satisfaction Rate vs Depth", fontsize=14)
    ax.set_xlabel("Circuit depth p")
    ax.set_ylabel("Fraction of valid portfolios")
    ax.grid(axis="y", alpha=0.3)
    return save_figure(fig, output_dir, "12_depth_vs_valid_rate.png")


def plot_depth_vs_sharpe(df, output_dir):
    if not {"depth", "sharpe"}.issubset(df.columns):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.lineplot(data=df, x="depth", y="sharpe", hue="run_group",
                 marker="o", errorbar="sd", ax=ax)
    ax.set_title("Sharpe Ratio vs Circuit Depth (higher is better)", fontsize=14)
    ax.set_xlabel("Circuit depth p")
    ax.set_ylabel("Sharpe ratio")
    ax.grid(alpha=0.3)
    return save_figure(fig, output_dir, "13_depth_vs_sharpe.png")


def plot_ticker_selection_heatmap(df, output_dir):
    if not {"tickers", "depth"}.issubset(df.columns):
        return None
    exploded = df.assign(tickers=df["tickers"].apply(ast.literal_eval)).explode("tickers")
    pivot = exploded.groupby(["tickers", "depth"]).size().unstack(fill_value=0)
    pivot = pivot.reindex(pivot.sum(axis=1).sort_values(ascending=False).index)
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.heatmap(pivot, annot=True, fmt="d", cmap="magma", linewidths=0.5, ax=ax)
    ax.set_title("Ticker Selection Frequency by Depth", fontsize=14)
    ax.set_xlabel("Circuit depth p")
    ax.set_ylabel("Ticker")
    return save_figure(fig, output_dir, "14_ticker_selection_heatmap.png")


def plot_energy_vs_sharpe(df, output_dir):
    if not {"final_energy", "sharpe"}.issubset(df.columns):
        return None
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.scatterplot(data=df, x="final_energy", y="sharpe", hue="valid",
                    style="run_group", s=160, ax=ax)
    ax.set_title("Energy vs Sharpe Ratio (valid runs should sit top-left)", fontsize=14)
    ax.set_xlabel("Final energy (lower is better)")
    ax.set_ylabel("Sharpe ratio (higher is better)")
    ax.grid(alpha=0.3)
    return save_figure(fig, output_dir, "15_energy_vs_sharpe.png")


def plot_philosophy_comparison(df, output_dir):
    if "philosophy" not in df.columns:
        return None
    available = [("return_pct", "Return (%)"), ("sharpe", "Sharpe ratio"),
                 ("final_energy", "Final energy")]
    metrics = [(c, label) for c, label in available if c in df.columns]
    if not metrics:
        return None
    fig, axes = plt.subplots(1, len(metrics), figsize=(6 * len(metrics), 6))
    if len(metrics) == 1:
        axes = [axes]
    for ax, (col, label) in zip(axes, metrics):
        sns.barplot(data=df, x="philosophy", y=col, ax=ax, errorbar="sd")
        ax.set_title(label, fontsize=13)
        ax.set_xlabel("Philosophy")
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("Strategy Philosophy Comparison", fontsize=15)
    return save_figure(fig, output_dir, "16_philosophy_comparison.png")


def generate_results_plots(df, output_dir):
    paths = []
    for fn in (plot_depth_vs_energy, plot_depth_vs_valid_rate, plot_depth_vs_sharpe,
               plot_ticker_selection_heatmap, plot_energy_vs_sharpe,
               plot_philosophy_comparison):
        path = fn(df, output_dir)
        if path:
            paths.append(path)
    return paths
