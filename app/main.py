import streamlit as st
from code.ui.sidebar import global_sidebar
from code.utils.utils import solver_combined, InputParser
from code.processing.validator import Validator
import pandas as pd

# Load the global sidebar
global_sidebar()

st.subheader("Nursing scheduling solver")
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

    solve_until_optimal = False

    if solver_to_use == "gurobi":
        if st.checkbox("Ignore max time and solve to optimality"):
            max_time = 1e9
            solve_until_optimal = True

    parser = InputParser()

    if st.button("Generate Schedule"):
        st.session_state.results = None
        st.session_state.input = None
        # Parse data
        try:
            shifts_df = parser.parse_input(st.session_state.shifts_data)
            tasks_df = parser.parse_input(st.session_state.tasks_data)
            st.info("Data parsed successfully.")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print(f"Relying on hardcoded pandas parser")
            shifts_df = pd.read_csv(st.session_state.shifts_data)
            tasks_df = pd.read_csv(st.session_state.tasks_data)
        except Exception as e:
            st.error(f"Error parsing data: {e}")
            st.stop()
        
        st.session_state.input = [shifts_df, tasks_df]
        
        # Solve
        with st.spinner("Solving..."):
            try:
                # shifts_results, tasks_results, cost, __ = solver_combined(shifts_df, tasks_df, min_nurses, max_time, solver=solver_to_use)
                shifts_results, tasks_results, cost_result, __ = solver_combined(shifts_df, tasks_df, max_time, min_nurses, solver_to_use)
                st.session_state["results"] = [shifts_results, tasks_results, cost_result, solver_to_use]
            except NotImplementedError as e:
                st.error(f"Solver \"{solver_to_use}\" not implemented. Please select another solver.")
            except Exception as e:
                st.error(f"An error occurred during solving: {e}. Please refresh the page and try again.")
else:
    st.info("Please upload both Shifts and Tasks files to enable the solver.")

    
# Display results if available
if st.session_state.results is not None:

    print(st.session_state["results"])

    shifts_result, tasks_result, cost_result, solver = st.session_state["results"]
    st.subheader("Results")
    st.write("**Results are displayed here. These are the results with the parameters:**")
    st.write(f"Minimum number of nurses: {min_nurses}")
    if solve_until_optimal:
        st.write(f"Solved until optimal solution was found.")
    else:
        st.write(f"Max time for the solver: {max_time} seconds")

    st.write(f"Solver used: {solver}")
    st.write(f"Total cost: {cost_result:.2f}")

    st.write("The total cost is the product of the number of 15-minute blocks scheduled, the number of nurses scheduled, and the weight of the scheduled nurse")

    if st.button("Verify Results"):
        print(f"Type of shifts_result: {type(shifts_result)}")
        print(f"Type of tasks_result: {type(tasks_result)}")
        if Validator.validate_schedule(shifts_result, tasks_result):
            st.success("Results are correct. ✅")
        else:
            st.error("Results are incorrect. ❌")
    

    st.subheader("Shifts schedule")
    st.dataframe(shifts_result)
    st.subheader("Tasks schedule")
    selected_day = st.radio(
        "Please choose the day you want to see the tasks for",
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        horizontal=True  # This parameter requires Streamlit 1.18 or newer
    )
    day_index = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(selected_day)
    st.dataframe(tasks_result[tasks_result["day_index"] == day_index])

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

