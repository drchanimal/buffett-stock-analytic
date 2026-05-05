# Standalone Value Investing Desktop Application

A Streamlit-based desktop application that acts as your AI Value Analyst, applying Warren Buffett-style investment principles (ROIC, Earnings Consistency, Debt Coverage, DCF Intrinsic Value) to any US ticker.

## Requirements

The app uses the following core libraries:
- `streamlit` for the UI
- `yfinance` for price, basic ratios, and historical shares outstanding
- `edgartools` for deep SEC EDGAR API fundamental parsing
- `pandas` & `numpy` for data manipulation

## Installation

1. Clone or navigate to this directory.
2. Provide a SEC EDGAR identity email in the `app.py` text input when you run it (or configure it securely).
3. (Optional but recommended) Create and activate a virtual environment:

```bash
python -m venv venv
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

4. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Running the Application

Run the application locally using Streamlit:

```bash
streamlit run app.py
```

## Running the S&P 500 Scanner

To run the standalone multithreaded scanner that evaluates all S&P 500 companies and generates a leaderboard CSV (`sp500_scan_results.csv` by default):

```bash
python scanner.py
```

You can customize the scan using command-line arguments:

```bash
python scanner.py --limit 10 --workers 5 --delay 0.1 --output results.csv
```

**Options:**
- `--limit`: Limit the number of tickers to scan (useful for testing). Default: 0 (scan all).
- `--workers`: Number of concurrent workers. Default: 3.
- `--delay`: Seconds to wait between requests to prevent API blocks. Default: 0.5.
- `--output`: Output CSV file name. Default: `sp500_scan_results.csv`.

## Features

1. **Buffett Scorecard:** Quick visual (Green/Yellow/Red) evaluation of fundamentals (ROIC, ROE, Margin, Debt, CAGR EPS).
2. **Intrinsic Value calculator:** Discounted Cash Flow (DCF) model where you can change the assumptions on the fly.
3. **Data Export:** Export the raw financial data generated into a CSV.
