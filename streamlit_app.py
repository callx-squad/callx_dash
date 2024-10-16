import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
from geopy.geocoders import Nominatim  # For geocoding zip codes

# Define EST timezone
est = pytz.timezone('US/Eastern')

# Function to format dates for the API
def format_date_for_api(date, start=True):
    return date.astimezone(est).strftime('%Y-%m-%dT00:00:01+00:00' if start else '%Y-%m-%dT23:59:59+00:00')

# Cache API data with 10-second refresh
@st.cache_data(ttl=10)
def fetch_call_data(start_date, end_date, limit=1000):
    url = "https://api.bland.ai/v1/calls"
    headers = {"authorization": "sk-s3zix6yia4ew2w9ymga9v0jexcx0j0crqu0kuvzwqqhg3hj7z9tteiuv6i3rls5u69"}

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
        "Zip": call.get("variables", {}).get("zip", "Unknown"),
        "Transferred": call.get("transferred_to") is not None,
        "Recording": f'<a href="{call.get("recording_url")}" target="_blank">Listen</a>'
                     if call.get("recording_url") else "No Recording"
    } for call in all_call_data])

# Geocode zip codes to get latitude and longitude
@st.cache_data
def geocode_zip_codes(df):
    geolocator = Nominatim(user_agent="geoapiExercises")
    locations = []

    for zip_code in df["Zip"].unique():
        try:
            location = geolocator.geocode({"postalcode": zip_code})
            if location:
                locations.append({"zip": zip_code, "latitude": location.latitude, "longitude": location.longitude})
        except:
            locations.append({"zip": zip_code, "latitude": None, "longitude": None})

    return pd.DataFrame(locations).dropna()

# Display logo
image_url = "https://cdn.prod.website-files.com/667c3ac275caf73d90d821aa/66f5f57cd6e1727fa47a1fad_call_xlogo.png"
st.image(image_url, width=200)

# Time periods
today, yesterday = datetime.now(est).date(), datetime.now(est).date() - timedelta(days=1)
last_7_days, last_30_days = today - timedelta(days=7), today - timedelta(days=30)

st.markdown("### Call Data")

# Date selection
option = st.selectbox(
    "Select a time period:",
    ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "Custom Date Range"]
)

# Date range logic
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

# Format dates
start_date_str, end_date_str = format_date_for_api(start_date, True), format_date_for_api(end_date, False)

# Fetch and display data
df = fetch_call_data(start_date_str, end_date_str)
if not df.empty:
    total_calls, total_cost = df.shape[0], df["Call Cost ($)"].sum()
    transferred_calls, converted_calls = df[df["Transferred"]].shape[0], df[df["Call Duration (minutes)"] > 30].shape[0]
    transferred_pct = (transferred_calls / total_calls) * 100 if total_calls > 0 else 0
    converted_pct = (converted_calls / transferred_calls) * 100 if transferred_calls > 0 else 0

    # Metrics display
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Calls", total_calls)
    col2.metric(f"Transferred ({transferred_pct:.2f}%)", transferred_calls)
    col3.metric(f"Converted ({converted_pct:.2f}%)", converted_calls)
    st.metric("Total Call Cost ($)", f"${total_cost:.2f}")

    # Display table
    with st.expander("Call Details"):
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)

    # Plot zip code locations on a map
    zip_data = geocode_zip_codes(df)
    st.map(zip_data[["latitude", "longitude"]])
else:
    st.write("No data available for the selected time period.")
