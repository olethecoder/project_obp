import streamlit as st
import pandas as pd
import os
from code.ui.sidebar import global_sidebar
from io import BytesIO

global_sidebar()

def display_uploaded_files_old():
    st.title("Display Uploaded Files")
    
    st.write("todoL also add example format of file")

    temp_dir = 'app/temp'
    file1_path = None
    file2_path = None

    # Check if temp directory exists
    if os.path.exists(temp_dir):
        # Look for files with the file1 and file2 prefix
        for file_name in os.listdir(temp_dir):
            if file_name.startswith("file1_"):
                file1_path = os.path.join(temp_dir, file_name)
            elif file_name.startswith("file2_"):
                file2_path = os.path.join(temp_dir, file_name)

    # Display DataFrame for File 1
    if file1_path and os.path.isfile(file1_path):
        st.subheader(f"File 1: {file1_path}")
        try:
            df1 = pd.read_csv(file1_path)
            st.dataframe(df1)
        except Exception as e:
            st.error(f"Error loading File 1: {e}")
    else:
        st.info("File 1 has not been uploaded yet.")

    # Display DataFrame for File 2
    if file2_path and os.path.isfile(file2_path):
        st.subheader(f"File 2: {file2_path}")
        try:
            df2 = pd.read_csv(file2_path)
            st.dataframe(df2)
        except Exception as e:
            st.error(f"Error loading File 2: {e}")
    else:
        st.info("File 2 has not been uploaded yet.")

def display_uploaded_files():
    st.title("Display Uploaded Files")
    st.write("This page displays the uploaded Shifts and Tasks files.")
    
    # Check if the Shifts file is uploaded in session state
    if st.session_state.get("shifts_data") is not None:
        st.subheader(f"Shifts File: {st.session_state.shifts_uploaded}")
        try:
            # Convert the in-memory bytes into a file-like object for pandas
            df_shifts = pd.read_csv(BytesIO(st.session_state.shifts_data))
            st.dataframe(df_shifts)
        except Exception as e:
            st.error(f"Error loading Shifts file: {e}")
    else:
        st.info("Shifts file has not been uploaded yet.")

    # Check if the Tasks file is uploaded in session state
    if st.session_state.get("tasks_data") is not None:
        st.subheader(f"Tasks File: {st.session_state.tasks_uploaded}")
        try:
            # Convert the in-memory bytes into a file-like object for pandas
            df_tasks = pd.read_csv(BytesIO(st.session_state.tasks_data))
            st.dataframe(df_tasks)
        except Exception as e:
            st.error(f"Error loading Tasks file: {e}")
    else:
        st.info("Tasks file has not been uploaded yet.")
# Call the function

display_uploaded_files()