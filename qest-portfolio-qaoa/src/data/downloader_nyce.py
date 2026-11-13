
import yfinance as yf
import pandas as pd
import numpy as np
import datetime

# NYSE Composite subset selection based on market cap representation
# This includes the top 30-35 most heavily weighted stocks from various sectors
tickers_info = {
    'TSM': ('Information Technology', 'Taiwan Semiconductor Manufacturing'),
    'LLY': ('Health Care', 'Eli Lilly & Co.'),
    'JPM': ('Financials', 'JPMorgan Chase & Co.'),
    'BRK-B': ('Financials', 'Berkshire Hathaway Class B'),
    'V': ('Financials', 'Visa Inc.'),
    'JNJ': ('Health Care', 'Johnson & Johnson'),
    'XOM': ('Energy', 'ExxonMobil Corporation'),
    'MA': ('Financials', 'Mastercard Incorporated'),
    'ABBV': ('Health Care', 'AbbVie Inc.'),
    'KO': ('Consumer Staples', 'Coca-Cola Company'),
    'CVX': ('Energy', 'Chevron Corporation'),
    'PG': ('Consumer Staples', 'Procter & Gamble Company'),
    'ORCL': ('Information Technology', 'Oracle Corp'),
    'MRK': ('Health Care', 'Merck & Co., Inc.'),
    'UNH': ('Health Care', 'UnitedHealth Group'),
    'GE': ('Industrials', 'GE Aerospace'),
    'HD': ('Consumer Discretionary', 'Home Depot, Inc.'),
    'BAC': ('Financials', 'Bank of America'),
    'NVS': ('Health Care', 'Novartis AG'),
    'HSBC': ('Financials', 'HSBC Holdings plc'),
    'PM': ('Consumer Staples', 'Philip Morris International'),
    'MS': ('Financials', 'Morgan Stanley'),
    'AZN': ('Health Care', 'AstraZeneca PLC'),
    'RY': ('Financials', 'Royal Bank of Canada'),
    'SHEL': ('Energy', 'Shell plc'),
    'RTX': ('Industrials', 'RTX Corporation'),
    'SAP': ('Information Technology', 'SAP SE'),
    'CAT': ('Industrials', 'Caterpillar Inc.'),
    'TMO': ('Health Care', 'Thermo Fisher Scientific'),
    'GS': ('Financials', 'Goldman Sachs Group'),
    'WFC': ('Financials', 'Wells Fargo & Co.'),
    'BABA': ('Consumer Discretionary', 'Alibaba Group')
}

tickers = list(tickers_info.keys())

print("Downloading data for NYSE subset...")
data = yf.download(tickers, start='2021-01-01', end='2025-12-31', progress=False)['Close']

returns = data.pct_change().dropna(how='all')

returns_21_24 = returns.loc['2021-01-01':'2024-12-31']
returns_25 = returns.loc['2025-01-01':'2025-12-31']

stock_data = []
TRADING_DAYS = 252

for ticker in tickers:
    if ticker not in returns.columns:
        continue
    
    t_ret_21_24 = returns_21_24[ticker].dropna()
    t_ret_25 = returns_25[ticker].dropna()
    
    if len(t_ret_21_24) == 0:
        continue
        
    ret_21_24_pct = t_ret_21_24.mean() * TRADING_DAYS * 100
    vol_21_24_pct = t_ret_21_24.std() * np.sqrt(TRADING_DAYS) * 100
    
    if len(t_ret_25) > 0:
        ret_25_pct = t_ret_25.mean() * TRADING_DAYS * 100
        vol_25_pct = t_ret_25.std() * np.sqrt(TRADING_DAYS) * 100
    else:
        ret_25_pct = np.nan
        vol_25_pct = np.nan
        
    sector, company = tickers_info[ticker]
    
    stock_data.append({
        'sector': sector,
        'company': company,
        'ticker': ticker,
        'return_2021_2024_pct_per_yr': round(ret_21_24_pct, 1),
        'volatility_2021_2024_pct': round(vol_21_24_pct, 1),
        'return_2025_pct': round(ret_25_pct, 1) if not np.isnan(ret_25_pct) else 0.0,
        'volatility_2025_pct': round(vol_25_pct, 1) if not np.isnan(vol_25_pct) else 0.0
    })

df_stock = pd.DataFrame(stock_data)
df_stock.to_csv('nyse_stock_data.csv', index=False)
print("Saved nyse_stock_data.csv")

valid_tickers = df_stock['ticker'].tolist()
df_corr = returns_21_24[valid_tickers].corr().round(2)
df_corr.index.name = 'ticker'
df_corr.reset_index(inplace=True)
df_corr.to_csv('nyse_correlation_2021_2024.csv', index=False)
print("Saved nyse_correlation_2021_2024.csv")
