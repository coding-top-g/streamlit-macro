import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yfinance as yf
from pycoingecko import CoinGeckoAPI
from fredapi import Fred
import traceback

# Function to log errors
def log_error(error):
    st.error(f"An error occurred: {str(error)}")
    st.text("Traceback:")
    st.text(traceback.format_exc())

# Initialize API clients
try:
    st.write("Initializing API clients...")
    cg = CoinGeckoAPI()
    fred = Fred(api_key=st.secrets["fred_api_key"])
    st.write("API clients initialized successfully.")
except Exception as e:
    log_error(e)

# Function to get multi-asset data
def get_multi_asset_data(days=30):
    st.write("Fetching multi-asset data...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Stocks and Forex data from Yahoo Finance
    try:
        st.write("Fetching stock and forex data...")
        symbols = {
            'S&P 500': '^GSPC',
            'NASDAQ': '^IXIC',
            'EUR/USD': 'EURUSD=X',
            'GBP/USD': 'GBPUSD=X'
        }
        yf_data = yf.download(list(symbols.values()), start=start_date, end=end_date)['Close']
        yf_data.columns = symbols.keys()
        st.write("Stock and forex data fetched successfully.")
    except Exception as e:
        log_error(e)
        return None

    # Crypto data from CoinGecko
    try:
        st.write("Fetching crypto data...")
        btc_data = cg.get_coin_market_chart_range_by_id(id='bitcoin', vs_currency='usd', from_timestamp=int(start_date.timestamp()), to_timestamp=int(end_date.timestamp()))
        eth_data = cg.get_coin_market_chart_range_by_id(id='ethereum', vs_currency='usd', from_timestamp=int(start_date.timestamp()), to_timestamp=int(end_date.timestamp()))
        
        btc_df = pd.DataFrame(btc_data['prices'], columns=['timestamp', 'Bitcoin'])
        eth_df = pd.DataFrame(eth_data['prices'], columns=['timestamp', 'Ethereum'])
        btc_df['timestamp'] = pd.to_datetime(btc_df['timestamp'], unit='ms')
        eth_df['timestamp'] = pd.to_datetime(eth_df['timestamp'], unit='ms')
        
        crypto_df = pd.merge(btc_df, eth_df, on='timestamp', how='outer')
        crypto_df.set_index('timestamp', inplace=True)
        st.write("Crypto data fetched successfully.")
    except Exception as e:
        log_error(e)
        return None

    # FRED data
    try:
        st.write("Fetching FRED data...")
        fred_series = {
            'US Unemployment Rate': 'UNRATE',
            'US Inflation Rate': 'T10YIE',
            'US GDP Growth': 'A191RL1Q225SBEA'
        }
        fred_data = pd.DataFrame()
        for name, series_id in fred_series.items():
            series = fred.get_series(series_id, start_date, end_date)
            fred_data[name] = series
        st.write("FRED data fetched successfully.")
    except Exception as e:
        log_error(e)
        return None

    # Combine all data
    try:
        st.write("Combining all data...")
        combined_data = pd.concat([yf_data, crypto_df, fred_data], axis=1)
        combined_data.index.name = 'date'
        st.write("Data combined successfully.")
        return combined_data.ffill().bfill()  # Forward and backward fill to handle any missing data
    except Exception as e:
        log_error(e)
        return None

# Set page configuration
st.set_page_config(page_title="Comprehensive Financial Dashboard", layout="wide")

# Title
st.title("Comprehensive Financial Dashboard")

try:
    # Get data
    data = get_multi_asset_data()
    
    if data is not None:
        st.write("Data fetched successfully. Displaying visualizations...")
        
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

except Exception as e:
    log_error(e)

# Add a footer
st.markdown(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown("Data sources: FRED (Macroeconomic Indicators), Yahoo Finance (Stocks, Forex), CoinGecko (Cryptocurrencies)")