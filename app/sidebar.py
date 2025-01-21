import streamlit as st
import os

def global_sidebar():
    """
    Create a global sidebar for the app.

    This sidebar will contain the file uploaders for the shifts and tasks data.

    The uploaded files will be stored in the session state.

    """

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

    # Button to clear all uploaded files
    if st.sidebar.button("Clear all uploaded"):
        st.session_state.shifts_uploaded = None
        st.session_state.shifts_data = None
        st.session_state.tasks_uploaded = None
        st.session_state.tasks_data = None
