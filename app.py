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

# Fetch crypto data
def get_crypto_data_wrapper(cg):
    @st.cache_data(ttl=3600)
    def get_crypto_data(coin_id, start_timestamp, end_timestamp):
        try:
            data = cg.get_coin_market_chart_range_by_id(id=coin_id, vs_currency='usd', from_timestamp=start_timestamp, to_timestamp=end_timestamp)
            df = pd.DataFrame(data['prices'], columns=['timestamp', coin_id.capitalize()])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('timestamp', inplace=True)
            return df
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
            data.index = data.index.tz_localize('UTC')
            return data
        except Exception as e:
            log_error(e)
            return None
    return get_fred_data

# Function to get multi-asset data
def get_multi_asset_data(cg, fred, days=30):
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    # Stocks and Forex data
    symbols = {
        'S&P 500': '^GSPC',
        'NASDAQ': '^IXIC',
        'EUR/USD': 'EURUSD=X',
        'GBP/USD': 'GBPUSD=X'
    }
    yf_data = get_stock_data(symbols, start_date, end_date)
    
    # Crypto data
    get_crypto_data = get_crypto_data_wrapper(cg)
    btc_data = get_crypto_data('bitcoin', int(start_date.timestamp()), int(end_date.timestamp()))
    eth_data = get_crypto_data('ethereum', int(start_date.timestamp()), int(end_date.timestamp()))
    
    # FRED data
    get_fred_data = get_fred_data_wrapper(fred)
    fred_series = {
        'US Unemployment Rate': 'UNRATE',
        'US Inflation Rate': 'T10YIE',
        'US GDP Growth': 'A191RL1Q225SBEA'
    }
    fred_data = pd.DataFrame({name: get_fred_data(series_id, start_date, end_date) for name, series_id in fred_series.items()})
    
    # Combine all data
    try:
        combined_data = pd.concat([yf_data, btc_data, eth_data, fred_data], axis=1)
        combined_data.index.name = 'date'
        return combined_data.ffill().bfill()  # Forward and backward fill to handle any missing data
    except Exception as e:
        log_error(e)
        return None

# Function to create and display visualizations
def display_dashboard(data):
    if data is not None:
        # Calculate correlations
        correlations = data.pct_change().corr()

        # Create layout
        col1, col2 = st.columns([3, 2])

        with col1:
            # Correlation Heatmap
            st.subheader("Asset and Economic Indicator Correlation Heatmap")
            fig = px.imshow(correlations, 
                            x=correlations.columns, 
                            y=correlations.columns, 
                            color_continuous_scale='RdBu_r', 
                            zmin=-1, zmax=1)
            fig.update_layout(height=500, width=700, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Key Metrics
            st.subheader("Key Metrics (30-day change)")
            for asset in data.columns:
                change = (data[asset].iloc[-1] - data[asset].iloc[0]) / data[asset].iloc[0] * 100
                st.metric(asset, f"{data[asset].iloc[-1]:.2f}", f"{change:.2f}%")

        # Multi-asset chart
        st.subheader("Multi-Asset and Economic Indicator Movement (Normalized)")
        normalized_data = data / data.iloc[0] * 100
        fig = px.line(normalized_data, x=normalized_data.index, y=normalized_data.columns)
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

        # Volatility comparison
        st.subheader("30-Day Rolling Volatility")
        volatility = data.pct_change().rolling(window=30).std() * np.sqrt(252) * 100  # Annualized
        fig = px.line(volatility, x=volatility.index, y=volatility.columns)
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Failed to fetch data. Please check the error messages above.")

# Main function to run the dashboard
def main():
    st.title("Comprehensive Financial Dashboard")

    # Sidebar for user inputs
    st.sidebar.header("Dashboard Settings")
    days = st.sidebar.slider("Number of days to analyze", 7, 365, 30)

    cg, fred = init_api_clients()
    if cg is not None and fred is not None:
        data = get_multi_asset_data(cg, fred, days)
        display_dashboard(data)
    else:
        st.error("Failed to initialize API clients. Please check your API keys and connections.")

    # Add a footer
    st.markdown(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.markdown("Data sources: FRED (Macroeconomic Indicators), Yahoo Finance (Stocks, Forex), CoinGecko (Cryptocurrencies)")

if __name__ == "__main__":
    main()