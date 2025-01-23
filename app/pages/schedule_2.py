import streamlit as st
from sidebar import global_sidebar
import pandas as pd
from datetime import datetime, timedelta
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
    
    # Add a new column for the actual end time
    data['end_time'] = data.apply(
        lambda row: (
            datetime.combine(datetime.today(), row['solution_start']) 
            + timedelta(minutes=row['duration'])
        ).time(),
        axis=1
    )
    
    # --------------------
    # SINGLE DAY SELECTOR
    # --------------------
    selected_day = st.radio(
        "Please choose the day you want to see the tasks for",
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        horizontal=True  # This parameter requires Streamlit 1.18 or newer
    )
    day_index = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(selected_day)

    
    # --------------------
    # TASKS OVERVIEW
    # --------------------
    filtered_data = data[data["day_index"] == day_index]
    
    tasks = []
    for _, row in filtered_data.iterrows():
        tasks.append({
            "Task": row['task_name'],
            "Start": datetime.combine(datetime.today(), row['solution_start']),
            "End": datetime.combine(datetime.today(), row['end_time']),
            "Nurses Required": row['required_nurses']
        })
    
    timeline_data = pd.DataFrame(tasks)
    timeline_data['Nurses Required'] = timeline_data['Nurses Required'].astype(str)

    fig = px.timeline(
        timeline_data,
        x_start="Start",
        x_end="End",
        y="Task",
        color="Nurses Required",
        title=f"Task Overview for {selected_day.capitalize()}",
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
