import streamlit as st
import pandas as pd
import os
from sidebar import global_sidebar

global_sidebar()

def display_uploaded_files():
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

# Call the function
display_uploaded_files()