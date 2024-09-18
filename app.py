import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pycoingecko import CoinGeckoAPI
from fredapi import Fred
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.foreignexchange import ForeignExchange
from datetime import datetime, timedelta

# Initialize API clients
cg = CoinGeckoAPI()
fred = Fred(api_key=st.secrets["fred_api_key"])
alpha_vantage = TimeSeries(key=st.secrets["alpha_vantage_api_key"])
fx = ForeignExchange(key=st.secrets["alpha_vantage_api_key"])

# Set page configuration
st.set_page_config(page_title="Global Market Correlation Dashboard", layout="wide")

# Title
st.title("Global Market Correlation Dashboard")

# Function to get data for multiple assets
def get_multi_asset_data(days=30):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Stocks (S&P 500, NASDAQ, DOW)
    stock_symbols = ['SPY', 'QQQ', 'DIA']
    stock_data = {}
    for symbol in stock_symbols:
        data, _ = alpha_vantage.get_daily(symbol=symbol, outputsize='full')
        df = pd.DataFrame(data).T
        df.index = pd.to_datetime(df.index)
        df = df[df.index >= start_date]
        stock_data[symbol] = df['4. close'].astype(float)
    
    # Crypto (Bitcoin, Ethereum)
    btc_data = cg.get_coin_market_chart_range_by_id(id='bitcoin', vs_currency='usd', from_timestamp=int(start_date.timestamp()), to_timestamp=int(end_date.timestamp()))
    eth_data = cg.get_coin_market_chart_range_by_id(id='ethereum', vs_currency='usd', from_timestamp=int(start_date.timestamp()), to_timestamp=int(end_date.timestamp()))
    
    # Forex (EUR/USD, GBP/USD)
    eurusd, _ = fx.get_currency_exchange_daily('EUR', 'USD', outputsize='full')
    gbpusd, _ = fx.get_currency_exchange_daily('GBP', 'USD', outputsize='full')
    
    # Combine all data
    combined_data = pd.DataFrame({
        'S&P 500': stock_data['SPY'],
        'NASDAQ': stock_data['QQQ'],
        'DOW': stock_data['DIA'],
        'Bitcoin': pd.DataFrame(btc_data['prices'], columns=['timestamp', 'price']).set_index('timestamp')['price'],
        'Ethereum': pd.DataFrame(eth_data['prices'], columns=['timestamp', 'price']).set_index('timestamp')['price'],
        'EUR/USD': pd.DataFrame(eurusd).T['4. close'].astype(float),
        'GBP/USD': pd.DataFrame(gbpusd).T['4. close'].astype(float)
    })
    
    combined_data.index = pd.to_datetime(combined_data.index, unit='ms')
    combined_data = combined_data.sort_index().ffill()
    return combined_data

# Get data
data = get_multi_asset_data()

# Calculate correlations
correlations = data.pct_change().corr()

# Create layout
col1, col2 = st.columns([3, 2])

with col1:
    # Correlation Heatmap
    st.subheader("Asset Correlation Heatmap")
    fig = px.imshow(correlations, 
                    x=correlations.columns, 
                    y=correlations.columns, 
                    color_continuous_scale='RdBu_r', 
                    zmin=-1, zmax=1)
    fig.update_layout(height=400, width=600, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Key Metrics
    st.subheader("Key Metrics (30-day change)")
    for asset in data.columns:
        change = (data[asset].iloc[-1] - data[asset].iloc[0]) / data[asset].iloc[0] * 100
        st.metric(asset, f"{data[asset].iloc[-1]:.2f}", f"{change:.2f}%")

# Multi-asset chart
st.subheader("Multi-Asset Price Movement (Normalized)")
normalized_data = data / data.iloc[0] * 100
fig = px.line(normalized_data, x=normalized_data.index, y=normalized_data.columns)
fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig, use_container_width=True)

# Volatility comparison
st.subheader("30-Day Rolling Volatility")
volatility = data.pct_change().rolling(window=30).std() * np.sqrt(252) * 100  # Annualized
fig = px.line(volatility, x=volatility.index, y=volatility.columns)
fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig, use_container_width=True)

# Add a footer
st.markdown(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown("Data sources: FRED, CoinGecko, Alpha Vantage")