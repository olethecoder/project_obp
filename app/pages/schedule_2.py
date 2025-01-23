import streamlit as st
from sidebar import global_sidebar
import pandas as pd
from datetime import datetime, timedelta, time
import plotly.express as px

global_sidebar()

st.title("Daily Schedule Viewer")

if(True):
    st.session_state.results = [pd.read_csv("shifts_results.csv"), pd.read_csv("tasks_results.csv"), 1]

if st.session_state.results is not None:
    shifts_result, tasks_result, __ = st.session_state["results"]

    ## Display the tasks results

    data = tasks_result
    
    data['solution_start'] = pd.to_datetime(data['solution_start'], format='%H:%M').dt.time

    # Define a helper function to clamp the end time to 23:59 *of the same day* if it overflows
    def clamp_end_time(row):
        # Convert solution_start to a full datetime object, using "today" (or any single reference date).
        start_dt = datetime.combine(datetime.today(), row['solution_start'])
        
        # Calculate the naive end (start + duration)
        naive_end_dt = start_dt + timedelta(minutes=row['duration'])
        
        # Create a cutoff at 23:59 on the same date as start_dt
        cutoff_dt = datetime.combine(start_dt.date(), time(23, 59))
        
        # Return whichever is earlier: either naive end or 23:59
        return min(naive_end_dt, cutoff_dt)

    # Create new columns for start and end as full datetime
    data['start_dt'] = data.apply(
        lambda row: datetime.combine(datetime.today(), row['solution_start']),
        axis=1
    )
    data['end_dt'] = data.apply(clamp_end_time, axis=1)

    # For debugging or future use
    data.to_csv('result_df.csv', index=False)

    # -----------------------------------------------------------------------------------
    # STREAMLIT UI ELEMENTS
    # -----------------------------------------------------------------------------------
    st.title("Task Overview")

    # Single day selector
    selected_day = st.radio(
        "Please choose the day you want to see the tasks for",
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        horizontal=True
    )
    day_index = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(selected_day)

    # Filter data by selected day
    filtered_data = data[data["day_index"] == day_index]

    # Build list of tasks for the timeline
    tasks = []
    for _, row in filtered_data.iterrows():
        tasks.append({
            "Task": row['task_name'],
            "Start": row['start_dt'],
            "End": row['end_dt'],
            "Nurses Required": row['required_nurses']
        })

    timeline_data = pd.DataFrame(tasks)

    # Convert Nurses Required to string for color mapping
    timeline_data['Nurses Required'] = timeline_data['Nurses Required'].astype(str)

    # -----------------------------------------------------------------------------------
    # PLOTLY TIMELINE
    # -----------------------------------------------------------------------------------
    fig = px.timeline(
        timeline_data,
        x_start="Start",
        x_end="End",
        y="Task",
        color="Nurses Required",
        title=f"Task Overview for {selected_day}",
        labels={"Nurses Required": "Nurses"},
        color_discrete_map={
            "1": "blue",   # Color for tasks requiring 1 nurse
            "2": "green",  # Color for tasks requiring 2 nurses
            "3": "red"     # Color for tasks requiring 3 nurses
        }
    )

    fig.update_yaxes(categoryorder="category descending")

    st.warning("Please open the graphs in full screen mode for the full schedule")
    st.plotly_chart(fig)

    if st.checkbox("Show raw task data"):
        st.write(data)
else:
    st.error("No results found.  Please run the solver first before viewing results.")
