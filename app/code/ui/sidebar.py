import streamlit as st
import os
import pandas as pd

def global_sidebar() -> None:
    """
    Create a global sidebar for the app.

    This sidebar will contain the file uploaders for the shifts and tasks data.

    The uploaded files will be stored in the session state.

    """

    if "results" not in st.session_state:
        st.session_state.results = None

    # Initialize session state variables for files if not present
    if "shifts_uploaded" not in st.session_state:
        st.session_state.shifts_uploaded = None
    if "shifts_data" not in st.session_state:
        st.session_state.shifts_data = None

    if "tasks_uploaded" not in st.session_state:
        st.session_state.tasks_uploaded = None
    if "tasks_data" not in st.session_state:
        st.session_state.tasks_data = None

    # Shifts
    if st.session_state.shifts_uploaded:
        st.sidebar.text(f"Uploaded: {st.session_state.shifts_uploaded}")
        if st.sidebar.button("Clear Shifts"):
            # Clear from session state
            st.session_state.shifts_uploaded = None
            st.session_state.shifts_data = None
            st.session_state.results = None
    else:
        uploaded_shifts = st.sidebar.file_uploader(
            "Choose an input file for Shifts", 
            type=["csv", "xlsx"], 
            key="shifts"
        )
        if uploaded_shifts:
            # Store file name and file data in session state
            st.session_state.shifts_uploaded = uploaded_shifts.name
            st.session_state.shifts_data = uploaded_shifts.getvalue()
            st.sidebar.success(f"Shifts file saved: {uploaded_shifts.name}")

    # Tasks
    if st.session_state.tasks_uploaded:
        st.sidebar.text(f"Uploaded: {st.session_state.tasks_uploaded}")
        if st.sidebar.button("Clear Tasks"):
            # Clear from session state
            st.session_state.tasks_uploaded = None
            st.session_state.tasks_data = None
            st.session_state.results = None
    else:
        uploaded_tasks = st.sidebar.file_uploader(
            "Choose an input file for Tasks", 
            type=["csv", "xlsx"], 
            key="tasks"
        )
        if uploaded_tasks:
            # Store file name and file data in session state
            st.session_state.tasks_uploaded = uploaded_tasks.name
            st.session_state.tasks_data = uploaded_tasks.getvalue()
            st.sidebar.success(f"Tasks file saved: {uploaded_tasks.name}")

    st.sidebar.divider()

    # Button to clear all uploaded files
    st.sidebar.write('Use this button to clear all uploaded files.')
    if st.sidebar.button("Clear all uploaded"):
        st.session_state.shifts_uploaded = None
        st.session_state.shifts_data = None
        st.session_state.tasks_uploaded = None
        st.session_state.tasks_data = None
        st.session_state.results = None

    st.sidebar.divider()

    # make buttons do download example files

    # Check if the data directory exists

    data_dir = "data"
    
    # Check if the example files exist

    example_shifts = os.path.join(data_dir, "shifts_example.csv")
    example_tasks = os.path.join(data_dir, "tasks_example.csv")

    example_shifts_file = pd.read_csv(example_shifts).to_csv()
    example_tasks_file = pd.read_csv(example_tasks).to_csv()


    if os.path.exists(example_shifts) and os.path.exists(example_tasks):
        # add download link
        st.sidebar.write("## Download Example Files")
        st.sidebar.write("Download the example files to see the expected format.")
        st.sidebar.download_button(
            label="Download Example Shifts",
            data=example_shifts_file,
            file_name="shifts.csv"
        )
        st.sidebar.download_button(
            label="Download Example Tasks",
            data=example_tasks_file,
            file_name="tasks.csv"
        )
    else:
        st.sidebar.error("Example files are missing. Please check the data directory.")