import streamlit as st
from sidebar import global_sidebar

global_sidebar()

st.title("Solver Page")
st.subheader("Instructions:")

st.write("These are the instructions")

## initialize files to None

if "file1_df" not in st.session_state:
    st.session_state.file1_df = None
    st.warning("Please upload the first file")
else:
    st.dataframe(st.session_state.file1_df)