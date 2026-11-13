# Concepts — Explained Without Quantum Jargon

This is the "no quantum background needed" guide. Every technical term is explained the first time it appears, and there is a [glossary](glossary.md) if you get lost. Math is kept in optional **"For the curious"** boxes — you can skip them.

---

## Part 1 — The money problem

### The goal

We have **ten stocks** from the Nasdaq Baltic market. We must build a portfolio of **exactly five** of them. Each chosen stock gets the **same share of money** (20% each — "equal weights"), so the only decision is *which five*.

Two rules apply:

1. **Exactly five stocks** must be chosen.
2. **At most two stocks from any one sector** — so we don't put all our eggs in one industry basket.

The aim: **as much return as possible, for as little risk as possible.**

### What "return" and "risk" mean

- **Return** is how much the stock price grew (including dividends) over a period, expressed as a percentage per year.
- **Risk** is how much the price bounces around. A stock that swings ±40% is riskier than one that swings ±8%, even if both end up at the same average. We measure risk as **volatility** — the standard deviation of daily returns, scaled to a yearly number.

A portfolio's risk is not just the average of its stocks' risks. It also depends on how the stocks move **together**:

- If two stocks tend to rise and fall together (**positively correlated**), combining them does **not** reduce risk much.
- If they move independently or in opposite directions, combining them **cancels out** some of the bumpiness.

This is the whole point of diversification, and it is why the project needs a **correlation matrix** — a table saying how each pair of stocks moves together.

### Why the count matters

Choosing 5 from 10 gives

```
C(10, 5) = 252
```

possible portfolios. The sector rule removes the ones with 3+ stocks in Financials or 3+ in Consumer (the only sectors with more than two members). That leaves **210 valid portfolios**. See the FAQ for the exact arithmetic.

For ten stocks, a computer can simply try all 210. The interesting question is what happens when there are hundreds of stocks — the number of combinations explodes, and brute force stops working. That is the regime where a quantum algorithm is *supposed* to help.

### The three investor personalities

"How much return do you want vs. how much risk can you tolerate?" is a dial. The project exposes it as **alpha** (also called the **risk factor**):

| Personality | Alpha | Behaviour |
|---|---|---|
| Gambling | 0.0 | Cares only about return; ignores risk |
| Neutral | 2.0 | Balanced |
| Safe | 5.0 | Heavily penalizes risk |

A **higher alpha means more risk-aversion**. The same ten stocks produce different "best" portfolios under different personalities.

---

## Part 2 — Turning choices into math

### Step 1: one yes/no switch per stock

Give every stock a switch that is **1 if we buy it** and **0 if we don't**:

```
x = [x1, x2, ..., x10]     each xi is 0 or 1
```

A portfolio is just a pattern of ten bits, e.g. `1 0 0 1 1 0 1 0 0 0`. The "exactly five" rule becomes "exactly five ones", and "at most two per sector" becomes a limit on how many ones a group of switches may contain.

### Step 2: a score to minimize

We want the computer to find the bit pattern with the best score. We write the score as an **energy** (low energy = good, borrowing the language of physics):

```
energy =  risk_penalty  −  return_reward  +  rule_violation_penalty
```

- **risk_penalty** grows with the portfolio's volatility (and alpha controls how loudly it complains).
- **return_reward** grows with expected return, so high-return portfolios get lower energy.
- **rule_violation_penalty** is a large fine for breaking the sector rule.

This kind of score — a sum of terms that are either constant, linear in the switches, or products of two switches — is called a **QUBO**: *Quadratic Unconstrained Binary Optimization*. "Quadratic" means pairs of switches multiply; "unconstrained" means the rules are folded into the score as penalties rather than enforced separately.

> **For the curious — the actual QUBO**
>
> With `r` the return vector, `Σ` the covariance matrix (risk), `α` the risk factor, `P` the penalty weight, and `S` the set of sectors:
>
> ```
> minimize   α · xᵀ Σ x  −  rᵀ x  +  P · Σ_sectors max(0, (Σ_{i∈sector} x_i) − 2)²
> ```
>
> The first term is risk, the second is negative return (minimizing the negative maximizes return), and the third fines any sector that holds more than two stocks.

### Step 3: from 0/1 switches to "spins"

Quantum hardware naturally speaks the language of **spins**, which are +1 or −1 (like a tiny bar magnet pointing up or down). The conversion is simple:

```
xi = (1 − Zi) / 2
```

where `Zi` is a spin variable. Substituting this into the QUBO produces an **Ising Hamiltonian**: the same score, rewritten in spin language, which is what a quantum circuit can act on. A **Hamiltonian** is just a compact way to write "the energy of a configuration"; the lowest-energy configuration is the answer we want.

> **Why bother?** Because the quantum algorithm's cost layer is built from this spin version. Mathematically it is the same problem wearing a different coat.

---

## Part 3 — The quantum part (QAOA)

### A qubit in one sentence

A classical bit is 0 or 1. A **qubit** can be 0, 1, or — before you measure it — a **superposition** of both at once. With ten qubits, the computer can hold a blend of many of the 2¹⁰ = 1024 possible bit patterns simultaneously.

**Measurement** collapses that blend: you get one concrete pattern (one portfolio), with probabilities determined by the blend. That is why the algorithm is run many times ("shots") and the most frequent answer is taken.

### What QAOA does

**QAOA** stands for *Quantum Approximate Optimization Algorithm*. It builds a circuit with alternating layers:

1. **Start** in a chosen initial state (a superposition of candidate portfolios).
2. **Cost layer** — a nudge whose strength is **gamma (γ)**. It makes good portfolios (low energy) slightly more likely and bad ones slightly less likely.
3. **Mixer layer** — a nudge whose strength is **beta (β)**. It shuffles probability between candidates so the algorithm can keep exploring instead of locking in too early.
4. **Repeat** steps 2–3 **p** times. `p` is the **depth**: more layers = more expressive, but a longer, noisier circuit.

So the circuit has two knobs per layer: `(γ₁, β₁, γ₂, β₂, …)`. For depth `p` there are `2p` numbers to tune.

### The hybrid loop

Nobody knows the best knob settings in advance. So QAOA runs in a loop:

```
pick initial knob values
repeat:
    run the circuit on a simulator
    measure the average energy of the resulting state
    let a classical optimizer (COBYLA) adjust the knobs to lower that energy
until the energy stops improving
```

This "quantum circuit + classical tuner" pattern is called a **hybrid** algorithm. The classical optimizer is the coach; the quantum circuit is the player.

### Why this is only "approximate"

QAOA does not guarantee the exact best answer, especially at low depth. It produces a probability distribution concentrated near good answers. The project therefore compares it against the **exact classical solution**, which for ten stocks is easy to compute and serves as the benchmark.

---

## Part 4 — Keeping exactly five stocks

### The problem with plain QAOA

A standard QAOA starts every qubit in an equal blend of 0 and 1. That means it explores **all 1024 bit patterns**, including portfolios with 0, 3, or 10 stocks. The "exactly five" rule would have to be enforced by an extra penalty — and penalties are soft: they discourage bad answers but do not forbid them.

The project uses a smarter trick instead.

### Trick 1: start in a Dicke state

A **Dicke state** is a special quantum state that is an **equal superposition of every bit pattern with exactly five ones** — and nothing else. Prepare the qubits in a Dicke state and the "exactly five" rule is true *by construction*. The number of ones in a bit pattern is called its **Hamming weight**; the Dicke state contains only Hamming-weight-5 patterns.

### Trick 2: use an XY mixer

The mixer is normally a global shuffle. The project uses an **XY mixer**, built from pairs of qubits:

```
XY mixer = ½ · Σ (XiXj + YiYj)
```

In plain terms, an XY mixer **moves a 1 from one qubit to another** — it swaps "selected" and "not selected". It never creates or destroys a 1. So if you start with five ones, you always have five ones. The Hamming weight is **conserved**.

**Dicke initial state + XY mixer = the "exactly five" rule is never violated.** No penalty needed.

### The trade-off

The project also contains a cheaper starting state (`build_simple_valid_state`, which just sets the first five qubits to 1) for noisy real hardware, and a standard QAOA for comparison. But the active configuration uses the Dicke + XY combination.

---

## Part 5 — The sector rule

"At most two per sector" is enforced by the **penalty term** in the QUBO (Part 2). The penalty is quadratic: it adds a fine proportional to the square of the excess.

Only two sectors can ever break the rule, because only two have more than two members:

| Sector | Stocks | Can it violate "max 2"? |
|---|---|---|
| Financials | 3 | Yes — all 3 could be chosen |
| Consumer | 3 | Yes |
| Energy & utilities | 2 | No — it only has 2 |
| Transport | 2 | No — it only has 2 |

That is why the penalty only ever "bites" for Financials and Consumer.

---

## Part 6 — How the answer is judged

For each candidate portfolio (the most frequent bit pattern measured from the circuit), the project computes:

| Check | Meaning |
|---|---|
| **Valid** | Exactly five stocks **and** no sector over two. This is a hard yes/no. |
| **Return %** | Annualized expected return of the equal-weight portfolio |
| **Volatility %** | Annualized risk of the portfolio, using the covariance matrix |
| **Sharpe ratio** | Return divided by volatility — "how much return per unit of risk". Higher is better. |

The **exact classical solver** finds the true optimum of the same QUBO. Comparing the QAOA portfolio's metrics to the classical one tells you how close the quantum approach got. The project also computes a **continuous relaxation** (allow fractional shares) as a second reference point.

---

## Part 7 — What is actually "quantum" here?

Be clear-eyed about this:

- The circuits are executed on **Aer**, a **simulator** that runs on a normal CPU. No quantum hardware is involved.
- The problem is small enough that the **classical exact solver is the ground truth**. The quantum path is being *evaluated against* it, not beating it.
- The value of the prototype is the **pipeline**: problem → QUBO → constrained QAOA → sampling → evaluation → visualization. Swap in a bigger stock universe or real hardware and the same pipeline applies.
- The constrained circuit (Dicke + XY) is the genuinely interesting part: it shows how to respect a hard cardinality constraint *inside* the quantum circuit instead of hoping a penalty works.

---

## Part 8 — The whole story in ten lines

1. Ten stocks, pick five, max two per sector.
2. Return is good; risk is bad; correlation decides how much risk cancels.
3. Give each stock a 0/1 switch.
4. Write a score that rewards return, punishes risk, and fines sector violations → **QUBO**.
5. Rewrite the score in ±1 spins → **Ising Hamiltonian**.
6. Start the qubits in a **Dicke state** (only five-stock patterns).
7. Alternate **cost layers** (γ) and **XY mixer layers** (β), `p` times.
8. A classical optimizer tunes the knobs to lower the average energy.
9. Measure many times; the most frequent five-stock pattern is the answer.
10. Score it (validity, return, volatility, Sharpe) and compare with the exact classical optimum.

That's the entire project. Everything else is engineering and pictures.
