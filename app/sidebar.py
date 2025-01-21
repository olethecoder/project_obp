import streamlit as st

def global_sidebar():
    st.sidebar.title("File uploader")
    st.sidebar.markdown("Please upload both the shifts and tasks files.")

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
            "Choose a CSV file for Shifts", 
            type=["csv"], 
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
            "Choose a CSV file for Tasks", 
            type=["csv"], 
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
