import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import yfinance as yf
from fredapi import Fred
import traceback

# Set page configuration
st.set_page_config(page_title="Comprehensive Financial Dashboard", layout="wide")

# Function to log errors
def log_error(error):
    st.error(f"An error occurred: {str(error)}")
    st.error("Please try refreshing the page. If the problem persists, some data sources may be unavailable.")
    st.text("Traceback:")
    st.text(traceback.format_exc())

# Initialize FRED API client
@st.cache_resource
def init_fred_client():
    try:
        return Fred(api_key=st.secrets["fred_api_key"])
    except Exception as e:
        log_error(e)
        return None

# Fetch financial data (stocks, forex, and crypto)
@st.cache_data(ttl=3600)
def get_financial_data(symbols, start_date, end_date):
    try:
        data = yf.download(list(symbols.values()), start=start_date, end=end_date)['Close']
        data.columns = symbols.keys()
        data.index = data.index.tz_convert('UTC')
        return data
    except Exception as e:
        log_error(e)
        return None

# Fetch FRED data
@st.cache_data(ttl=3600)
def get_fred_data(fred, series_id, start_date, end_date):
    try:
        data = fred.get_series(series_id, start_date, end_date)
        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index)
        data.index = data.index.tz_localize('UTC', ambiguous='NaT', nonexistent='shift_forward')
        return data
    except Exception as e:
        log_error(e)
        return None

# Function to get multi-asset data
def get_multi_asset_data(fred, days=30):
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Financial data (stocks, forex, and crypto)
    status_text.text("Fetching financial data...")
    symbols = {
        'S&P 500': '^GSPC',
        'NASDAQ': '^IXIC',
        'EUR/USD': 'EURUSD=X',
        'GBP/USD': 'GBPUSD=X',
        'Bitcoin': 'BTC-USD',
        'Ethereum': 'ETH-USD'
    }
    financial_data = get_financial_data(symbols, start_date, end_date)
    progress_bar.progress(50)

    # FRED data
    status_text.text("Fetching economic indicators...")
    fred_series = {
        'US Unemployment Rate': 'UNRATE',
        'US Inflation Rate': 'T10YIE',
        'US GDP Growth': 'A191RL1Q225SBEA'
    }
    fred_data = pd.DataFrame({name: get_fred_data(fred, series_id, start_date, end_date) for name, series_id in fred_series.items()})
    progress_bar.progress(100)
    
    # Combine all data
    try:
        status_text.text("Combining data...")
        combined_data = pd.concat([financial_data, fred_data], axis=1)
        combined_data.index.name = 'date'
        status_text.text("Data fetching completed.")
        status_text.empty()
        progress_bar.empty()
        return combined_data.ffill().bfill()  # Forward and backward fill to handle any missing data
    except Exception as e:
        log_error(e)
        status_text.text("Error occurred while combining data.")
        return None

# Function to display the dashboard
def display_dashboard(data):
    if data is None or data.empty:
        st.error("No data available to display.")
        return

    # Resample data to daily frequency
    daily_data = data.resample('D').last()

    # Calculate percentage changes
    pct_change = daily_data.pct_change().mul(100)

    # Create tabs for different views
    tabs = st.tabs(["Overview", "Asset Comparison", "Economic Indicators"])

    with tabs[0]:
        st.header("Market Overview")
        col1, col2 = st.columns(2)

        # Latest values
        with col1:
            st.subheader("Latest Values")
            latest_values = daily_data.iloc[-1].dropna()
            for asset, value in latest_values.items():
                st.metric(asset, f"{value:.2f}", f"{pct_change.iloc[-1][asset]:.2f}%")

        # Heatmap of correlations
        with col2:
            st.subheader("Correlation Heatmap")
            corr_matrix = daily_data.pct_change().corr()
            fig = px.imshow(corr_matrix, text_auto=True, aspect="auto")
            st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        st.header("Asset Comparison")
        assets = st.multiselect("Select assets to compare", daily_data.columns.tolist(), default=daily_data.columns[:3].tolist())
        if assets:
            fig = px.line(daily_data[assets], title="Asset Price Comparison")
            st.plotly_chart(fig, use_container_width=True)

            # Normalized comparison
            st.subheader("Normalized Comparison (Start = 100)")
            normalized_data = daily_data[assets].div(daily_data[assets].iloc[0]).mul(100)
            fig_norm = px.line(normalized_data, title="Normalized Asset Comparison")
            st.plotly_chart(fig_norm, use_container_width=True)

    with tabs[2]:
        st.header("Economic Indicators")
        indicators = [col for col in daily_data.columns if col in ['US Unemployment Rate', 'US Inflation Rate', 'US GDP Growth']]
        for indicator in indicators:
            fig = px.line(daily_data[indicator], title=indicator)
            st.plotly_chart(fig, use_container_width=True)

# Main function to run the dashboard
def main():
    try:
        st.title("Comprehensive Financial Dashboard")

        # Sidebar for user inputs
        st.sidebar.header("Dashboard Settings")
        days = st.sidebar.slider("Number of days to analyze", 7, 365, 30)

        fred = init_fred_client()
        if fred is None:
            st.error("Failed to initialize FRED API client. Please check your API key and connection.")
            return

        data = get_multi_asset_data(fred, days)
        if data is None:
            st.error("Failed to fetch or process data. Please check the error messages above.")
            return

        display_dashboard(data)

        # Add a footer
        st.markdown(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        st.markdown("Data sources: FRED (Macroeconomic Indicators), Yahoo Finance (Stocks, Forex, Cryptocurrencies)")

    except Exception as e:
        log_error(e)
        st.error("An unexpected error occurred. Please check the error message and try again.")

if __name__ == "__main__":
    main()