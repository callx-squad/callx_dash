import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz  # Ensure this is installed with: pip install pytz

# Define EST timezone
est = pytz.timezone('US/Eastern')

# Function to format the dates in ISO 8601 with timezone (EST)
def format_date_for_api(date, start=True):
    if start:
        return date.astimezone(est).strftime('%Y-%m-%dT00:00:01+00:00')
    else:
        return date.astimezone(est).strftime('%Y-%m-%dT23:59:59+00:00')

# Display the header image from a URL
image_url = "https://cdn.prod.website-files.com/667c3ac275caf73d90d821aa/66f5f57cd6e1727fa47a1fad_call_xlogo.png"
st.image(image_url, width=200)

# Helper function to fetch data from the API with pagination
def fetch_call_data_paginated(start_date, end_date, limit=1000):
    url = "https://api.bland.ai/v1/calls"
    headers = {"authorization": "sk-s3zix6yia4ew2w9ymga9v0jexcx0j0crqu0kuvzwqqhg3hj7z9tteiuv6i3rls5u69"}
    
    all_call_data = []
    next_from = None

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
            calls = data['calls']
            all_call_data.extend(calls)

            if 'next_from' in data and data['next_from']:
                next_from = data['next_from']
            else:
                break
        else:
            st.error(f"Failed to fetch data from the API. Status code: {response.status_code}")
            break
    
    if all_call_data:
        return pd.DataFrame([{
            "Inbound Number": call["from"],
            "Call Duration (minutes)": call["call_length"],
            "Call Cost ($)": call["price"],
            "Recording URL": f'<a href="{call["recording_url"]}" target="_blank">Listen</a>' if call["recording_url"] else "No Recording"
        } for call in all_call_data])
    else:
        return pd.DataFrame()

# Define time periods and Streamlit UI
today = datetime.now(est).date()
yesterday = today - timedelta(days=1)
last_7_days = today - timedelta(days=7)
last_30_days = today - timedelta(days=30)

st.title("📞 Call Data Analysis")

option = st.selectbox(
    "Select a time period:",
    ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "Custom Date Range"]
)

# Determine the start and end date for each option
if option == "Today":
    start_date = datetime.combine(today, datetime.min.time(), tzinfo=est)
    end_date = datetime.combine(today, datetime.max.time(), tzinfo=est)
elif option == "Yesterday":
    start_date = datetime.combine(yesterday, datetime.min.time(), tzinfo=est)
    end_date = datetime.combine(yesterday, datetime.max.time(), tzinfo=est)
elif option == "Last 7 Days":
    start_date = datetime.combine(last_7_days, datetime.min.time(), tzinfo=est)
    end_date = datetime.combine(today, datetime.max.time(), tzinfo=est)
elif option == "Last 30 Days":
    start_date = datetime.combine(last_30_days, datetime.min.time(), tzinfo=est)
    end_date = datetime.combine(today, datetime.max.time(), tzinfo=est)
else:
    start_date = st.date_input("Start date", last_30_days)
    end_date = st.date_input("End date", today)
    if start_date > end_date:
        st.error("Start date must be before or equal to end date.")

# Format dates for API
start_date_str = format_date_for_api(start_date, start=True)
end_date_str = format_date_for_api(end_date, start=False)

# Fetch the data using the paginated API call
df = fetch_call_data_paginated(start_date_str, end_date_str)

if not df.empty:
    total_calls = df.shape[0]
    total_cost = df["Call Cost ($)"].sum()
    
    # Calculate transferred calls (over 60 seconds) and converted calls (over 30 minutes)
    transferred_calls = df[df["Call Duration (minutes)"] > 1].shape[0]
    converted_calls = df[df["Call Duration (minutes)"] > 30].shape[0]
    
    # Calculate percentages
    transferred_percentage = (transferred_calls / total_calls) * 100 if total_calls > 0 else 0
    converted_percentage = (converted_calls / transferred_calls) * 100 if transferred_calls > 0 else 0
    
    # Create three columns for metrics
    col1, col2, col3 = st.columns(3)

    # Display metrics in each column with percentages
    col1.metric("Total Calls", total_calls)
    col2.metric(f"Transferred ({transferred_percentage:.2f}%)", transferred_calls)
    col3.metric(f"Converted ({converted_percentage:.2f}%)", converted_calls)
    
    st.metric("Total Call Cost ($)", f"${total_cost:.2f}")
    
    # Display the table in an expander (dropdown)
    with st.expander("Call Details"):
        df_html = df.to_html(escape=False, index=False)
        st.write(df_html, unsafe_allow_html=True)
else:
    st.write("No data available for the selected time period.")
