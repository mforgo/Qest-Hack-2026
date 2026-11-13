import pandas as pd
import numpy as np

class PortfolioData:
    def __init__(self, stock_csv: str, corr_csv: str):
        # Load raw data
        self.df_stocks = pd.read_csv(stock_csv)
        self.df_corr = pd.read_csv(corr_csv)

        if 'ticker' not in self.df_stocks.columns:
            raise ValueError(
                f"{stock_csv} must contain a 'ticker' column, "
                f"found {list(self.df_stocks.columns)}"
            )

        # Correlation files written with DataFrame.reset_index() may use
        # 'Ticker', 'ticker', 'index', or an unnamed first column.
        index_column = next(
            (
                column
                for column in self.df_corr.columns
                if str(column).strip().lower() in {'ticker', 'index', 'unnamed: 0'}
            ),
            None,
        )
        if index_column is None:
            raise ValueError(
                f"{corr_csv} must have a ticker index column, "
                f"found {list(self.df_corr.columns)}"
            )
        self.df_corr = self.df_corr.set_index(index_column)
        self.df_corr.index.name = 'ticker'

        self.tickers = self.df_stocks['ticker'].tolist()
        self.n_assets = len(self.tickers)

        missing_rows = sorted(set(self.tickers) - set(self.df_corr.index))
        missing_columns = sorted(set(self.tickers) - set(self.df_corr.columns))
        if missing_rows or missing_columns:
            raise ValueError(
                "Correlation matrix does not match the stock list. "
                f"Missing rows: {missing_rows or 'none'}; "
                f"missing columns: {missing_columns or 'none'}"
            )

        # We optimize on 2021-2024 data, leaving 2025 for validation
        # Convert percentages to decimals
        self.returns = self.df_stocks['return_2021_2024_pct_per_yr'].values / 100.0
        self.volatilities = self.df_stocks['volatility_2021_2024_pct'].values / 100.0

        # Build Covariance Matrix: Cov(i,j) = Corr(i,j) * Vol(i) * Vol(j)
        corr = self.df_corr.loc[self.tickers, self.tickers].astype(float).values
        self.covariance = corr * np.outer(self.volatilities, self.volatilities)
                
        # Group indices by sector for constraints
        self.sector_indices = {}
        for idx, row in self.df_stocks.iterrows():
            sector = row['sector']
            if sector not in self.sector_indices:
                self.sector_indices[sector] = []
            self.sector_indices[sector].append(idx)

    def subset(self, indices: list[int]) -> "PortfolioData":
        """Return a new PortfolioData containing only the given asset indices.

        The selected assets keep their original relative order. This is used by
        the hardware runner to shrink a large universe before building the
        circuit, so every downstream array and sector mapping must be sliced
        consistently.
        """
        selected = [int(index) for index in indices]
        if not selected:
            raise ValueError("A portfolio subset must contain at least one asset.")
        if len(set(selected)) != len(selected):
            raise ValueError(f"Duplicate asset indices in subset: {selected}.")
        invalid = [index for index in selected if index < 0 or index >= self.n_assets]
        if invalid:
            raise ValueError(
                f"Asset indices {invalid} are out of range for {self.n_assets} assets."
            )

        subset = object.__new__(PortfolioData)
        subset.df_stocks = self.df_stocks.iloc[selected].reset_index(drop=True)
        subset.df_corr = self.df_corr.iloc[selected, selected].copy()
        subset.df_corr.index = subset.df_stocks["ticker"].tolist()
        subset.df_corr.columns = subset.df_stocks["ticker"].tolist()
        subset.df_corr.index.name = "ticker"

        subset.tickers = subset.df_stocks["ticker"].tolist()
        subset.n_assets = len(subset.tickers)
        subset.returns = self.returns[selected]
        subset.volatilities = self.volatilities[selected]
        subset.covariance = self.covariance[np.ix_(selected, selected)]

        subset.sector_indices = {}
        for idx, row in subset.df_stocks.iterrows():
            subset.sector_indices.setdefault(row["sector"], []).append(idx)

        return subset

    def get_formulation_data(self):
        """Returns the necessary variables for the Markowitz formulation."""
        return self.returns, self.covariance, self.sector_indices, self.tickers