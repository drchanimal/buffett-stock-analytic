import streamlit as st
import pandas as pd
import yfinance as yf
from buffett_engine import perform_fundamental_analysis, calculate_intrinsic_value, resolve_ticker, calculate_fcf_cagr

@st.cache_data(ttl=3600)
def get_sidebar_fcf(ticker_val):
    """Silently fetch and calculate the historical FCF for the sidebar UI."""
    try:
        r_ticker = resolve_ticker(ticker_val)
        cf = yf.Ticker(r_ticker).cashflow
        if cf is not None and not cf.empty:
            return calculate_fcf_cagr(cf)
    except:
        pass
    return None

# Page Config
st.set_page_config(page_title="Buffett AI Analyst", layout="wide", page_icon="📈")

# Helper functions for UI coloring
def get_color(value, thresholds, reverse=False):
    """Return red, yellow, or green depending on thresholds.
       thresholds = (yellow_thresh, green_thresh)
       If reverse=False, higher is better. If reverse=True, lower is better.
    """
    y, g = thresholds
    if not reverse:
        if value >= g: return "green"
        if value >= y: return "goldenrod"
        return "red"
    else:
        if value <= g: return "green"
        if value <= y: return "goldenrod"
        return "red"

def styled_metric(label, value_str, color="white"):
    return f"""
    <div style="background-color: #1e1e1e; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        <p style="color: #888; margin: 0; font-size: 14px; font-weight: 600;">{label}</p>
        <p style="color: {color}; margin: 5px 0 0 0; font-size: 24px; font-weight: bold;">{value_str}</p>
    </div>
    """

# Sidebar Inputs
st.sidebar.title("Value Analyst Setup")
st.sidebar.markdown("Provide your settings below:")


ticker_input = st.sidebar.text_input("Stock Ticker", value="AAPL")

st.sidebar.markdown("---")
st.sidebar.subheader("DCF Assumptions")
growth_rate = st.sidebar.slider("Expected FCF Growth Rate (%)", min_value=0.0, max_value=50.0, value=10.0, step=0.5) / 100.0

# Fetch and display the historical FCF directly inside the sidebar
hist_fcf_val = get_sidebar_fcf(ticker_input)
if hist_fcf_val is not None:
    st.sidebar.caption(f"*(Calculated Historical FCF Growth: **{hist_fcf_val * 100:.1f}%**)*")

use_hist_fcf = st.sidebar.checkbox("Override with Historical FCF Growth", value=False, help="Instead of the slider, force the DCF model to project using the company's past 4-year FCF CAGR.")
discount_rate = st.sidebar.slider("Discount Rate (%)", min_value=5.0, max_value=20.0, value=10.0, step=0.5) / 100.0
terminal_rate = st.sidebar.slider("Terminal Growth Rate (%)", min_value=0.0, max_value=5.0, value=2.5, step=0.1) / 100.0
margin_of_safety_target = st.sidebar.slider("Target Margin of Safety (%)", min_value=10, max_value=50, value=20, step=5) / 100.0

analyze_btn = st.sidebar.button("Analyze Stock")

# Main Content
tab1, tab2 = st.tabs(["Single Stock Analyst", "S&P 500 Leaderboard"])

with tab1:
    # Main Content
    st.title(f"Warren Buffett-Style Analysis: {ticker_input.upper()}")
    if analyze_btn or ticker_input:
        with st.spinner(f"Analyzing {ticker_input.upper()}..."):
            try:
                # Resolve the input (which might be a company name like 'Apple') into a stock ticker
                resolved_ticker = resolve_ticker(ticker_input)
            
                if resolved_ticker.upper() != ticker_input.upper():
                    st.info(f"Resolved **'{ticker_input}'** to ticker **{resolved_ticker.upper()}**")
                
                results = perform_fundamental_analysis(resolved_ticker)
            
                # Additional Intrinsic Value calculation relying on user inputs
                fcf = results["Latest FCF"]
                shares_out = results["Shares Outstanding"]
                current_price = results["Current Price"]
            
                # Decide which growth rate to use for the DCF
                applied_growth = results["FCF CAGR (Historical)"] if use_hist_fcf else growth_rate
            
                intrinsic_val = calculate_intrinsic_value(
                    fcf=fcf,
                    growth_rate=applied_growth,
                    discount_rate=discount_rate,
                    terminal_rate=terminal_rate,
                    shares_out=shares_out
                )
            
                margin_of_safety_actual = (intrinsic_val - current_price) / intrinsic_val if intrinsic_val > 0 else 0
                buy_below_price = intrinsic_val * (1 - margin_of_safety_target)
            
                # Combine all data for reporting
                results["Calculated Intrinsic Value"] = intrinsic_val
                results["Margin of Safety (%)"] = margin_of_safety_actual
                results["Buy Target Price"] = buy_below_price
            
                # Top Banner
                st.markdown(f"### {results['Company Name']} ({results['Industry']} | {results['Sector']})")
                st.caption(f"Current Price: ${current_price:,.2f} | Market Cap: ${(results['Market Cap']/1e9):,.2f}B")
            
                st.markdown("---")
                st.subheader("Buffett Scorecard")
            
                # Scorecard mapping
                col1, col2, col3, col4 = st.columns(4)
            
                # ROIC: >15% is green, >10% yellow
                roic = results["ROIC"] * 100
                c_roic = get_color(roic, (10, 15))
                col1.markdown(styled_metric("ROIC (5Y)", f"{roic:.1f}%", c_roic), unsafe_allow_html=True)
            
                # ROE: >15% is green, >10% yellow
                roe = results["ROE"] * 100
                c_roe = get_color(roe, (10, 15))
                col2.markdown(styled_metric("ROE", f"{roe:.1f}%", c_roe), unsafe_allow_html=True)
            
                # Debt to Equity: <0.5 green, <1.0 yellow
                d2e = results["Debt to Equity"]
                c_d2e = get_color(d2e, (1.0, 0.5), reverse=True)
                d2e_str = "N/A" if d2e == float('inf') else f"{d2e:.2f}"
                col3.markdown(styled_metric("Debt to Equity", d2e_str, c_d2e), unsafe_allow_html=True)
            
                # Years to Pay Off Debt: <3 green, <5 yellow
                y2p = results["Years to Pay Off Debt"]
                c_y2p = get_color(y2p, (5.0, 3.0), reverse=True)
                y2p_str = "N/A" if y2p == float('inf') or y2p < 0 else f"{y2p:.1f}x"
                col4.markdown(styled_metric("Years to Payoff", y2p_str, c_y2p), unsafe_allow_html=True)
            
                st.write("")
                col5, col6, col7 = st.columns(3)
            
                # EPS CAGR: >10% green, >5% yellow
                eps_cagr = results["EPS CAGR (Historical)"] * 100
                c_eps = get_color(eps_cagr, (5, 10))
                col5.markdown(styled_metric("EPS Growth (CAGR)", f"{eps_cagr:.1f}%", c_eps), unsafe_allow_html=True)
            
                # FCF CAGR: >10% green, >5% yellow
                fcf_cagr = results["FCF CAGR (Historical)"] * 100
                c_fcf = get_color(fcf_cagr, (5, 10))
                col6.markdown(styled_metric("FCF Growth (CAGR)", f"{fcf_cagr:.1f}%", c_fcf), unsafe_allow_html=True)
            
                # Gross Margin: >40% green, >20% yellow
                gm = results["Gross Margin"] * 100
                c_gm = get_color(gm, (20, 40))
                col7.markdown(styled_metric("Gross Margin", f"{gm:.1f}%", c_gm), unsafe_allow_html=True)
            
                st.markdown("---")
                st.subheader("Valuation & Margin of Safety")
            
                vc1, vc2, vc3 = st.columns(3)
                vc1.metric("Current Price", f"${current_price:,.2f}")
                vc2.metric("Intrinsic Value (DCF)", f"${intrinsic_val:,.2f}", 
                           delta=f"{margin_of_safety_actual*100:.1f}% MoS",
                           delta_color="normal" if margin_of_safety_actual > 0 else "inverse")
                vc3.metric(f"Target Entry (<{margin_of_safety_target*100:.0f}% MoS)", f"${buy_below_price:,.2f}")
            
                # Conclusion banner
                if current_price <= buy_below_price:
                    st.success(f"🟢 **BUY SIGNAL:** At \${current_price:,.2f}, {ticker_input.upper()} provides your target Margin of Safety compared to the calculated intrinsic value of \${intrinsic_val:,.2f}.")
                elif current_price <= intrinsic_val:
                    st.warning(f"🟡 **HOLD SIGNAL:** {ticker_input.upper()} is trading below intrinsic value, but does not meet your {margin_of_safety_target*100:.0f}% Margin of Safety threshold.")
                else:
                    st.error(f"🔴 **OVERVALUED:** {ticker_input.upper()} is trading at a premium to its calculated intrinsic value of \${intrinsic_val:,.2f}.")

                st.markdown("---")
                st.subheader("Data Export")
            
                # Create DF for export
                df_export = pd.DataFrame([results])
                csv = df_export.to_csv(index=False).encode('utf-8')
            
                st.download_button(
                    label="Download Analysis as CSV",
                    data=csv,
                    file_name=f"{ticker_input.lower()}_buffett_analysis.csv",
                    mime="text/csv",
                )
            
            except Exception as e:
                st.error(f"An error occurred while analyzing {ticker_input}: {e}")
                st.exception(e)


with tab2:
    st.header("S&P 500 Buffett Score Leaderboard")
    import os as _os
    if _os.path.exists("sp500_scan_results.csv"):
        st.success("Scanner data loaded from local cache.")
        df = pd.read_csv("sp500_scan_results.csv")
        # Apply some light styling
        st.dataframe(df.style.background_gradient(subset=["Buffett Score", "ROIC", "ROE"], cmap="Greens"), use_container_width=True, height=600)
    else:
        st.warning("No scan results found. Please run `python scanner.py` in your terminal to generate the S&P 500 scan.")
