# Glossary

One- or two-sentence definitions. Terms are grouped loosely from finance → math → quantum → software. See [`concepts.md`](concepts.md) for the narrative version.

---

## Finance

**Alpha (α) / risk factor** — The dial that controls how much the optimizer cares about risk versus return. Alpha 0 = return only ("Gambling"), 2 = balanced ("Neutral"), 5 = risk-averse ("Safe").

**Annualized return** — The average yearly growth of an investment, expressed as a percentage.

**Annualized volatility** — The yearly standard deviation of returns; the project's measure of **risk**. Computed from daily returns and scaled by √252 (252 trading days per year).

**Correlation** — A number from −1 to +1 describing how two stocks move together. +1 = lockstep, 0 = unrelated, −1 = opposite.

**Covariance matrix (Σ)** — A table of pairwise risk relationships. The diagonal holds each stock's variance; off-diagonal entries hold covariances. Used to compute portfolio risk.

**Diversification** — Spreading money across assets whose movements don't perfectly align, so their ups and downs partly cancel.

**Efficient frontier** — The set of portfolios that offer the best possible return for each level of risk. The project visualizes the feasible frontier of its 210 valid portfolios.

**Equal weights** — Every selected stock gets the same fraction of the portfolio (20% when five are chosen).

**Portfolio** — A collection of stocks with assigned weights. Here: exactly five stocks, equal weights.

**Return** — Profit from holding a stock, as a percentage. Higher is better.

**Sharpe ratio** — Return divided by volatility. "Return per unit of risk." Higher is better.

**Sector** — An industry group (Financials, Consumer, Energy & utilities, Transport). The rule allows at most two stocks per sector.

**Ticker** — A short stock identifier, e.g. `ROE1L.VS`.

**Volatility** — How much a price bounces around; the project's proxy for risk.

---

## Math & optimization

**Binary variable** — A variable that is only 0 or 1. Here, "don't buy / buy" for each stock.

**Cardinality constraint** — A rule about *how many* items are selected. Here: exactly five.

**Classical solver** — A non-quantum algorithm that finds the best answer. The project uses an exact solver (true optimum) and a continuous relaxation (fractional shares allowed).

**COBYLA** — A classical numerical optimizer that adjusts parameters to minimize a function without needing gradients. It tunes the QAOA angles.

**Combinatorial explosion** — The way the number of possible selections grows exponentially with the number of items. C(10,5)=252, but C(100,5) ≈ 75 million.

**Constraint** — A rule the answer must satisfy. Hard constraints must hold; soft constraints are encouraged via penalties.

**Continuous relaxation** — Allowing variables to take fractional values between 0 and 1, which makes the problem easier to solve and gives a reference point.

**Energy** — The score being minimized. Low energy = good portfolio. Borrowed from physics.

**Feasible** — Satisfying all hard rules (exactly five stocks, max two per sector).

**Global optimum** — The single best possible answer.

**Hamming weight** — The number of 1s in a bit string. A five-stock portfolio has Hamming weight 5.

**Heuristic / approximate algorithm** — An algorithm that aims for a good answer without guaranteeing the best one.

**Ising Hamiltonian** — The energy function written in terms of ±1 spin variables instead of 0/1 variables.

**Penalty term** — A fine added to the energy when a soft rule is broken. Large penalties make violations unattractive.

**QUBO** — *Quadratic Unconstrained Binary Optimization*: an energy function over 0/1 variables with linear and pairwise terms. Constraints are folded in as penalties.

**Seed** — A number that makes random choices reproducible. Same seed + same code = same result.

**Simulator** — Software that mimics a quantum computer on a classical CPU. The project uses Qiskit's **Aer** simulator.

---

## Quantum computing

**Aer** — Qiskit's high-performance local simulator for quantum circuits.

**Amplitude** — The complex number attached to each bit pattern in a superposition; its squared magnitude gives the measurement probability.

**Ansatz** — The parameterized circuit template that QAOA fills in. "Ansatz" = an educated guess at the circuit's shape.

**Beta (β)** — The mixer angle in a QAOA layer. Controls how much probability is shuffled between candidates.

**Bitstring** — A string of 0s and 1s, e.g. `1011001000`, representing one measured portfolio.

**Circuit depth (p)** — The number of cost+mixer layer pairs in QAOA. More depth = more expressive but longer and noisier.

**Cost layer** — The part of the QAOA circuit that applies the problem's energy, nudging probability toward low-energy (good) portfolios. Strength = gamma.

**Dicke state** — A quantum state that is an equal superposition of *all* bit patterns with exactly k ones. Used to guarantee "exactly five" from the start.

**Entanglement** — A quantum correlation between qubits stronger than any classical link. QAOA circuits can create it; it is what makes simulating large circuits hard.

**Gamma (γ)** — The cost-layer angle in a QAOA layer. Controls how strongly good portfolios are favored.

**Gate** — A basic operation on qubits (like a logic gate for bits).

**Hamiltonian** — An operator whose eigenvalues are the possible energies of a configuration. The lowest eigenvalue is the ground state (best answer).

**Measurement** — Reading out qubits, collapsing a superposition into one concrete bitstring. Repeated many times ("shots") to estimate probabilities.

**Mixer** — The part of the QAOA circuit that shuffles probability between candidates so the search keeps exploring. Standard mixers use X rotations; this project uses an **XY mixer**.

**Pauli operators (X, Y, Z)** — The three basic single-qubit observables. X flips a qubit; Z measures its 0/1 value; Y is a combination. Energy functions are written as sums of Pauli strings.

**p (depth)** — See "Circuit depth".

**QAOA** — *Quantum Approximate Optimization Algorithm*. Alternating cost and mixer layers, with classically tuned angles, used to find good solutions to combinatorial problems.

**Qubit** — A quantum bit: can be 0, 1, or a superposition of both before measurement.

**Shots** — The number of times a circuit is run and measured. More shots = better probability estimates but longer runtime.

**Spin** — A quantum property with two values, +1 and −1 (up/down), used in the Ising formulation.

**Superposition** — A qubit's ability to hold a blend of 0 and 1 at once.

**Transpile** — Rewrite a circuit into the specific gate set of a target device/simulator. Needed before execution.

**XY mixer** — A mixer built from pairs of qubits that **swaps** a 1 between them. It conserves the number of 1s, so it preserves "exactly five".

---

## Software & project

**Agg backend** — A non-interactive Matplotlib backend that renders plots to files without opening a window. Forced in the visualization package to avoid GUI/shutdown crashes on headless machines.

**AerSampler / AerEstimator** — Qiskit primitives that sample bitstrings and estimate expectation values on the Aer simulator.

**CLI flag** — A command-line option such as `--all` or `--network`.

**CSV** — Comma-separated values; the results log format.

**Grid search** — Trying every combination of settings (philosophy × ansatz × depth × seed) and logging each result.

**Primitive** — A Qiskit interface that hides the low-level details of running circuits (`Sampler`, `Estimator`).

**Runner** — `src/pipeline/runner.py`, the main experiment script.

**Transpilation level** — How aggressively Qiskit optimizes a circuit. The project uses level 1.
