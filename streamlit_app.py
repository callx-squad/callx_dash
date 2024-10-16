import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# Helper function to fetch data from the API with pagination
def fetch_call_data_paginated(start_date, end_date, limit=1000):
    url = "https://api.bland.ai/v1/calls"
    headers = {"authorization": "sk-s3zix6yia4ew2w9ymga9v0jexcx0j0crqu0kuvzwqqhg3hj7z9tteiuv6i3rls5u69"}
    
    all_call_data = []
    next_from = None  # Pagination variable (check if your API uses this or next_token)

    while True:
        querystring = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": str(limit),
        }
        
        # Add the "from" parameter for pagination if it exists
        if next_from:
            querystring["from"] = next_from
        
        response = requests.get(url, headers=headers, params=querystring)
        
        if response.status_code == 200:
            data = response.json()
            calls = data['calls']
            all_call_data.extend(calls)  # Append calls to the list

            # Use pagination to get the next batch
            if len(calls) < limit:
                break
            next_from = calls[-1]["c_id"]  # Check if the API provides an actual "next_token" for pagination
        else:
            st.error(f"Failed to fetch data from the API. Status code: {response.status_code}")
            break
    
    # Create a DataFrame from the collected call data
    if all_call_data:
        return pd.DataFrame([{
            "Call ID": call["c_id"],
            "Created At": call["created_at"],
            "Call Length (minutes)": call["call_length"],
            "Price ($)": call["price"],
            "Status": call["status"]
        } for call in all_call_data])
    else:
        return pd.DataFrame()

# Define time periods and Streamlit UI
today = datetime.today().date()
yesterday = today - timedelta(days=1)
last_7_days = today - timedelta(days=7)
last_30_days = today - timedelta(days=30)

st.title("📞 Call Data Analysis")

option = st.selectbox(
    "Select a time period:",
    ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "Custom Date Range"]
)

# Set the date range based on user selection
if option == "Today":
    start_date = today
    end_date = today
elif option == "Yesterday":
    start_date = yesterday
    end_date = yesterday
elif option == "Last 7 Days":
    start_date = last_7_days
    end_date = today
elif option == "Last 30 Days":
    start_date = last_30_days
    end_date = today
else:
    start_date = st.date_input("Start date", last_30_days)
    end_date = st.date_input("End date", today)
    if start_date > end_date:
        st.error("Start date must be before or equal to end date.")

# Convert dates to string format for the API call
start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")

# Fetch the data using the paginated API call
df = fetch_call_data_paginated(start_date_str, end_date_str)

if not df.empty:
    total_calls = df.shape[0]
    total_cost = df["Price ($)"].sum()
    
    st.metric("Total Calls", total_calls)
    st.metric("Total Call Cost ($)", f"${total_cost:.2f}")
    st.dataframe(df)
else:
    st.write("No data available for the selected time period.")
