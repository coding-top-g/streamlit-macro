import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import yfinance as yf
from pycoingecko import CoinGeckoAPI
from fredapi import Fred
import traceback
import concurrent.futures
import time
import random

# Set page configuration
st.set_page_config(page_title="Comprehensive Financial Dashboard", layout="wide")

# Function to log errors
def log_error(error):
    st.error(f"An error occurred: {str(error)}")
    st.error("Please try refreshing the page. If the problem persists, some data sources may be unavailable.")
    st.text("Traceback:")
    st.text(traceback.format_exc())

# Initialize API clients
@st.cache_resource
def init_api_clients():
    try:
        cg = CoinGeckoAPI()
        fred = Fred(api_key=st.secrets["fred_api_key"])
        return cg, fred
    except Exception as e:
        log_error(e)
        return None, None

# Fetch stock data
@st.cache_data(ttl=3600)
def get_stock_data(symbols, start_date, end_date):
    try:
        data = yf.download(list(symbols.values()), start=start_date, end=end_date)['Close']
        data.columns = symbols.keys()
        data.index = data.index.tz_convert('UTC')
        return data
    except Exception as e:
        log_error(e)
        return None

# Fetch crypto data with timeout and retry
def get_crypto_data_with_retry(cg, coin_id, start_timestamp, end_timestamp, max_retries=3, base_timeout=15):
    def fetch_data():
        return cg.get_coin_market_chart_range_by_id(id=coin_id, vs_currency='usd', from_timestamp=start_timestamp, to_timestamp=end_timestamp)

    for attempt in range(max_retries):
        timeout = base_timeout * (2 ** attempt)  # Exponential backoff
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(fetch_data)
                data = future.result(timeout=timeout)
                df = pd.DataFrame(data['prices'], columns=['timestamp', coin_id.capitalize()])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                df.set_index('timestamp', inplace=True)
                return df
        except concurrent.futures.TimeoutError:
            if attempt < max_retries - 1:
                st.warning(f"CoinGecko API call for {coin_id} timed out after {timeout} seconds. Retrying... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(random.uniform(1, 3))  # Random delay before retry
            else:
                raise TimeoutError(f"CoinGecko API call for {coin_id} timed out after {max_retries} attempts")
        except Exception as e:
            raise e

# Fetch crypto data wrapper
def get_crypto_data_wrapper(cg):
    @st.cache_data(ttl=3600)
    def get_crypto_data(coin_id, start_timestamp, end_timestamp):
        try:
            return get_crypto_data_with_retry(cg, coin_id, start_timestamp, end_timestamp)
        except Exception as e:
            log_error(e)
            return None
    return get_crypto_data

# Fetch FRED data
def get_fred_data_wrapper(fred):
    @st.cache_data(ttl=3600)
    def get_fred_data(series_id, start_date, end_date):
        try:
            data = fred.get_series(series_id, start_date, end_date)
            if not isinstance(data.index, pd.DatetimeIndex):
                data.index = pd.to_datetime(data.index)
            data.index = data.index.tz_localize('UTC', ambiguous='NaT', nonexistent='shift_forward')
            return data
        except Exception as e:
            log_error(e)
            return None
    return get_fred_data

# Function to get multi-asset data
def get_multi_asset_data(cg, fred, days=30):
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Stocks and Forex data
    status_text.text("Fetching stock and forex data...")
    symbols = {
        'S&P 500': '^GSPC',
        'NASDAQ': '^IXIC',
        'EUR/USD': 'EURUSD=X',
        'GBP/USD': 'GBPUSD=X'
    }
    yf_data = get_stock_data(symbols, start_date, end_date)
    progress_bar.progress(25)

    # Crypto data
    status_text.text("Fetching cryptocurrency data...")
    get_crypto_data = get_crypto_data_wrapper(cg)
    btc_data = get_crypto_data('bitcoin', int(start_date.timestamp()), int(end_date.timestamp()))
    if btc_data is None:
        st.error("Failed to fetch Bitcoin data. Skipping...")
    else:
        progress_bar.progress(50)
    
    eth_data = get_crypto_data('ethereum', int(start_date.timestamp()), int(end_date.timestamp()))
    if eth_data is None:
        st.error("Failed to fetch Ethereum data. Skipping...")
    else:
        progress_bar.progress(75)
    
    # FRED data
    status_text.text("Fetching economic indicators...")
    get_fred_data = get_fred_data_wrapper(fred)
    fred_series = {
        'US Unemployment Rate': 'UNRATE',
        'US Inflation Rate': 'T10YIE',
        'US GDP Growth': 'A191RL1Q225SBEA'
    }
    fred_data = pd.DataFrame({name: get_fred_data(series_id, start_date, end_date) for name, series_id in fred_series.items()})
    progress_bar.progress(100)
    
    # Combine all data
    try:
        status_text.text("Combining data...")
        data_frames = [df for df in [yf_data, btc_data, eth_data, fred_data] if df is not None]
        if not data_frames:
            raise ValueError("No data available to combine")
        combined_data = pd.concat(data_frames, axis=1)
        combined_data.index.name = 'date'
        status_text.text("Data fetching completed.")
        time.sleep(1)  # Give user a moment to see the completion message
        status_text.empty()
        progress_bar.empty()
        return combined_data.ffill().bfill()  # Forward and backward fill to handle any missing data
    except Exception as e:
        log_error(e)
        status_text.text("Error occurred while combining data.")
        return None

# Function to display the dashboard
def display_dashboard(data):
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
    st.title("Comprehensive Financial Dashboard")

    # Sidebar for user inputs
    st.sidebar.header("Dashboard Settings")
    days = st.sidebar.slider("Number of days to analyze", 7, 365, 30)

    cg, fred = init_api_clients()
    if cg is not None and fred is not None:
        data = get_multi_asset_data(cg, fred, days)
        if data is not None:
            display_dashboard(data)
        else:
            st.error("Failed to fetch or process data. Please check the error messages above.")
    else:
        st.error("Failed to initialize API clients. Please check your API keys and connections.")

    # Add a footer
    st.markdown(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.markdown("Data sources: FRED (Macroeconomic Indicators), Yahoo Finance (Stocks, Forex), CoinGecko (Cryptocurrencies)")

if __name__ == "__main__":
    main()