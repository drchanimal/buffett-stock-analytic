import yfinance as yf
import pandas as pd
import numpy as np
import edgar
from edgar import Company
import requests

def resolve_ticker(query: str) -> str:
    """Attempt to resolve a company name or phrase into a stock ticker using Yahoo's search API."""
    query = query.strip()
    if not query:
        return query
        
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if 'quotes' in data and len(data['quotes']) > 0:
                # Find the first equity
                for match in data['quotes']:
                    if match.get('quoteType') == 'EQUITY':
                        return match['symbol']
                # Fallback to very first symbol
                return data['quotes'][0]['symbol']
    except Exception as e:
        print(f"Warning: Failed to resolve ticker name via search API: {e}")
        
    # Fallback to the original search string if it fails
    return query


def set_sec_identity(email: str):
    """Set the SEC EDGAR user agent identity string required by the API."""
    try:
        # SEC requires format: Sample Company Name user@domain.com
        if "@" in email and " " not in email:
            email = f"ValueApp {email}"
        edgar.set_identity(email)
        return True
    except Exception as e:
        print(f"Error setting SEC identity: {e}")
        return False

def pull_yfinance_data(ticker_symbol: str):
    """Pull financial data from yfinance."""
    ticker = yf.Ticker(ticker_symbol)
    
    return {
        "info": ticker.info,
        "income_statement": ticker.financials,
        "balance_sheet": ticker.balance_sheet,
        "cashflow": ticker.cashflow,
        "history": ticker.history(period="1mo")
    }

def get_recent_value(df, row_name, default=0):
    """Safely get the most recent value from a yfinance dataframe row."""
    if df is None or df.empty or row_name not in df.index:
        return default
    row = df.loc[row_name].dropna()
    if not row.empty:
        return float(row.iloc[0])
    return default

def get_row_series(df, row_name):
    """Safely get the entire row as a series from a yfinance dataframe."""
    if df is None or df.empty or row_name not in df.index:
        return pd.Series(dtype=float)
    return df.loc[row_name].dropna()

def calculate_roic(income_statement, balance_sheet):
    """Calculate Return on Invested Capital."""
    ebit = get_recent_value(income_statement, "EBIT")
    tax_provision = get_recent_value(income_statement, "Tax Provision")
    pretax_income = get_recent_value(income_statement, "Pretax Income")
    
    tax_rate = (tax_provision / pretax_income) if pretax_income > 0 else 0.21
    nopat = ebit * (1 - tax_rate)
    
    total_debt = get_recent_value(balance_sheet, "Total Debt")
    total_equity = get_recent_value(balance_sheet, "Total Equity Gross Minority Interest", 
                                    default=get_recent_value(balance_sheet, "Stockholders Equity"))
    cash = get_recent_value(balance_sheet, "Cash And Cash Equivalents")
    
    invested_capital = total_debt + total_equity - cash
    if invested_capital <= 0:
        return 0
    return nopat / invested_capital

def calculate_roe(income_statement, balance_sheet):
    """Calculate Return on Equity."""
    net_income = get_recent_value(income_statement, "Net Income")
    total_equity = get_recent_value(balance_sheet, "Stockholders Equity", 
                                    default=get_recent_value(balance_sheet, "Total Equity Gross Minority Interest"))
    if total_equity <= 0:
        return 0
    return net_income / total_equity

def calculate_debt_coverage(balance_sheet, income_statement):
    """Calculate Debt to Equity and Years to Pay Off Debt."""
    total_debt = get_recent_value(balance_sheet, "Total Debt")
    total_equity = get_recent_value(balance_sheet, "Stockholders Equity", 
                                    default=get_recent_value(balance_sheet, "Total Equity Gross Minority Interest"))
    net_income = get_recent_value(income_statement, "Net Income")
    
    debt_to_equity = (total_debt / total_equity) if total_equity > 0 else float('inf')
    years_to_payoff = (total_debt / net_income) if net_income > 0 else float('inf')
    
    return {
        "debt_to_equity": debt_to_equity,
        "years_to_pay_off": years_to_payoff
    }

def calculate_eps_cagr(income_statement):
    """Calculate the Compound Annual Growth Rate of EPS across available history (usually 4-5 years)."""
    eps_series = get_row_series(income_statement, "Basic EPS")
    if eps_series.empty or len(eps_series) < 2:
        eps_series = get_row_series(income_statement, "Diluted EPS")
        
    if len(eps_series) < 2:
        return 0
        
    # Sort series by date to ensure chronological order (yfinance returns newest first)
    eps_series = eps_series.sort_index()
    try:
        eps_oldest = eps_series.iloc[0]
        eps_newest = eps_series.iloc[-1]
        years = len(eps_series) - 1
        
        if eps_oldest <= 0:
            return 0 # CAGR is meaningless if base year is negative
            
        return (eps_newest / eps_oldest) ** (1 / years) - 1
    except:
        return 0

def calculate_fcf_cagr(cashflow):
    """Calculate the Compound Annual Growth Rate of Free Cash Flow."""
    fcf_series = get_row_series(cashflow, "Free Cash Flow")
        
    if len(fcf_series) < 2:
        return 0
        
    fcf_series = fcf_series.sort_index()
    try:
        fcf_oldest = fcf_series.iloc[0]
        fcf_newest = fcf_series.iloc[-1]
        years = len(fcf_series) - 1
        
        if fcf_oldest <= 0:
            return 0 # Cannot compute meaningful CAGR if starting FCF is negative
            
        cagr = (fcf_newest / fcf_oldest) ** (1 / years) - 1
        return cagr
    except:
        return 0

def calculate_intrinsic_value(fcf, growth_rate, discount_rate, terminal_rate, shares_out, years_projected=10):
    """Calculate intrinsic value using a Discounted Cash Flow (DCF) model."""
    if fcf <= 0 or shares_out <= 0 or discount_rate <= terminal_rate:
        return 0
    
    # Project FCF
    projected_fcf = []
    current_fcf = fcf
    for _ in range(years_projected):
        current_fcf *= (1 + growth_rate)
        projected_fcf.append(current_fcf)
        
    # Discount FCF
    pv_fcf = 0
    for i, cf in enumerate(projected_fcf):
        pv_fcf += cf / ((1 + discount_rate) ** (i + 1))
        
    # Terminal Value
    terminal_value = (projected_fcf[-1] * (1 + terminal_rate)) / (discount_rate - terminal_rate)
    pv_terminal = terminal_value / ((1 + discount_rate) ** years_projected)
    
    total_enterprise_value = pv_fcf + pv_terminal
    
    return total_enterprise_value / shares_out

def perform_fundamental_analysis(ticker_symbol: str, user_identity: str = "") -> dict:
    """Wrapper function to perform full fundamental analysis on a ticker."""
    if user_identity:
        set_sec_identity(user_identity)
        
    data = pull_yfinance_data(ticker_symbol)
    inc = data["income_statement"]
    bs = data["balance_sheet"]
    cf = data["cashflow"]
    info = data["info"]
    history = data["history"]
    
    current_price = history["Close"].iloc[-1] if not history.empty else info.get("currentPrice", 0)
    
    fcf = get_recent_value(cf, "Free Cash Flow")
    shares_out = info.get("sharesOutstanding", 0)
    
    if shares_out == 0 and current_price: # Attempt to approx from market cap
        market_cap = info.get("marketCap", 0)
        if market_cap:
            shares_out = market_cap / current_price
            
    debt_coverage = calculate_debt_coverage(bs, inc)
    
    # Incorporating edgartools: if user mapped an identity, we can fetch facts
    edgar_data_found = False
    if user_identity:
        try:
            company = Company(ticker_symbol)
            # You can access financials with company.financials but yfinance provides easily 
            # parsable data. We just map success here.
            edgar_data_found = True
        except Exception:
            pass
            
    return {
        "Ticker": ticker_symbol.upper(),
        "Current Price": current_price,
        "ROIC": calculate_roic(inc, bs),
        "ROE": calculate_roe(inc, bs),
        "Debt to Equity": debt_coverage["debt_to_equity"],
        "Years to Pay Off Debt": debt_coverage["years_to_pay_off"],
        "EPS CAGR (Historical)": calculate_eps_cagr(inc),
        "FCF CAGR (Historical)": calculate_fcf_cagr(cf),
        "Latest FCF": fcf,
        "Shares Outstanding": shares_out,
        "Market Cap": info.get("marketCap", 0),
        "Gross Margin": info.get("grossMargins", 0),
        "Net Margin": info.get("profitMargins", 0),
        "Company Name": info.get("shortName", ticker_symbol.upper()),
        "Industry": info.get("industry", "Unknown"),
        "Sector": info.get("sector", "Unknown"),
        "Edgar Fetched": edgar_data_found
    }
