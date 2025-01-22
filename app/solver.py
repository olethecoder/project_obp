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

    max_time = st.number_input("Max Time (seconds)", value=30)
    min_nurses = st.number_input("Minimum Nurses", value=2)
    solver_to_use = st.selectbox("Solver to use", options=["cp", "gurobi"], placeholder="cp")

    parser = InputParser()

    if st.button("Generate Schedule"):
        st.session_state.results = None
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
                # shifts_results, tasks_results, cost, __ = solver_combined(shifts_df, tasks_df, min_nurses, max_time, solver=solver_to_use)
                shifts_results, tasks_results, cost_result, __ = solver_combined(shifts_df, tasks_df, max_time, min_nurses, solver_to_use)
                st.session_state["results"] = [shifts_results, tasks_results, cost_result]
            except NotImplementedError as e:
                st.error(f"Solver \"{solver_to_use}\" not implemented. Please select another solver.")
            except Exception as e:
                st.error(f"An error occurred during solving: {e}. Please refresh the page and try again.")
else:
    st.info("Please upload both Shifts and Tasks files to enable the solver.")

    

# Display results if available
if st.session_state.results is not None:

    shifts_result, tasks_result, cost_result = st.session_state["results"]
    st.subheader("Results")
    st.write("**Results are displayed here. These are the results with the parameters:**")
    st.write(f"Minimum number of nurses: {min_nurses}")
    st.write(f"Max time for the solver: {max_time} seconds")
    st.write(f"Solver used: {solver_to_use}")
    st.write(f"Total cost: {cost_result}")

    st.write("The total cost is the product of the number of 15-minute blocks scheduled, the number of nurses scheduled, and the weight of the scheduled nurse")

    # add section to verify the correctness of the results
    if st.button("Verify Results"):
        if verify_solution(shifts_result, tasks_result):
            st.success("Results are correct. ✅")
        else:
            st.error("Results are incorrect. ❌")

    st.subheader("Shifts schedule")
    st.dataframe(shifts_result)
    st.subheader("Tasks schedule")
    selected_day = st.radio(
    "Please choose the day you want to see the tasks for",
    [0, 1, 2, 3, 4, 5, 6],
    horizontal=True  # This parameter requires Streamlit 1.18 or newer
    )
    st.dataframe(tasks_result[tasks_result["day_index"] == selected_day])

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

