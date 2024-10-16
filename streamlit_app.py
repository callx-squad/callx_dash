import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
import time
from streamlit.components.v1 import html

# Get the API key from Streamlit secrets
API_KEY = st.secrets["API_KEY"]

if not API_KEY:
    st.error("API_KEY is not set. Please set it in your Streamlit secrets.")
    st.stop()

# Define EST timezone
est = pytz.timezone('US/Eastern')

def format_date_for_api(date, start=True):
    """Format dates to API-friendly format."""
    return date.astimezone(est).strftime('%Y-%m-%dT00:00:01+00:00' if start else '%Y-%m-%dT23:59:59+00:00')

@st.cache_data(ttl=10)
def fetch_call_data(start_date, end_date):
    url = "https://api.bland.ai/v1/calls"
    headers = {"authorization": API_KEY}

    all_call_data = []
    total_count = 0
    total_cost = 0
    transferred_calls = 0
    converted_calls = 0
    from_index = 0
    to_index = 999  # Start with the first 1000 records

    while True:
        querystring = {
            "start_date": start_date,
            "end_date": end_date,
            "from": str(from_index),
            "to": str(to_index)
        }

        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            data = response.json()
            total_count = data.get('total_count', 0)
            calls = data.get('calls', [])
            
            for call in calls:
                price = call.get("price")
                if price is not None:
                    try:
                        total_cost += float(price)
                    except (ValueError, TypeError):
                        st.warning(f"Invalid price value: {price}")
                
                if call.get("transferred_to") is not None:
                    transferred_calls += 1
                
                call_length = call.get("call_length")
                if call_length is not None:
                    try:
                        if float(call_length) > 30:
                            converted_calls += 1
                    except (ValueError, TypeError):
                        st.warning(f"Invalid call length value: {call_length}")
            
            all_call_data.extend(calls)
            
            if len(calls) < 1000:  # Less than 1000 records returned, we've reached the end
                break
            
            from_index = to_index + 1
            to_index = min(from_index + 999, total_count - 1)  # Ensure we don't exceed total_count
        else:
            st.error(f"Failed to fetch data. Status: {response.status_code}")
            break

    df = pd.DataFrame([{
        "Inbound Number": call.get("from"),
        "Call Date": call.get("created_at", "").split("T")[0],
        "Call Duration (minutes)": call.get("call_length", 0),
        "Call Cost ($)": call.get("price", 0.0),
        "Transferred": call.get("transferred_to") is not None,
        "Recording": call.get("recording_url") if call.get("recording_url") else "No Recording"
    } for call in all_call_data])

    return total_count, df, total_cost, transferred_calls, converted_calls

def process_data(total_count, total_cost, transferred_calls, converted_calls):
    transferred_pct = (transferred_calls / total_count) * 100 if total_count else 0
    converted_pct = (converted_calls / transferred_calls) * 100 if transferred_calls else 0
    call_profit = (total_count * 0.25) - total_cost
    return total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct, call_profit

def display_metrics(total_count, total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct, call_profit, show_profit=False):
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Calls", total_count)
    col2.metric(f"Transferred ({transferred_pct:.2f}%)", transferred_calls)
    col3.metric("Converted", "TBC")
    
    col4, col5 = st.columns(2)
    col4.metric("Total Call Cost ($)", f"${total_cost:.2f}")
    if show_profit:
        col5.metric("Call Profit ($)", f"${call_profit:.2f}")
    else:
        col5.empty()  # This keeps the layout consistent when profit is not shown

# Display the logo
st.image("https://cdn.prod.website-files.com/667c3ac275caf73d90d821aa/66f5f57cd6e1727fa47a1fad_call_xlogo.png", width=200)

# Define time periods
today, yesterday = datetime.now(est).date(), datetime.now(est).date() - timedelta(days=1)
last_7_days, last_30_days = today - timedelta(days=7), today - timedelta(days=30)

st.markdown("### Call Data")

# Add date selection
option = st.selectbox("Select a time period:", ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "Custom Date Range"])

# Create a placeholder for the main content
main_content = st.empty()

def style_dataframe(df):
    def make_clickable(val):
        if isinstance(val, str):
            if val.startswith('<a href='):
                return val
            return f'<div>{val}</div>'
        elif pd.isna(val):
            return ''
        else:
            return f'<div>{val}</div>'
    
    styled_df = df.style.format({
        'Call Cost ($)': '${:.2f}'.format,
        'Call Duration (minutes)': '{:.2f}'.format
    }).applymap(make_clickable)
    
    return styled_df

def format_dataframe(df):
    formatted_df = df.copy()
    formatted_df['Call Cost ($)'] = formatted_df['Call Cost ($)'].apply(lambda x: f'${x:.2f}')
    formatted_df['Call Duration (minutes)'] = formatted_df['Call Duration (minutes)'].apply(lambda x: f'{x:.2f}')
    formatted_df['Transferred'] = formatted_df['Transferred'].apply(lambda x: 'Yes' if x else 'No')
    return formatted_df

def create_paginated_table(df):
    records_per_page = 25
    total_pages = (len(df) - 1) // records_per_page + 1
    
    if 'page' not in st.session_state:
        st.session_state.page = 1
    
    page = st.session_state.page
    start_idx = (page - 1) * records_per_page
    end_idx = start_idx + records_per_page
    
    st.write(f"Showing records {start_idx + 1} to {min(end_idx, len(df))} of {len(df)}")
    
    # Convert the 'Recording' column to a clickable link
    df['Recording'] = df['Recording'].apply(lambda x: f'<a href="{x}" target="_blank">Listen</a>' if x != "No Recording" else x)
    
    # Display the table with HTML
    st.write(df.iloc[start_idx:end_idx].to_html(escape=False, index=False), unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    if page > 1:
        if col1.button('Previous 25'):
            st.session_state.page -= 1
            st.rerun()
    
    if page < total_pages:
        if col2.button('Next 25'):
            st.session_state.page += 1
            st.rerun()

# Add this at the end of your script, after all other content
st.markdown(
    """
    <style>
    .stButton button {
        position: fixed;
        left: 5px;
        bottom: 5px;
        z-index: 999;
        background: none;
        border: none;
        color: rgba(0,0,0,0.1);
        font-size: 2px;
        padding: 0;
        width: 4px;
        height: 4px;
        cursor: default;
    }
    .stButton button:hover {
        color: rgba(0,0,0,0.2);
    }
    @media (max-width: 768px) {
        .stButton button {
            position: absolute;
            bottom: -200px;
            left: 5px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

if 'show_profit' not in st.session_state:
    st.session_state.show_profit = False

if st.button("🤖", key="toggle_profit"):
    st.session_state.show_profit = not st.session_state.show_profit

# Define start_date and end_date based on the selected option
if option == "Today":
    start_date, end_date = datetime.combine(today, datetime.min.time(), tzinfo=est), datetime.combine(today, datetime.max.time(), tzinfo=est)
elif option == "Yesterday":
    start_date, end_date = datetime.combine(yesterday, datetime.min.time(), tzinfo=est), datetime.combine(yesterday, datetime.max.time(), tzinfo=est)
elif option == "Last 7 Days":
    start_date, end_date = datetime.combine(last_7_days, datetime.min.time(), tzinfo=est), datetime.combine(today, datetime.max.time(), tzinfo=est)
elif option == "Last 30 Days":
    start_date, end_date = datetime.combine(last_30_days, datetime.min.time(), tzinfo=est), datetime.combine(today, datetime.max.time(), tzinfo=est)
else:
    start_date = st.date_input("Start date", last_30_days)
    end_date = st.date_input("End date", today)
    if start_date > end_date:
        st.error("Start date must be before or equal to end date.")
        st.stop()
    start_date = datetime.combine(start_date, datetime.min.time(), tzinfo=est)
    end_date = datetime.combine(end_date, datetime.max.time(), tzinfo=est)

# Update the "Today" section
if option == "Today":
    while True:
        with main_content.container():
            start_date_str, end_date_str = format_date_for_api(start_date, True), format_date_for_api(end_date, False)
            total_count, df, total_cost, transferred_calls, converted_calls = fetch_call_data(start_date_str, end_date_str)

            if not df.empty:
                total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct, call_profit = process_data(total_count, total_cost, transferred_calls, converted_calls)
                display_metrics(total_count, total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct, call_profit, st.session_state.show_profit)

                with st.expander("Call Details"):
                    formatted_df = format_dataframe(df)
                    create_paginated_table(formatted_df)
            else:
                st.write("No data available for today.")

        time.sleep(10)
        st.rerun()

# Update the section for other options
else:
    with main_content.container():
        start_date_str, end_date_str = format_date_for_api(start_date, True), format_date_for_api(end_date, False)
        total_count, df, total_cost, transferred_calls, converted_calls = fetch_call_data(start_date_str, end_date_str)

        if not df.empty:
            total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct, call_profit = process_data(total_count, total_cost, transferred_calls, converted_calls)
            display_metrics(total_count, total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct, call_profit, st.session_state.show_profit)

            with st.expander("Call Details"):
                formatted_df = format_dataframe(df)
                create_paginated_table(formatted_df)
        else:
            st.write("No data available for the selected time period.")
