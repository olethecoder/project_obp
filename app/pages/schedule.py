import streamlit as st
from code.ui.sidebar import global_sidebar
import pandas as pd
from datetime import datetime, timedelta, time
import plotly.express as px

global_sidebar()

st.title("Daily Schedule Viewer")

if st.session_state.results is not None:
    shifts_result, tasks_result, __, __ = st.session_state["results"]

        # Single day selector
    selected_day = st.radio(
        "Please choose the day you want to see the tasks for",
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        horizontal=True
    )
    day_index = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(selected_day)

    st.warning("Please open the graphs in full screen mode for the full schedule. Only tasks and shifts that start on the selected day are shown.")

    def display_tasks_results(data):
        data = data.copy()

        data['solution_start'] = pd.to_datetime(data['solution_start'], format='mixed').dt.time
        # add duration to solution start

        data['solution_end'] = data.apply(
            lambda row: datetime.combine(datetime.today(), row['solution_start']) + timedelta(minutes=row['duration']),
            axis=1
        )


        data['start_dt'] = data.apply(
            lambda row: datetime.combine(datetime.today(), row['solution_start']),
            axis=1
        )

        data['end_dt'] = data['solution_end']

        st.subheader("Task Overview")

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

        st.plotly_chart(fig)

        if st.checkbox("Show raw task data"):
            st.dataframe(data[data.day_index == day_index])

    def display_nurse_results(data):

        data = data.copy()
        
        data['start'] = pd.to_datetime(data['start'], format='mixed').dt.time
        data['end'] = pd.to_datetime(data['end'], format='mixed').dt.time

        data['start_dt'] = data.apply(
            lambda row: datetime.combine(datetime.today(), row['start']),
            axis=1
        )

        data['end_dt'] = data.apply(
            lambda row: (datetime.combine(datetime.today(), row['end'])
                        if row['end'] >= row['start']
                        else datetime.combine(datetime.today() + timedelta(days=1), row['end'])),
            axis=1
        )

        # -----------------------------------------------------------------------------------
        # STREAMLIT UI ELEMENTS
        # -----------------------------------------------------------------------------------
        st.subheader("Shifts Overview")

        day_index = selected_day.lower()

        filtered_data = data[(data[day_index] == 1) & (data['usage'] != 1)]

        filtered_data['index'] = filtered_data.index.astype(str) + " - " + filtered_data['name']

        # Build list of shifts for the timeline
        shifts = []
        for _, row in filtered_data.iterrows():
            shifts.append({
                "Shift name": row['index'],
                "Start": row['start_dt'],
                "End": row['end_dt'],
                "Amount planned": row['usage']
            })

        timeline_data = pd.DataFrame(shifts)

        df_agg = (
            timeline_data
            .groupby(["Start", "End"], as_index=False)
            .agg({
                "Shift name": lambda x: ", ".join(x),  # Combine shift names
                "Amount planned": "sum"               # Or 'count', depending on your needs
            })
        )

        # Create a new column 'Count' to hold how many original rows were aggregated
        df_counts = (
            timeline_data
            .groupby(["Start", "End"], as_index=False)
            .size()  # size() returns a Series named 'size'
            .rename(columns={"size": "Count"})
        )

        # Merge counts back into df_agg
        df_agg = df_agg.merge(df_counts, on=["Start", "End"], how="left")


        df_agg['Count'] = df_agg['Count'].astype(str)

        fig = px.timeline(
            df_agg,
            x_start="Start",
            x_end="End",
            y="Shift name",
            color="Count",              # color by the number of merged shifts
            title="Shifts Overview",
            labels={"Count": "Nurses", "Shift name": "Index - Shift Name"},  # Legend label
            color_discrete_map={
            "1": "blue",   # Color for tasks requiring 1 nurse
            "2": "green",  # Color for tasks requiring 2 nurses
            "3": "red"     # Color for tasks requiring 3 nurses
            }
        )

        fig.update_yaxes(categoryorder="category descending")

        st.plotly_chart(fig)

        if st.checkbox("Show raw shift data"):
            st.dataframe(data[(data[day_index] == 1) & (data['usage'] != 0)])


    display_tasks_results(tasks_result)
    display_nurse_results(shifts_result)


else:
    st.error("No results found.  Please run the solver first before viewing results.")
