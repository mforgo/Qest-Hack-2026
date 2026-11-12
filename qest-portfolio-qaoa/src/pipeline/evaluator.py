import numpy as np

def evaluate_portfolio(bitstring, returns, covariance, tickers, sector_indices):
    """
    Evaluates the financial metrics and constraint validity of a selected portfolio.
    
    Args:
        bitstring (list or np.ndarray): e.g. [1, 0, 1, 0, 0, 1, 1, 0, 0, 1]
        returns (np.ndarray): Expected returns.
        covariance (np.ndarray): Covariance matrix.
        tickers (list): List of stock tickers.
        sector_indices (dict): Sector to index mapping.
        
    Returns:
        dict: Portfolio metrics and constraint status.
    """
    # The first 10 bits correspond to our stocks (ignoring slack variables if any were passed)
    stock_bits = np.array(bitstring[:len(tickers)])
    selected_indices = np.where(stock_bits == 1)[0]
    selected_tickers = [tickers[i] for i in selected_indices]
    
    num_selected = len(selected_indices)
    
    # Check Constraints
    is_valid = True
    constraint_issues = []
    
    if num_selected != 5:
        is_valid = False
        constraint_issues.append(f"Selected {num_selected} stocks instead of 5.")
        
    for sector, indices in sector_indices.items():
        count_in_sector = sum(1 for i in indices if stock_bits[i] == 1)
        if count_in_sector > 2:
            is_valid = False
            constraint_issues.append(f"Sector {sector} exceeded limit with {count_in_sector} stocks.")
            
    # Calculate Financials (Hackathon rules: equal weights -> 20% each)
    if num_selected > 0:
        weights = stock_bits / num_selected
        port_return = np.dot(weights, returns)
        port_variance = np.dot(weights.T, np.dot(covariance, weights))
        port_volatility = np.sqrt(port_variance)
        sharpe_ratio = port_return / port_volatility if port_volatility > 0 else 0
    else:
        port_return, port_volatility, sharpe_ratio = 0, 0, 0
        
    return {
        "valid": is_valid,
        "selected_tickers": selected_tickers,
        "return_pct": port_return * 100,
        "volatility_pct": port_volatility * 100,
        "sharpe_ratio": sharpe_ratio,
        "issues": constraint_issues
    }