import streamlit as st
from sidebar import global_sidebar
from utils import solver_combined, InputParser, verify_solution
import pandas as pd
import base64

# Load the global sidebar
global_sidebar()

st.subheader("Nusing scheduling solver")
st.write("This is a solver for the nursing scheduling problem. It takes two files as input: one for the shifts and one for the tasks. The solver will then generate a schedule for the nurses and the tasks.")

# make a user input that allow the user to input max time for the solver (minutes / seconds format), and the minimum number of nurses that should be working at any given time (integer)



# Only show 'Generate Schedule' button if both files are uploaded
shifts_uploaded = st.session_state.get("shifts_data") is not None
tasks_uploaded = st.session_state.get("tasks_data") is not None

if shifts_uploaded and tasks_uploaded:
    st.info("Both Shifts and Tasks files are uploaded. You can now generate the schedule.")

    max_time = st.number_input("Max Time (seconds)", value=60)
    min_nurses = st.number_input("Minimum Nurses", value=2)

    parser = InputParser()

    if st.button("Generate Schedule"):
        # Parse data
        try:
            shifts_df = parser.parse_input(st.session_state.shifts_data)
            tasks_df = parser.parse_input(st.session_state.tasks_data)
            st.info("Data parsed successfully.")
        except FileNotFoundError:
            shifts_df = pd.read_csv(st.session_state.shifts_data)
            tasks_df = pd.read_csv(st.session_state.tasks_data)
        except Exception as e:
            st.error(f"Error parsing data: {e}")
            st.stop()

        # Solve
        with st.spinner("Solving..."):
            try:
                shifts_results, tasks_results = solver_combined(shifts_df, tasks_df, min_nurses, max_time)
                st.session_state["results"] = [shifts_results, tasks_results]
            except Exception as e:
                st.error(f"An error occurred during solving: {e}")
                # Fallback, just in case
                st.session_state["results"] = [pd.DataFrame(), pd.DataFrame()]
else:
    st.info("Please upload both Shifts and Tasks files to enable the solver.")

    

# Display results if available
if st.session_state.results is not None:

    shifts_result, tasks_result = st.session_state["results"]
    st.subheader("Results")
    st.write("Results are displayed here. These are the results with paramters:")
    st.write(f"Minimum number of nurses: {min_nurses}")
    st.write(f"Max time for the solver: {max_time} seconds")

    # add section to verify the correctness of the results
    if st.button("Verify Results"):
        if verify_solution(shifts_result, tasks_result):
            st.success("Results are correct. ✅")
        else:
            st.error("Results are incorrect. ❌")

    st.subheader("Shifts schedule")
    st.dataframe(shifts_result)
    st.subheader("Tasks schedule")
    st.dataframe(tasks_result)

    # make options to download the results as csv files

    st.markdown("## Download Results")
    shifts_csv = shifts_result.to_csv(index=False).encode()
    tasks_csv = tasks_result.to_csv(index=False).encode()

    st.download_button(
        label="Download Shifts Results as CSV",
        data=shifts_csv,
        file_name="shifts_results.csv",
        mime="text/csv"
    )

    st.download_button(
        label="Download Tasks Results as CSV",
        data=tasks_csv,
        file_name="tasks_results.csv",
        mime="text/csv"
    )

