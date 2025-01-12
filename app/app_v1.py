import streamlit as st
import pandas as pd
import os
from input_parser import InputParser
from solver import NurseSchedulingSolver


def solve_shedule(shifts_input, tasks_input):
    # import data

    # parse input
    shifts = InputParser.parse_input(shifts_input)
    tasks = InputParser.parse_input(tasks_input)
    
    # 2) Instantiate solver
    solver = NurseSchedulingSolver(
        shifts, 
        tasks,
        max_nurses_per_shift = 100
    )

    # 3) Solve
    solver.solve()

    # 4) Print solution

    #solver.print_solution()

    # 5) Extract usage
    usage = solver.get_solution_usage()
    
    return usage

# Streamlit UI
st.title("Nursing Ward Shift Scheduler")

st.sidebar.header("Upload Data")

# File Upload Section
uploaded_shifts = st.sidebar.file_uploader("Upload Shifts CSV", type=["csv"], key="shifts")
uploaded_tasks = st.sidebar.file_uploader("Upload Tasks CSV", type=["csv"], key="tasks")

# Local File Section
use_local_shifts = st.sidebar.button("Use Local Shifts File")
use_local_tasks = st.sidebar.button("Use Local Tasks File")


# Load local files if buttons are clicked
if use_local_shifts:
    shifts_path = os.path.join(os.path.dirname(__file__), "../data/shifts.csv")  # Adjust this path as needed
    if os.path.exists(shifts_path):
        #shifts_df = pd.read_csv(shifts_path)
        uploaded_shifts = shifts_path
        st.sidebar.success(f"Loaded local shifts file: {shifts_path}")
    else:
        st.sidebar.error(f"Local shifts file not found at {shifts_path}")

if use_local_tasks:
    tasks_path = os.path.join(os.path.dirname(__file__), "../data/tasks.csv")  # Adjust this path as needed
    if os.path.exists(tasks_path):
        #tasks_df = pd.read_csv(tasks_path)
        uploaded_tasks = tasks_path
        st.sidebar.success(f"Loaded local tasks file: {tasks_path}")
    else:
        st.sidebar.error(f"Local tasks file not found at {tasks_path}")

# Display Uploaded Data or Local Files
if uploaded_shifts:
    shifts_df = pd.read_csv(uploaded_shifts)
    st.subheader("Uploaded Shifts")
    st.dataframe(shifts_df)

if uploaded_tasks:
    tasks_df = pd.read_csv(uploaded_tasks)
    st.subheader("Uploaded Tasks")
    st.dataframe(tasks_df)

# Solve Button
if st.sidebar.button("Solve"):
    if shifts_df is not None and tasks_df is not None:
        with st.spinner("Solving..."):
            result = solve_scheduling_problem(shifts_df, tasks_df)
            st.success("Scheduling completed!")

            # Display Result
            st.subheader("Result: Shifts Used")
            st.write(result["Shifts Used"])

            st.subheader("Result: Tasks Scheduled")
            tasks_scheduled_df = pd.DataFrame(result["Tasks Scheduled"])
            st.dataframe(tasks_scheduled_df)

            st.subheader("Summary")
            st.write(result["Summary"])
    else:
        st.error("Please upload or select both shifts and tasks files.")

# Instructions or Additional Features
st.sidebar.header("Instructions")
st.sidebar.write(
    "1. Upload CSV files for shifts and tasks or use local files.\n"
    "2. Click 'Solve' to generate an optimized schedule.\n"
    "3. View results in the main area."
)
