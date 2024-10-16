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
        "Recording": f'<a href="{call.get("recording_url")}" target="_blank">Listen</a>'
                     if call.get("recording_url") else "No Recording"
    } for call in all_call_data])

    return total_count, df, total_cost, transferred_calls, converted_calls

def process_data(total_count, total_cost, transferred_calls, converted_calls):
    transferred_pct = (transferred_calls / total_count) * 100 if total_count else 0
    converted_pct = (converted_calls / transferred_calls) * 100 if transferred_calls else 0
    return total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct

def display_metrics(total_count, total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct):
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Calls", total_count)
    col2.metric(f"Transferred ({transferred_pct:.2f}%)", transferred_calls)
    col3.metric("Converted", "TBC")
    st.metric("Total Call Cost ($)", f"${total_cost:.2f}")

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
    def format_recording(val):
        if pd.isna(val) or val == "No Recording":
            return "No Recording"
        return f'<a href="{val}" target="_blank">Listen</a>'

    formatted_df = df.copy()
    formatted_df['Call Cost ($)'] = formatted_df['Call Cost ($)'].apply(lambda x: f'${x:.2f}')
    formatted_df['Call Duration (minutes)'] = formatted_df['Call Duration (minutes)'].apply(lambda x: f'{x:.2f}')
    formatted_df['Transferred'] = formatted_df['Transferred'].apply(lambda x: 'Yes' if x else 'No')
    formatted_df['Recording'] = formatted_df['Recording'].apply(format_recording)
    
    return formatted_df

if option == "Today":
    start_date, end_date = datetime.combine(today, datetime.min.time(), tzinfo=est), datetime.combine(today, datetime.max.time(), tzinfo=est)
    
    while True:
        with main_content.container():
            start_date_str, end_date_str = format_date_for_api(start_date, True), format_date_for_api(end_date, False)
            total_count, df, total_cost, transferred_calls, converted_calls = fetch_call_data(start_date_str, end_date_str)

            if not df.empty:
                total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct = process_data(total_count, total_cost, transferred_calls, converted_calls)
                display_metrics(total_count, total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct)

                with st.expander("Call Details"):
                    formatted_df = format_dataframe(df)
                    html_table = formatted_df.to_html(escape=False, index=False, classes=['display', 'nowrap'])

                    sortable_table = f"""
                    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
                    <script src="https://cdn.datatables.net/1.10.24/js/jquery.dataTables.min.js"></script>
                    <link rel="stylesheet" href="https://cdn.datatables.net/1.10.24/css/jquery.dataTables.min.css">
                    <style>
                        .dataTables_wrapper .dataTables_length, .dataTables_wrapper .dataTables_filter, .dataTables_wrapper .dataTables_info, .dataTables_wrapper .dataTables_processing, .dataTables_wrapper .dataTables_paginate {{
                            color: #ffffff;
                        }}
                        .dataTables_wrapper .dataTables_paginate .paginate_button {{
                            color: #ffffff !important;
                        }}
                        .dataTables_wrapper .dataTables_paginate .paginate_button.disabled {{
                            color: #666 !important;
                        }}
                        .dataTables_wrapper .dataTables_paginate .paginate_button.current, .dataTables_wrapper .dataTables_paginate .paginate_button.current:hover {{
                            color: #333 !important;
                        }}
                        table.dataTable tbody tr {{
                            background-color: #0e1117;
                            color: #ffffff;
                        }}
                        table.dataTable.display tbody tr.odd {{
                            background-color: #1e2127;
                        }}
                        table.dataTable.display tbody tr.even {{
                            background-color: #0e1117;
                        }}
                        table.dataTable.hover tbody tr:hover, table.dataTable.display tbody tr:hover {{
                            background-color: #2e3137;
                        }}
                        .dataTables_wrapper .dataTables_length select, .dataTables_wrapper .dataTables_filter input {{
                            background-color: #262730;
                            color: #ffffff;
                            border: 1px solid #4a4a4a;
                        }}
                    </style>

                    <table id="sortable_table" class="display nowrap">
                        {html_table}
                    </table>

                    <script>
                        $(document).ready(function() {{
                            $('#sortable_table').DataTable({{
                                "pageLength": 25,
                                "order": [],
                                "columnDefs": [
                                    {{ "orderable": false, "targets": 5 }}  // Disable sorting for the "Recording" column
                                ],
                                "scrollX": true
                            }});
                        }});
                    </script>
                    """

                    html(sortable_table, height=600)
            else:
                st.write("No data available for today.")

        time.sleep(10)
        st.rerun()

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

# Store the current selection in session state
st.session_state['date_selection'] = option

# For options other than "Today"
if option != "Today":
    with main_content.container():
        start_date_str, end_date_str = format_date_for_api(start_date, True), format_date_for_api(end_date, False)
        total_count, df, total_cost, transferred_calls, converted_calls = fetch_call_data(start_date_str, end_date_str)

        if not df.empty:
            total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct = process_data(total_count, total_cost, transferred_calls, converted_calls)
            display_metrics(total_count, total_cost, transferred_calls, converted_calls, transferred_pct, converted_pct)

            with st.expander("Call Details"):
                formatted_df = format_dataframe(df)
                html_table = formatted_df.to_html(escape=False, index=False, classes=['display', 'nowrap'])

                sortable_table = f"""
                <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
                <script src="https://cdn.datatables.net/1.10.24/js/jquery.dataTables.min.js"></script>
                <link rel="stylesheet" href="https://cdn.datatables.net/1.10.24/css/jquery.dataTables.min.css">
                <style>
                    .dataTables_wrapper .dataTables_length, .dataTables_wrapper .dataTables_filter, .dataTables_wrapper .dataTables_info, .dataTables_wrapper .dataTables_processing, .dataTables_wrapper .dataTables_paginate {{
                        color: #ffffff;
                    }}
                    .dataTables_wrapper .dataTables_paginate .paginate_button {{
                        color: #ffffff !important;
                    }}
                    .dataTables_wrapper .dataTables_paginate .paginate_button.disabled {{
                        color: #666 !important;
                    }}
                    .dataTables_wrapper .dataTables_paginate .paginate_button.current, .dataTables_wrapper .dataTables_paginate .paginate_button.current:hover {{
                        color: #333 !important;
                    }}
                    table.dataTable tbody tr {{
                        background-color: #0e1117;
                        color: #ffffff;
                    }}
                    table.dataTable.display tbody tr.odd {{
                        background-color: #1e2127;
                    }}
                    table.dataTable.display tbody tr.even {{
                        background-color: #0e1117;
                    }}
                    table.dataTable.hover tbody tr:hover, table.dataTable.display tbody tr:hover {{
                        background-color: #2e3137;
                    }}
                    .dataTables_wrapper .dataTables_length select, .dataTables_wrapper .dataTables_filter input {{
                        background-color: #262730;
                        color: #ffffff;
                        border: 1px solid #4a4a4a;
                    }}
                </style>

                <table id="sortable_table" class="display nowrap">
                    {html_table}
                </table>

                <script>
                    $(document).ready(function() {{
                        $('#sortable_table').DataTable({{
                            "pageLength": 25,
                            "order": [],
                            "columnDefs": [
                                {{ "orderable": false, "targets": 5 }}  // Disable sorting for the "Recording" column
                            ],
                            "scrollX": true
                        }});
                    }});
                </script>
                """

                html(sortable_table, height=600)
        else:
            st.write("No data available for the selected time period.")
