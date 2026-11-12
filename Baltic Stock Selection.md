QEst Hack 2026 · Coop Bank challenge

# Stock selection on Nasdaq Baltic

From 10 stocks in 4 sectors, select 5 so that the return is as high as possible and the volatility as low as possible. Weights are equal, and no more than 2 stocks may come from the same sector. Optional extra: repeat the same with NYSE stocks.

Financials

- LHV Group
- Coop Pank
- Artea bankas

Max 2 of 3

Consumer

- Tallinna Kaubamaja
- Apranga
- Pieno žvaigždės

Max 2 of 3

Energy & utilities

- Ignitis
- Tallinna Vesi

Max 2 of 2

Transport

- Tallink
- Tallinna Sadam

Max 2 of 2

## Data

Public daily closing prices. The portfolio is selected on 2021–2024 data; 2025 is used only for validation. No synthetic or client data is used.

**252** ways to pick 5 of 10 **210** meet the sector rule **987** common trading days, 2021–24

[Return & volatility (CSV)](https://drive.google.com/uc?export=download&id=1O_FkANwtcrlkATJoup48ZlLq5fjyjcXy) [Correlation matrix (CSV)](https://drive.google.com/uc?export=download&id=1uQNagZqvV9T7hsFKmczAjfXaOIT4lvME)

## Return vs. volatility, 2021–2024

Up and to the left is better: higher return for less risk.

Financials Consumer Energy & utilities Transport

## Stock data

Return: annual growth of the dividend-adjusted price. Volatility: annualized standard deviation of daily log returns (√252).

| Company | Ticker | Return 21–24 | Vol. 21–24 | Return 2025 | Vol. 2025 |
| --- | --- | --- | --- | --- | --- |

All values in %. Return 2021–24 is per year.

## Correlation of daily returns, 2021–2024

Needed for portfolio volatility and as edge weights in a graph formulation. Darker = moves together more. Banks correlate most with each other; Pieno žvaigždės barely correlates with anything.

Students can download the daily prices themselves with the tickers above (for example with the `yfinance` Python package) to rebuild these numbers or compute the covariance matrix. Source: daily dividend-adjusted closing prices, 4 Jan 2021 – 30 Dec 2025, from [Yahoo Finance](https://finance.yahoo.com/quote/LHV1T.TL/history/), retrieved 12 Nov 2026.