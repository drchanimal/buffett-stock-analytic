import argparse
import pandas as pd
import requests
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from buffett_engine import perform_fundamental_analysis

def fetch_sp500_tickers():
    """Fetch the latest S&P 500 tickers from Wikipedia."""
    print("Fetching S&P 500 tickers from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Wikipedia uses periods for dual-class shares (e.g., BRK.B), yfinance requires dashes (BRK-B)
        tables = pd.read_html(io.StringIO(response.text))
        tickers = tables[0]['Symbol'].tolist()
        clean_tickers = [ticker.replace('.', '-') for ticker in tickers]
        print(f"Successfully fetched {len(clean_tickers)} tickers.")
        return clean_tickers
    except Exception as e:
        print(f"Failed to fetch S&P 500 tickers: {e}")
        return []

def calculate_buffett_score(results):
    """
    Calculate a 7-point score based on Warren Buffett's principles:
    1. ROIC > 15%
    2. ROE > 15%
    3. Debt/Equity < 0.5
    4. Years to Payoff Debt < 3
    5. EPS CAGR > 10%
    6. FCF CAGR > 10%
    7. Gross Margin > 40%
    """
    score = 0
    
    # Safely extract metrics
    roic = results.get("ROIC", 0)
    roe = results.get("ROE", 0)
    d2e = results.get("Debt to Equity", float('inf'))
    y2p = results.get("Years to Pay Off Debt", float('inf'))
    eps_cagr = results.get("EPS CAGR (Historical)", 0)
    fcf_cagr = results.get("FCF CAGR (Historical)", 0)
    margin = results.get("Gross Margin", 0)
    
    if roic and roic > 0.15: score += 1
    if roe and roe > 0.15: score += 1
    if d2e != float('inf') and d2e < 0.5: score += 1
    if y2p != float('inf') and 0 <= y2p < 3.0: score += 1
    if eps_cagr and eps_cagr > 0.10: score += 1
    if fcf_cagr and fcf_cagr > 0.10: score += 1
    if margin and margin > 0.40: score += 1
        
    return score

def scan_single_ticker(ticker, delay=0.0):
    """Worker function to analyze a single ticker with optional rate-limiting delay."""
    try:
        if delay > 0:
            time.sleep(delay)
            
        results = perform_fundamental_analysis(ticker)
        score = calculate_buffett_score(results)
        results['Buffett Score'] = score
        return results
    except Exception as e:
        # Fails generally if the company has missing or totally broken yfinance data
        return None

def main():
    parser = argparse.ArgumentParser(description="Scan S&P 500 for Buffett-style metrics.")
    parser.add_argument('--limit', type=int, default=0, help='Limit the number of tickers to scan (for testing)')
    parser.add_argument('--workers', type=int, default=3, help='Number of concurrent workers (reduced to prevent rate limiting)')
    parser.add_argument('--delay', type=float, default=0.5, help='Seconds to wait between requests to prevent API blocks')
    parser.add_argument('--output', type=str, default='sp500_scan_results.csv', help='Output CSV file name')
    args = parser.parse_args()

    tickers = fetch_sp500_tickers()
    if not tickers:
        return

    if args.limit > 0:
        tickers = tickers[:args.limit]
        print(f"Limiting scan to {args.limit} tickers.")

    print(f"Starting scan of {len(tickers)} companies with {args.workers} workers...")
    
    valid_results = []
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_ticker = {executor.submit(scan_single_ticker, ticker, args.delay): ticker for ticker in tickers}
        
        # Process as they complete with a progress bar
        for future in tqdm(as_completed(future_to_ticker), total=len(tickers), desc="Scanning Stocks"):
            ticker = future_to_ticker[future]
            try:
                res = future.result()
                if res is not None:
                    valid_results.append(res)
            except Exception as exc:
                print(f"{ticker} generated an exception: {exc}")

    if not valid_results:
        print("No valid data retrieved.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(valid_results)
    
    # Sort primarily by score, then by ROIC to break ties
    df = df.sort_values(by=['Buffett Score', 'ROIC'], ascending=[False, False])
    
    # Rearrange columns slightly to highlight the core metrics up front
    cols = list(df.columns)
    first_cols = ['Ticker', 'Company Name', 'Sector', 'Buffett Score', 'ROIC', 'Current Price']
    for c in first_cols:
        if c in cols:
            cols.remove(c)
    df = df[first_cols + cols]

    # Export to CSV
    df.to_csv(args.output, index=False)
    print(f"\nScan complete! Saved data for {len(df)} companies to {args.output}")
    
    # Print Top 10 Leaderboard
    print("\n--- TOP 10 BUFFETT SCORE LEADERBOARD ---")
    top_10 = df.head(10)
    for idx, row in top_10.iterrows():
        print(f"{row['Ticker']:<5} | Score: {row['Buffett Score']}/7 | ROIC: {row['ROIC']*100:5.1f}% | {row['Company Name'][:30]}")

if __name__ == "__main__":
    main()
