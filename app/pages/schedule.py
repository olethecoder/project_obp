import streamlit as st
from sidebar import global_sidebar
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os

global_sidebar()

current_dir = os.path.dirname(__file__)

st.title("Daily Schedule")

# Construct the path to the CSV file relative to the current file
csv_path = os.path.join(current_dir, '../data/tasks_output.csv')

uploaded_file = pd.read_csv(csv_path)

if st.session_state.results is not None:
    shifts_result, tasks_result, __ = st.session_state["results"]
else:
    st.error("No results found. The data below is dummy data. Please run the solver first.")

if uploaded_file is not None:
    data = uploaded_file
    
    data['start_time'] = pd.to_datetime(data['start_time'], format='%H:%M').dt.time
    
    # Add a new column for the actual end time
    data['end_time'] = data.apply(
        lambda row: (
            datetime.combine(datetime.today(), row['start_time']) 
            + timedelta(minutes=row['duration_min'])
        ).time(),
        axis=1
    )
    
    # --------------------
    # SINGLE DAY SELECTOR
    # --------------------
    selected_day = st.radio(
    "Select a day to view schedule",
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
    horizontal=True  # This parameter requires Streamlit 1.18 or newer
    )

    
    # --------------------
    # TASKS OVERVIEW
    # --------------------
    filtered_data = data[data[selected_day] == 1]
    
    tasks = []
    for _, row in filtered_data.iterrows():
        tasks.append({
            "Task": row['task'],
            "Start": datetime.combine(datetime.today(), row['start_time']),
            "End": datetime.combine(datetime.today(), row['end_time']),
            "Nurses Required": row['nurses_required']
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

    # --------------------
    # NURSE SCHEDULE
    # --------------------
    # Example DataFrame matching the format
    nurse_schedule_data = [
        [
            "",        # name
            "0:15",    # max_nurses
            "0:00",    # start
            "12:00",   # end
            "0",       # break
            "1",       # break_duration
            "1",       # weight
            "0",       # monday
            "1",       # tuesday
            "1",       # wednesday
            "1",       # thursday
            "1",       # friday
            "1",       # saturday
            "1",       # sunday
            "3"        # number_of_nurses
        ],
        [
            "",        # name
            "1:00",    # max_nurses
            "0:45",    # start
            "12:00",   # end
            "0",       # break
            "1",       # break_duration
            "1",       # weight
            "1",       # monday
            "1",       # tuesday
            "1",       # wednesday
            "1",       # thursday
            "1",       # friday
            "1",       # saturday
            "1",       # sunday
            "1"        # number_of_nurses
        ]
    ]

    nurse_schedule_columns = [
        "name", "max_nurses", "start", "end", "break", "break_duration",
        "weight", "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday", "number_of_nurses"
    ]

    nurse_schedule_df = pd.DataFrame(nurse_schedule_data, columns=nurse_schedule_columns)
    
    # Convert day columns to integers so we can filter with == 1
    day_cols = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for dcol in day_cols:
        nurse_schedule_df[dcol] = nurse_schedule_df[dcol].astype(int)
    
    # --------------------
    # GRAPHICAL OVERVIEW FOR NURSES
    # --------------------

    # Convert the 'start' and 'end' columns to datetime
    nurse_schedule_df['start_dt'] = pd.to_datetime(nurse_schedule_df['start'], format='%H:%M')
    nurse_schedule_df['end_dt'] = pd.to_datetime(nurse_schedule_df['end'], format='%H:%M')

    # Filter nurse schedule by selected_day
    filtered_nurse_df = nurse_schedule_df[nurse_schedule_df[selected_day] == 1]

    if filtered_nurse_df.empty:
        st.warning(f"No nurses scheduled for {selected_day.capitalize()}.")
    else:
        # Build data for the timeline
        nurse_timeline_data = []
        for i, row in filtered_nurse_df.iterrows():
            nurse_name = row['name'] if row['name'] else f"Shift {i+1}"
            nurse_timeline_data.append({
                "Nurse": nurse_name,
                "Start": datetime.combine(datetime.today(), row['start_dt'].time()),
                "End": datetime.combine(datetime.today(), row['end_dt'].time()),
                "Number of Nurses": str(row['number_of_nurses'])
            })

        timeline_nurses = pd.DataFrame(nurse_timeline_data)

        # Plot the nurse schedule using Plotly
        fig_nurses = px.timeline(
            timeline_nurses,
            x_start="Start",
            x_end="End",
            y="Nurse",
            color="Number of Nurses",
            title=f"Nurse Schedule for {selected_day.capitalize()}",
            labels={"Number of Nurses": "Nurses"},
            color_discrete_map={
                "1": "blue", 
                "2": "green",
                "3": "red"
            }
        )

        fig_nurses.update_yaxes(categoryorder="category descending")
        st.plotly_chart(fig_nurses)

    if st.checkbox("Show raw nurse schedule data"):
        st.dataframe(nurse_schedule_df)
