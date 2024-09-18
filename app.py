import streamlit as st
import pandas as pd
import plotly.express as px
from fredapi import Fred

# Initialize FRED API client
fred_api_key = st.secrets["fred_api_key"]
fred = Fred(api_key=fred_api_key)

# Set page configuration
st.set_page_config(page_title="Global Macro Indicators Dashboard", layout="wide")

# Title
st.title("Global Macro Indicators Dashboard")

# Sidebar
st.sidebar.header("Select Indicators")

# Define a list of indicators with their FRED series IDs
indicators = {
    "US GDP Growth Rate": "A191RL1Q225SBEA",
    "US Inflation Rate": "CPIAUCSL",
    "US Unemployment Rate": "UNRATE",
    "US 10-Year Treasury Yield": "DGS10",
    "Euro Area GDP Growth Rate": "CLVMNACSCAB1GQEA19",
    "Euro Area Inflation Rate": "CP0000EZ19M086NEST",
    "China GDP Growth Rate": "MKTGDPCNA646NWDB",
    "Global Economic Policy Uncertainty Index": "GEPUCURRENT"
}

# Allow user to select indicators
selected_indicators = st.sidebar.multiselect(
    "Choose indicators to display",
    list(indicators.keys()),
    default=list(indicators.keys())[:3]
)

# Main content
for indicator in selected_indicators:
    st.header(indicator)
    series_id = indicators[indicator]
    
    # Fetch data from FRED
    data = fred.get_series(series_id)
    df = pd.DataFrame(data).reset_index()
    df.columns = ['Date', 'Value']
    
    # Create a line chart using Plotly
    fig = px.line(df, x='Date', y='Value', title=indicator)
    st.plotly_chart(fig, use_container_width=True)
    
    # Display recent values
    st.subheader("Recent Values")
    st.dataframe(df.tail())

# Add a footer
st.markdown("---")
st.markdown("Data source: Federal Reserve Economic Data (FRED)")