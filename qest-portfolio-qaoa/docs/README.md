# Documentation Map

This folder explains the project for **three audiences**. Pick a path.

The project supports three datasets: `qest` (10 assets, the default), `nasdaq_baltic` (29), and `nyse` (32).

## Path A — "I know nothing about quantum computing"
Read in this order:

1. [`concepts.md`](concepts.md) — the problem, risk/return, and QAOA explained with analogies
2. [`glossary.md`](glossary.md) — one-sentence definitions for every term
3. [`results_and_visualizations.md`](results_and_visualizations.md) — what the numbers and pictures mean

You can stop there. You will understand what the project does, how it decides, and how to read its output.

## Path B — "I want to run and modify it"
1. [`usage.md`](usage.md) — install, run, regenerate plots, change parameters
2. [`architecture.md`](architecture.md) — repo layout, module responsibilities, data flow
3. [`hardware.md`](hardware.md) — optional real-IBM-hardware demo (two-stage: optimize on Aer, sample on hardware)
4. [`faq.md`](faq.md) — limitations, placeholders, troubleshooting

## Path C — "I am reviewing or judging it"
1. Root [`README.md`](../README.md) — one-page overview and status
2. [`results_and_visualizations.md`](results_and_visualizations.md) — evidence and how to read it
3. [`faq.md`](faq.md) — what is real, what is a placeholder, what the caveats are

---

## The documents

| File | Contents |
|---|---|
| [`concepts.md`](concepts.md) | Plain-language primer: the stock problem, return vs risk, binary choices, QUBO, Ising spins, QAOA, the XY mixer, Dicke states, the risk dial, and how answers are scored |
| [`glossary.md`](glossary.md) | Alphabetical glossary; every term defined in one or two sentences |
| [`architecture.md`](architecture.md) | Directory tree, per-module responsibilities, end-to-end data-flow trace, entry points, and every hardcoded parameter |
| [`usage.md`](usage.md) | Setup, data format, running the experiment (`--quick` / `--full`), generating visualizations, changing settings, reproducibility |
| [`hardware.md`](hardware.md) | Optional IBM Quantum hardware demo: two-stage design, circuit-depth trade-off, configuration, commands, measured result, caveats |
| [`results_and_visualizations.md`](results_and_visualizations.md) | Result-CSV schema and column dictionary; catalog of all 20 plots with "how to read this" notes |
| [`faq.md`](faq.md) | FAQ, design decisions, empty placeholder files, limitations, and troubleshooting |

## One-paragraph summary

The project treats stock selection as a **yes/no decision per stock**. It builds a mathematical "score" (a Hamiltonian) that rewards high return and low risk, and adds a penalty for breaking the sector rule. A **QAOA** circuit prepares a quantum state biased toward high-scoring selections; a classical optimizer tunes the circuit's two knobs, and measuring the circuit yields a candidate portfolio. Because the portfolio must contain exactly five stocks, the circuit starts in a **Dicke state** (an equal blend of all exactly-five selections) and uses an **XY mixer** (which only swaps a selected stock for an unselected one, so the count never changes). The best sampled portfolio is then scored for validity, return, volatility, and Sharpe ratio, and compared with the exact classical optimum.
