import pandas as pd
import numpy as np

class PortfolioData:
    def __init__(self, stock_csv: str, corr_csv: str):
        # Load raw data
        self.df_stocks = pd.read_csv(stock_csv)
        self.df_corr = pd.read_csv(corr_csv, index_col='ticker')
        
        self.tickers = self.df_stocks['ticker'].tolist()
        self.n_assets = len(self.tickers)
        
        # We optimize on 2021-2024 data, leaving 2025 for validation
        # Convert percentages to decimals
        self.returns = self.df_stocks['return_2021_2024_pct_per_yr'].values / 100.0
        self.volatilities = self.df_stocks['volatility_2021_2024_pct'].values / 100.0
        
        # Build Covariance Matrix: Cov(i,j) = Corr(i,j) * Vol(i) * Vol(j)
        self.covariance = np.zeros((self.n_assets, self.n_assets))
        for i, t_i in enumerate(self.tickers):
            for j, t_j in enumerate(self.tickers):
                corr_ij = self.df_corr.loc[t_i, t_j]
                self.covariance[i, j] = corr_ij * self.volatilities[i] * self.volatilities[j]
                
        # Group indices by sector for constraints
        self.sector_indices = {}
        for idx, row in self.df_stocks.iterrows():
            sector = row['sector']
            if sector not in self.sector_indices:
                self.sector_indices[sector] = []
            self.sector_indices[sector].append(idx)

    def get_formulation_data(self):
        """Returns the necessary variables for the Markowitz formulation."""
        return self.returns, self.covariance, self.sector_indices, self.tickers