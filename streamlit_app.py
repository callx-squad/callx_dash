import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the API key from environment variables
API_KEY = os.getenv("API_KEY")

# Define EST timezone
est = pytz.timezone('US/Eastern')

def format_date_for_api(date, start=True):
    """Format dates to API-friendly format."""
    return date.astimezone(est).strftime('%Y-%m-%dT00:00:01+00:00' if start else '%Y-%m-%dT23:59:59+00:00')

@st.cache_data(ttl=10)
def fetch_call_data(start_date, end_date, limit=1000):
    url = "https://api.bland.ai/v1/calls"
    headers = {"authorization": API_KEY}

    all_call_data = []
    next_from = None

    while True:
        querystring = {"start_date": start_date, "end_date": end_date, "limit": str(limit)}
        if next_from:
            querystring["next_from"] = next_from

        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            data = response.json()
            all_call_data.extend(data.get('calls', []))
            next_from = data.get('next_from')
            if not next_from:
                break
        else:
            st.error(f"Failed to fetch data. Status: {response.status_code}")
            break

    return pd.DataFrame([{
        "Inbound Number": call.get("from"),
        "Call Date": call.get("created_at", "").split("T")[0],
        "Call Duration (minutes)": call.get("call_length", 0),
        "Call Cost ($)": call.get("price", 0.0),
        "Transferred": call.get("transferred_to") is not None,
        "Recording": f'<a href="{call.get("recording_url")}" target="_blank">Listen</a>'
                     if call.get("recording_url") else "No Recording"
    } for call in all_call_data])

# Display the logo
st.image("https://cdn.prod.website-files.com/667c3ac275caf73d90d821aa/66f5f57cd6e1727fa47a1fad_call_xlogo.png", width=200)

today, yesterday = datetime.now(est).date(), datetime.now(est).date() - timedelta(days=1)
last_7_days, last_30_days = today - timedelta(days=7), today - timedelta(days=30)

st.markdown("### Call Data")

option = st.selectbox("Select a time period:", ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "Custom Date Range"])

if option == "Today":
    start_date, end_date = datetime.combine(today, datetime.min.time(), tzinfo=est), datetime.combine(today, datetime.max.time(), tzinfo=est)
elif option == "Yesterday":
    start_date, end_date = datetime.combine(yesterday, datetime.min.time(), tzinfo=est), datetime.combine(yesterday, datetime.max.time(), tzinfo=est)
elif option == "Last 7 Days":
    start_date, end_date = datetime.combine(last_7_days, datetime.min.time(), tzinfo=est), datetime.combine(today, datetime.max.time(), tzinfo=est)
elif option == "Last 30 Days":
    start_date, end_date = datetime.combine(last_30_days, datetime.min.time(), tzinfo=est), datetime.combine(today, datetime.max.time(), tzinfo=est)
else:
    start_date, end_date = st.date_input("Start date", last_30_days), st.date_input("End date", today)
    if start_date > end_date:
        st.error("Start date must be before or equal to end date.")

start_date_str, end_date_str = format_date_for_api(start_date, True), format_date_for_api(end_date, False)

df = fetch_call_data(start_date_str, end_date_str)

if not df.empty:
    total_calls = df.shape[0]
    total_cost = df["Call Cost ($)"].sum()
    transferred_calls = df[df["Transferred"]].shape[0]
    converted_calls = df[df["Call Duration (minutes)"] > 30].shape[0]
    transferred_pct = (transferred_calls / total_calls) * 100 if total_calls else 0
    converted_pct = (converted_calls / transferred_calls) * 100 if transferred_calls else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Calls", total_calls)
    col2.metric(f"Transferred ({transferred_pct:.2f}%)", transferred_calls)
    col3.metric(f"Converted ({converted_pct:.2f}%)", converted_calls)
    st.metric("Total Call Cost ($)", f"${total_cost:.2f}")

    with st.expander("Call Details"):
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.write("No data available for the selected time period.")
