import yfinance as yf
import pandas as pd
import numpy as np

# Nasdaq Baltic Total Market (Main, Secondary, and First North)
# Note: Yahoo Finance coverage for First North and Secondary lists is often incomplete.
# Tickers must have the correct suffix: .TL (Tallinn), .RG (Riga), .VS (Vilnius)
tickers_info = {
    # --- MAIN LIST ---
    'LHV1T.TL': ('Financials', 'LHV Group'),
    'CPA1T.TL': ('Financials', 'Coop Pank'),
    'TAL1T.TL': ('Consumer Discretionary', 'Tallink Grupp'),
    'TSM1T.TL': ('Industrials', 'Tallinna Sadam'),
    'TKM1T.TL': ('Consumer Discretionary', 'Tallinna Kaubamaja'),
    'TVE1T.TL': ('Utilities', 'Tallinna Vesi'),
    'MRK1T.TL': ('Real Estate', 'Merko Ehitus'),
    'PRF1T.TL': ('Consumer Staples', 'PRFoods'),
    'PKG1T.TL': ('Real Estate', 'Pro Kapital Grupp'),
    'SKN1T.TL': ('Consumer Discretionary', 'Silvano Fashion Group'),
    'HAE1T.TL': ('Industrials', 'Harju Elekter'),
    'ARC1T.TL': ('Real Estate', 'Arco Vara'),
    'EFT1T.TL': ('Real Estate', 'EfTEN Real Estate Fund'),
    'HPR1T.TL': ('Real Estate', 'Hepsor'),
    'INF1T.TL': ('Energy', 'Infortar'),
    'LVN1T.TL': ('Real Estate', 'Liven'),
    'SAF1R.RG': ('Information Technology', 'SAF Tehnika'),
    'BAL1R.RG': ('Consumer Staples', 'Latvijas Balzams'),
    'DGR1R.RG': ('Financials', 'DelfinGroup'),
    'ELEVR.RG': ('Financials', 'Eleving Group'),
    'IDX1R.RG': ('Financials', 'INDEXO'),
    'IGN1L.VS': ('Utilities', 'Ignitis grupe'),
    'ROE1L.VS': ('Consumer Staples', 'Rokiskio suris'),
    'PZV1L.VS': ('Real Estate', 'Panevezio statybos trestas'),
    'APG1L.VS': ('Consumer Discretionary', 'Apranga'),
    'TEL1L.VS': ('Communication Services', 'Telia Lietuva'),
    'SAB1L.VS': ('Financials', 'Siauliu bankas'),
    'AKO1L.VS': ('Consumer Staples', 'Akola group'),
    'GRG1L.VS': ('Materials', 'Grigeo'),
    'INL1L.VS': ('Financials', 'Invalda INVL'),
    'NTU1L.VS': ('Consumer Discretionary', 'Novaturas'),
    'VLP1L.VS': ('Consumer Staples', 'Vilkyskiu pienine'),
    'ZMP1L.VS': ('Consumer Staples', 'Zemaitijos pienas'),
    'AUG1L.VS': ('Consumer Staples', 'AUGA group'),
    'KNE1L.VS': ('Energy', 'KN Energies'),

    # --- SECONDARY LIST & FIRST NORTH (Sample of prominent tickers) ---
    'MAD1R.RG': ('Consumer Staples', 'Madara Cosmetics'),
    'VIR1L.VS': ('Utilities', 'Atsinaujinancios energetikos investicijos'),
    'NEO1L.VS': ('Financials', 'NEO Finance'),
    'AER1T.TL': ('Industrials', 'Airobot Technologies'),
    'BGC1T.TL': ('Information Technology', 'Bercman Technologies'),
    'ELM1T.TL': ('Consumer Discretionary', 'Elmo Rent'),
    'MDR1T.TL': ('Information Technology', 'Modera'),
    'PUN1T.TL': ('Information Technology', 'Punktid Technologies'),
    'LIN1T.TL': ('Consumer Staples', 'Linda Nektar'),
    'GZE1R.RG': ('Energy', 'Latvijas Gaze'),
    'VSS1R.RG': ('Industrials', 'Valmieras stikla skiedra'),
    'SNG1L.VS': ('Energy', 'Snaige'),
    'KNR1L.VS': ('Industrials', 'Kauno energija'),
    'LNA1L.VS': ('Materials', 'Linas'),
    'ZVG1L.VS': ('Real Estate', 'Zemaitijos Investicija'),
    # Note: Adding more tickers requires knowing their exact Yahoo Finance representation.
}

tickers = list(tickers_info.keys())

print(f"Downloading data for {len(tickers)} Baltic companies...")
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
df_stock.to_csv('nasdaq_baltic_all_stock_data.csv', index=False)
print(f"Saved nasdaq_baltic_all_stock_data.csv with {len(df_stock)} rows.")

valid_tickers = df_stock['ticker'].tolist()
df_corr = returns_21_24[valid_tickers].corr().round(2)
df_corr.reset_index(inplace=True)
df_corr.rename(columns={'index': 'ticker'}, inplace=True)
df_corr.to_csv('nasdaq_baltic_all_correlation_2021_2024.csv', index=False)
print("Saved nasdaq_baltic_all_correlation_2021_2024.csv")
