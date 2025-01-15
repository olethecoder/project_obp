import streamlit as st
import os


def global_sidebar():
    st.sidebar.title("File uploader")
    st.sidebar.markdown("Please upload both the shift and task files.")

    # Create temp directory if it doesn't exist
    temp_dir = 'app/temp'
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # File upload for file1
    if "file1_uploaded" not in st.session_state:
        st.session_state.file1_uploaded = None

    if st.session_state.file1_uploaded:
        st.sidebar.text(f"Uploaded: {st.session_state.file1_uploaded}")
        if st.sidebar.button("Clear File 1"):
            #remove the file from the temp directory
            file_path = os.path.join(temp_dir, f"file1_{st.session_state.file1_uploaded}")
            os.remove(file_path)
            st.session_state.file1_uploaded = None
    else:
        uploaded_file1 = st.sidebar.file_uploader("Choose a CSV file for File 1", type=['csv'], key='file1')
        if uploaded_file1:
            file_path = os.path.join(temp_dir, f"file1_{uploaded_file1.name}")
            with open(file_path, 'wb') as f:
                f.write(uploaded_file1.getbuffer())
            st.session_state.file1_uploaded = uploaded_file1.name
            st.sidebar.success(f"File 1 saved: {uploaded_file1.name}")

    # File upload for file2
    if "file2_uploaded" not in st.session_state:
        st.session_state.file2_uploaded = None

    if st.session_state.file2_uploaded:
        st.sidebar.text(f"Uploaded: {st.session_state.file2_uploaded}")
        if st.sidebar.button("Clear File 2"):
            #remove the file from the temp directory
            file_path = os.path.join(temp_dir, f"file2_{st.session_state.file2_uploaded}")
            os.remove(file_path)
            st.session_state.file2_uploaded = None
    else:
        uploaded_file2 = st.sidebar.file_uploader("Choose a CSV file for File 2", type=['csv'], key='file2')
        if uploaded_file2:
            file_path = os.path.join(temp_dir, f"file2_{uploaded_file2.name}")
            with open(file_path, 'wb') as f:
                f.write(uploaded_file2.getbuffer())
            st.session_state.file2_uploaded = uploaded_file2.name
            st.sidebar.success(f"File 2 saved: {uploaded_file2.name}")

    # create reset button to clear all uploaded files

    if st.sidebar.button("clear all uploaded"):
        for file_name in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file_name)
            os.remove(file_path)
