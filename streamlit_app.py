import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import time

# Define EST timezone
est = pytz.timezone('US/Eastern')

# Function to format dates for API
def format_date_for_api(date, start=True):
    if start:
        return date.astimezone(est).strftime('%Y-%m-%dT00:00:01+00:00')
    else:
        return date.astimezone(est).strftime('%Y-%m-%dT23:59:59+00:00')

# Fetch call data from the API
@st.experimental_memo(ttl=10)  # Cache results and refresh every 10 seconds
def fetch_call_data(start_date, end_date, limit=1000):
    url = "https://api.bland.ai/v1/calls"
    headers = {"authorization": "sk-s3zix6yia4ew2w9ymga9v0jexcx0j0crqu0kuvzwqqhg3hj7z9tteiuv6i3rls5u69"}
    
    all_call_data = []
    next_from = None
    total_count = 0

    while True:
        querystring = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": str(limit),
        }
        if next_from:
            querystring["next_from"] = next_from
        
        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            data = response.json()
            total_count = data.get('total_count', 0)
            calls = data.get('calls', [])
            all_call_data.extend(calls)

            if 'next_from' in data and data['next_from']:
                next_from = data['next_from']
            else:
                break
        else:
            st.error(f"Failed to fetch data. Status: {response.status_code}")
            break

    return total_count, pd.DataFrame([{
        "Inbound Number": call["from"],
        "Call Duration (minutes)": call["call_length"],
        "Call Cost ($)": call["price"],
        "Recording URL": f'<a href="{call["recording_url"]}" target="_blank">Listen</a>' if call["recording_url"] else "No Recording"
    } for call in all_call_data])

# Default to 'Today'
today = datetime.now(est).date()
start_date = datetime.combine(today, datetime.min.time(), tzinfo=est)
end_date = datetime.combine(today, datetime.max.time(), tzinfo=est)

# Format dates for API
start_date_str = format_date_for_api(start_date, start=True)
end_date_str = format_date_for_api(end_date, start=False)

# Fetch data and display metrics
total_calls, df = fetch_call_data(start_date_str, end_date_str)

st.title("📞 Call Data Analysis")
st.metric("Total Calls", total_calls)

transferred_calls = df[df["Call Duration (minutes)"] > 1].shape[0]
converted_calls = df[df["Call Duration (minutes)"] > 30].shape[0]

transferred_percentage = (transferred_calls / total_calls) * 100 if total_calls > 0 else 0
converted_percentage = (converted_calls / transferred_calls) * 100 if transferred_calls > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("Total Calls", total_calls)
col2.metric(f"Transferred ({transferred_percentage:.2f}%)", transferred_calls)
col3.metric(f"Converted ({converted_percentage:.2f}%)", converted_calls)

with st.expander("Call Details"):
    df_html = df.to_html(escape=False, index=False)
    st.write(df_html, unsafe_allow_html=True)
