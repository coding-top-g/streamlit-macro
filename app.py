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

# Set page configuration
st.set_page_config(page_title="Comprehensive Financial Dashboard", layout="wide")

# Function to log errors
def log_error(error):
    st.error(f"An error occurred: {str(error)}")
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

# Fetch crypto data with timeout
def get_crypto_data_with_timeout(cg, coin_id, start_timestamp, end_timestamp, timeout=10):
    def fetch_data():
        return cg.get_coin_market_chart_range_by_id(id=coin_id, vs_currency='usd', from_timestamp=start_timestamp, to_timestamp=end_timestamp)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(fetch_data)
        try:
            data = future.result(timeout=timeout)
            df = pd.DataFrame(data['prices'], columns=['timestamp', coin_id.capitalize()])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('timestamp', inplace=True)
            return df
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"CoinGecko API call for {coin_id} timed out after {timeout} seconds")

# Fetch crypto data wrapper
def get_crypto_data_wrapper(cg):
    @st.cache_data(ttl=3600)
    def get_crypto_data(coin_id, start_timestamp, end_timestamp):
        try:
            return get_crypto_data_with_timeout(cg, coin_id, start_timestamp, end_timestamp)
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
    progress_bar.progress(50)
    eth_data = get_crypto_data('ethereum', int(start_date.timestamp()), int(end_date.timestamp()))
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
        combined_data = pd.concat([yf_data, btc_data, eth_data, fred_data], axis=1)
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

# ... (rest of the code remains the same)

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