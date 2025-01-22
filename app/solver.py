import streamlit as st
from sidebar import global_sidebar
from utils import solver_combined, InputParser, verify_solution, call_cp_solver
import pandas as pd
import base64
import threading
import time

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

        # -----------------------------
        # Start solver in background
        # -----------------------------
        solver_result = {}  # We'll store the result here

        def run_solver():
            try:
                shifts_results, tasks_results, cost, __ = solver_combined(shifts_df, tasks_df, max_time, min_nurses, solver=solver_to_use)
                solver_result["results"] = [shifts_results, tasks_results, cost]
            except Exception as e:
                st.error(f"Solver error: {e}")
                st.stop()
                solver_result["error"] = e

        solver_thread = threading.Thread(target=run_solver)
        solver_thread.start()

        # -----------------------------
        # Show a simple progress bar
        # -----------------------------

        progress_bar = st.progress(0)
        for i in range(int(max_time)*10):
            # If the solver is finished, break out early
            if not solver_thread.is_alive():
                break
            # Update progress from 0% to 100% linearly over max_time
            progress_bar.progress(int((i + 1) / max_time * 100), text='Solving...')
            time.sleep(0.1)  # Each loop iteration is 1 second

        # Ensure solver thread finishes
        solver_thread.join()
        # Clear the progress bar
        progress_bar.empty()

        # -----------------------------
        # Check for results or errors
        # -----------------------------
        if "error" in solver_result:
            st.error(f"Solver error: {solver_result['error']}")
        elif "results" in solver_result:
            st.session_state["results"] = solver_result["results"]
            st.success("Solver finished!")
        else:
            st.warning("Solver did not finish within the given time.")
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

