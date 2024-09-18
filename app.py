import streamlit as st
import pandas as pd
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
st.set_page_config(page_title="Comprehensive Financial Dashboard", layout="wide")

# Title
st.title("Comprehensive Financial Dashboard")

# Function to get historical crypto data
def get_crypto_historical_data(coin_id, days):
    data = cg.get_coin_market_chart_by_id(id=coin_id, vs_currency='usd', days=days)
    df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Function to create price chart
def create_price_chart(df, name, title):
    fig = px.line(df, x='date', y='price', title=f"{title} ({name})")
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
    return fig

# Macro Indicators
st.header("Macro Indicators")
macro_indicators = {
    "US GDP Growth Rate": "A191RL1Q225SBEA",
    "US Inflation Rate": "CPIAUCSL",
    "US Unemployment Rate": "UNRATE",
}

col1, col2, col3 = st.columns(3)
for i, (name, series_id) in enumerate(macro_indicators.items()):
    data = fred.get_series(series_id)
    latest_value = data.iloc[-1]
    previous_value = data.iloc[-2]
    change = latest_value - previous_value
    col = [col1, col2, col3][i]
    col.metric(name, f"{latest_value:.2f}", f"{change:.2f}")

# Crypto Section
st.header("Cryptocurrency Market")
top_coins = cg.get_coins_markets(vs_currency='usd', order='market_cap_desc', per_page=5, page=1)

# Market Overview
st.subheader("Top 5 Cryptocurrencies")
market_data = pd.DataFrame(top_coins)[['name', 'current_price', 'market_cap', 'price_change_percentage_24h']]
market_data.columns = ['Name', 'Price (USD)', 'Market Cap (USD)', '24h Change (%)']
st.dataframe(market_data.set_index('Name'), use_container_width=True)

# Bitcoin Price Chart
btc_data = get_crypto_historical_data('bitcoin', 30)
st.plotly_chart(create_price_chart(btc_data, 'Bitcoin', 'Price Last 30 Days'), use_container_width=True)

# Stock Market Section
st.header("Stock Market")
stocks = ['AAPL', 'GOOGL', 'MSFT']
stock_data = {}

for symbol in stocks:
    data, _ = alpha_vantage.get_daily(symbol=symbol, outputsize='compact')
    df = pd.DataFrame(data).T
    df.index = pd.to_datetime(df.index)
    df['4. close'] = df['4. close'].astype(float)
    stock_data[symbol] = df

col1, col2, col3 = st.columns(3)
for i, (symbol, data) in enumerate(stock_data.items()):
    latest_price = data['4. close'].iloc[-1]
    prev_price = data['4. close'].iloc[-2]
    change = (latest_price - prev_price) / prev_price * 100
    col = [col1, col2, col3][i]
    col.metric(symbol, f"${latest_price:.2f}", f"{change:.2f}%")

# S&P 500 Chart
sp500, _ = alpha_vantage.get_daily(symbol='SPY', outputsize='compact')
sp500_df = pd.DataFrame(sp500).T
sp500_df.index = pd.to_datetime(sp500_df.index)
sp500_df['4. close'] = sp500_df['4. close'].astype(float)
st.plotly_chart(create_price_chart(sp500_df.reset_index().rename(columns={'index': 'date', '4. close': 'price'}), 'S&P 500', 'Price Last 100 Days'), use_container_width=True)

# Forex Section
st.header("Forex")
currency_pairs = ['EURUSD', 'GBPUSD', 'USDJPY']

col1, col2, col3 = st.columns(3)
for i, pair in enumerate(currency_pairs):
    data, _ = fx.get_currency_exchange_rate(from_currency=pair[:3], to_currency=pair[3:])
    rate = float(data['5. Exchange Rate'])
    col = [col1, col2, col3][i]
    col.metric(pair, f"{rate:.4f}")

# Add a footer
st.markdown("---")
st.markdown("Data sources: FRED, CoinGecko, Alpha Vantage")
st.markdown(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")