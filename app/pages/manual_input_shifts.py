import streamlit as st
import pandas as pd
from code.ui.sidebar import global_sidebar

global_sidebar()

# Initialize session state for the DataFrame
if 'manual_shifts' not in st.session_state:
    st.session_state['manual_shifts'] = pd.DataFrame(columns=[
        "name", "max_nurses", "start", "end", "break", "break_duration", "weight",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ])

# Function to add a row to the DataFrame
def add_row(name, max_nurses, start, end, break_time, break_duration, weight, days):
    new_row = pd.DataFrame({
        "name": [name],
        "max_nurses": [max_nurses],
        "start": [start],
        "end": [end],
        "break": [break_time],
        "break_duration": [break_duration],
        "weight": [weight],
        "monday": [days['monday']],
        "tuesday": [days['tuesday']],
        "wednesday": [days['wednesday']],
        "thursday": [days['thursday']],
        "friday": [days['friday']],
        "saturday": [days['saturday']],
        "sunday": [days['sunday']]
    })
    st.session_state['manual_shifts'] = pd.concat([st.session_state['manual_shifts'], new_row], ignore_index=True)

# App title
st.title("Use this page to create a shifts input file within the dashboard.")

# Instructions

st.write("### Instructions:")
st.write("1. Fill in the details for the shift.")
st.write("2. Select the active days for the shift.")
st.write("3. Click on 'Add Shift' to add the shift to the DataFrame.")

# Input form
with st.form("shifts_manual"):
    name = st.text_input("Shift Name", key="name_input")
    max_nurses = st.number_input("Max Nurses", min_value=1, step=1, key="max_nurses_input")
    start = st.text_input("Start Time (e.g., 08:00)", key="start_input")
    end = st.text_input("End Time (e.g., 16:00)", key="end_input")
    break_time = st.text_input("Break Time (e.g., 12:00)", key="break_input")
    break_duration = st.number_input("Break Duration (minutes)", min_value=0, step=1, key="break_duration_input")
    weight = st.number_input("Weight", min_value=0.0, step=0.1, key="weight_input")

    st.write("Select Active Days:")
    days = {
        "monday": st.checkbox("Monday", key="monday_checkbox"),
        "tuesday": st.checkbox("Tuesday", key="tuesday_checkbox"),
        "wednesday": st.checkbox("Wednesday", key="wednesday_checkbox"),
        "thursday": st.checkbox("Thursday", key="thursday_checkbox"),
        "friday": st.checkbox("Friday", key="friday_checkbox"),
        "saturday": st.checkbox("Saturday", key="saturday_checkbox"),
        "sunday": st.checkbox("Sunday", key="sunday_checkbox")
    }

    # Convert True/False to 1/0
    days = {day: int(value) for day, value in days.items()}

    submitted = st.form_submit_button("Add Shift")

    if submitted:
        add_row(name, max_nurses, start, end, break_time, break_duration, weight, days)
        st.success("Shift added successfully!")

# Display the current DataFrame
st.write("### Shifts file:")
st.dataframe(st.session_state['manual_shifts'])

# Option to download the DataFrame as CSV
if not st.session_state['manual_shifts'].empty:
    csv = st.session_state['manual_shifts'].to_csv(index=False)
    st.download_button(
        label="Download Data as CSV",
        data=csv,
        file_name="shifts_data.csv",
        mime="text/csv",
    )
