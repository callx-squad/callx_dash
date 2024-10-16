import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
import time
from streamlit.components.v1 import html
import hashlib

# Define multiple sets of credentials
CREDENTIALS = {
    "user1": {
        "username": st.secrets["USERNAME1"],
        "password": st.secrets["PASSWORD1"]
    },
    "user2": {
        "username": st.secrets["USERNAME2"],
        "password": st.secrets["PASSWORD2"]
    }
}

# Function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Function to check login
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        for user, cred in CREDENTIALS.items():
            if (st.session_state["username"] == cred["username"] and 
                hash_password(st.session_state["password"]) == hash_password(cred["password"])):
                st.session_state["password_correct"] = True
                st.session_state["current_user"] = user
                del st.session_state["password"]  # Don't store password
                return
        st.session_state["password_correct"] = False

    # Center the logo and create some space
    if "password_correct" not in st.session_state or not st.session_state["password_correct"]:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.image("https://cdn.prod.website-files.com/667c3ac275caf73d90d821aa/66f5f57cd6e1727fa47a1fad_call_xlogo.png", width=200)
    
    st.write("")  # Add some space

    if "password_correct" not in st.session_state:
        # First run, show inputs for username + password.
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error.
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        st.error("😕 User not known or password incorrect")
        return False
    else:
        # Password correct.
        return True

# Main function to display dashboard
def main():
    if not check_password():
        st.stop()  # Do not continue if check_password is not True.
    
    # Retrieve API_KEY from Streamlit secrets
    API_KEY = st.secrets.get("API_KEY")
    
    # Your existing dashboard code starts here
    if not API_KEY:
        st.error("API_KEY is not set. Please set it in your Streamlit secrets.")
        st.stop()

    # Display the logo and logout button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.image("https://cdn.prod.website-files.com/667c3ac275caf73d90d821aa/66f5f57cd6e1727fa47a1fad_call_xlogo.png", width=200)
    with col2:
        if st.button("Logout", key="logout_button", type="primary"):
            st.session_state["password_correct"] = False
            st.rerun()

    st.markdown("---")  # Add a horizontal line for visual separation

    st.markdown("### Call Data")

    # Add date selection (only once)
    option = st.selectbox("Select a time period:", ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "Custom Date Range"])

    # Create a placeholder for the main content
    main_content = st.empty()

    # Check if the current user is user1
    if st.session_state.get("current_user") == "user1":
        if st.button("🤖", key="toggle_profit"):
            st.session_state.show_profit = not st.session_state.show_profit

    # Define start_date and end_date based on the selected option
    today = datetime.now(pytz.timezone('US/Eastern')).date()
    yesterday = today - timedelta(days=1)
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)

    if option == "Today":
        start_date, end_date = datetime.combine(today, datetime.min.time(), tzinfo=pytz.timezone('US/Eastern')), datetime.combine(today, datetime.max.time(), tzinfo=pytz.timezone('US/Eastern'))
    elif option == "Yesterday":
        start_date, end_date = datetime.combine(yesterday, datetime.min.time(), tzinfo=pytz.timezone('US/Eastern')), datetime.combine(yesterday, datetime.max.time(), tzinfo=pytz.timezone('US/Eastern'))
    elif option == "Last 7 Days":
        start_date, end_date = datetime.combine(last_7_days, datetime.min.time(), tzinfo=pytz.timezone('US/Eastern')), datetime.combine(today, datetime.max.time(), tzinfo=pytz.timezone('US/Eastern'))
    elif option == "Last 30 Days":
        start_date, end_date = datetime.combine(last_30_days, datetime.min.time(), tzinfo=pytz.timezone('US/Eastern')), datetime.combine(today, datetime.max.time(), tzinfo=pytz.timezone('US/Eastern'))
    else:
        start_date = st.date_input("Start date", last_30_days)
        end_date = st.date_input("End date", today)
        if start_date > end_date:
            st.error("Start date must be before or equal to end date.")
            st.stop()
        start_date = datetime.combine(start_date, datetime.min.time(), tzinfo=pytz.timezone('US/Eastern'))
        end_date = datetime.combine(end_date, datetime.max.time(), tzinfo=pytz.timezone('US/Eastern'))

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

if __name__ == "__main__":
    main()
