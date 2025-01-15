import streamlit as st
from sidebar import global_sidebar
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os

current_dir = os.path.dirname(__file__)

global_sidebar()

st.title("Daily Task Overview")

# Construct the path to the CSV file relative to the current file
csv_path = os.path.join(current_dir, '../data/tasks_output.csv')

uploaded_file = pd.read_csv(csv_path)

if uploaded_file is not None:
    data = uploaded_file
    
    data['start_time'] = pd.to_datetime(data['start_time'], format='%H:%M').dt.time
    
    # Add a new column for the actual end time
    data['end_time'] = data.apply(
        lambda row: (datetime.combine(datetime.today(), row['start_time']) + 
                     timedelta(minutes=row['duration_min'])).time(),
        axis=1
    )
    
    selected_day = st.selectbox("Select a day to view", 
                                ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])
    
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

    # Optional: Adjust the sorting of the y-axis
    fig.update_yaxes(categoryorder="category descending")

    st.warning("Please open the graph in full screen mode for the full schedule")
    # Display the chart
    st.plotly_chart(fig)

    # Show raw data (optional)
    if st.checkbox("Show raw data"):
        st.write(data)

    print(timeline_data['Nurses Required'].dtype)
    print(timeline_data['Nurses Required'].unique())

    st.header("Dataframe_tasks")
    st.dataframe(timeline_data)