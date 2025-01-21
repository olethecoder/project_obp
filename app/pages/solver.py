import streamlit as st
from sidebar import global_sidebar
from utils import solver_combined, InputParser
import pandas as pd

global_sidebar()

st.title("Solver Page")
st.subheader("Instructions:")

st.write("These are the instructions")

if st.session_state.get("shifts_data") is not None:
    st.subheader(f"Shifts File: {st.session_state.shifts_uploaded}")
    try:
        st.write("Shifts data is uploaded")
    except Exception as e:
        st.error(f"Error loading shifts data: {e}")
else:
    st.info("Shifts file has not been uploaded yet.")

if st.session_state.get("tasks_data") is not None:
    st.subheader(f"Tasks File: {st.session_state.tasks_uploaded}")    
    try:
        st.write("Tasks data is uploaded")
    except Exception as e:
        st.error(f"Error loading tasks data: {e}")
        st.error("Tasks data not uploaded?")
else:
    st.info("Tasks file has not been uploaded yet.")

st.subheader("Solver")

# make a a button to run the solver with the uploaded data

parser = InputParser()

st.subheader("Solve")
if st.button("Generate Schedule"):
    try:
        shifts_df = parser.parse_input(st.session_state.shifts_data)
        tasks_df = parser.parse_input(st.session_state.tasks_data)
        st.info("Data parsed successfully")
    except Exception as e:
        st.error(f"Error parsing data: {e}")
        st.stop()

    with st.spinner("Solving..."):
        try:
            shifts_results, tasks_results = solver_combined(shifts_df, tasks_df)
            st.session_state['results'] = [shifts_results, tasks_results]
        except Exception as e:
            st.error(f"An error occurred during solving: {e}")
            st.session_state['results'] = pd.read_csv('data/tasks_output.csv')
        
# Result Display

if 'results' in st.session_state:
    shifts_result, tasks_results = st.session_state['results']
    st.subheader("Results")
    st.write("Results are displayed here")

    st.dataframe(shifts_result)
    st.dataframe(tasks_results)

