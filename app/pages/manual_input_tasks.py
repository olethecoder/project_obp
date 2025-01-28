import streamlit as st
import pandas as pd
from code.ui.sidebar import global_sidebar

global_sidebar()

# Initialize session state for the DataFrame
if "manual_tasks" not in st.session_state:
    st.session_state["manual_tasks"] = pd.DataFrame(
        columns=[
            "task",
            "start",
            "end",
            "duration_min",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "nurses_required",
        ]
    )

# Function to add a row to the DataFrame
def add_task_row(task, start, end, duration_min, nurses_required, days):
    new_row = pd.DataFrame(
        {
            "task": [task],
            "start": [start],
            "end": [end],
            "duration_min": [duration_min],
            "monday": [days["monday"]],
            "tuesday": [days["tuesday"]],
            "wednesday": [days["wednesday"]],
            "thursday": [days["thursday"]],
            "friday": [days["friday"]],
            "saturday": [days["saturday"]],
            "sunday": [days["sunday"]],
            "nurses_required": [nurses_required],
        }
    )
    st.session_state["manual_tasks"] = pd.concat(
        [st.session_state["manual_tasks"], new_row], ignore_index=True
    )

# App title
st.title("Use this page to create a tasks input file within the dashboard.")

# Instructions
st.write("### Instructions:")
st.write("1. Fill in the details for the task.")
st.write("2. Select the active days for the task.")
st.write("3. Click on 'Add Task' to add the task to the DataFrame.")

# Input form
with st.form("tasks_form"):
    task_name = st.text_input("Task Name", key="task_name_input")
    start_time = st.text_input("Start Time (e.g., 08:00)", key="start_time_input")
    end_time = st.text_input("End Time (e.g., 16:00)", key="end_time_input")
    duration = st.number_input(
        "Total Duration (minutes)",
        min_value=0,
        step=1,
        key="duration_input",
    )
    nurses_required = st.number_input(
        "Nurses Required",
        min_value=1,
        step=1,
        key="nurses_required_input",
    )

    st.write("Select Active Days:")
    days = {
        "monday": st.checkbox("Monday", key="monday_checkbox"),
        "tuesday": st.checkbox("Tuesday", key="tuesday_checkbox"),
        "wednesday": st.checkbox("Wednesday", key="wednesday_checkbox"),
        "thursday": st.checkbox("Thursday", key="thursday_checkbox"),
        "friday": st.checkbox("Friday", key="friday_checkbox"),
        "saturday": st.checkbox("Saturday", key="saturday_checkbox"),
        "sunday": st.checkbox("Sunday", key="sunday_checkbox"),
    }

    # Convert True/False to 1/0
    days = {day: int(value) for day, value in days.items()}

    submitted = st.form_submit_button("Add Task")

    if submitted:
        add_task_row(task_name, start_time, end_time, duration, nurses_required, days)
        st.success("Task added successfully!")

# Display the current DataFrame
st.write("### Tasks file:")
st.dataframe(st.session_state["manual_tasks"])

# Option to download the DataFrame as CSV
if not st.session_state["manual_tasks"].empty:
    csv = st.session_state["manual_tasks"].to_csv(index=False)
    st.download_button(
        label="Download Data as CSV",
        data=csv,
        file_name="tasks_data.csv",
        mime="text/csv",
    )
