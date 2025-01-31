# User Guide for Project OBP

## Table of Contents
1. Introduction
2. Setup
3. Running the Dashboard
4. Using the Dashboard
    - Manual Input for Tasks
    - Manual Input for Shifts
    - Schedule Overview
    - Show Input Files
5. Solver
6. Downloading Results

## Introduction
Project OBP is a Streamlit-based application designed to help manage and optimize nurse scheduling. The application allows users to input tasks and shifts manually, view schedules, and solve for optimal nurse allocation.

> Please note that a Gurobi license is required to run the Gurobi version of the solver. If no license is found, the solver will not run.

## Setup
1. **Clone the repository and cd into the correct directory**:
    ```
    git clone https://github.com/kurkmeister/project_obp.git
    ```
    ```
    cd project-obp
    ```

2. **Install the required packages**:
    ```
    pip install -r requirements.txt
    ```

## Running the Dashboard
To start the dashboard, `cd` to the `app` directory: 
```
cd app
```

the run the dashboard with the command:
```
streamlit run main.py
```
This will launch the Streamlit application in your default web browser.

## Using the Dashboard

### Manual Input for Tasks
1. Navigate to the "Manual Input Tasks" page.
2. Fill in the task details, including task name, start time, end time, duration, nurses required, and active days.
3. Click "Add Task" to add the task to the DataFrame.
4. The current tasks will be displayed in a table below the form.
5. You can download the tasks as a CSV file using the "Download Data as CSV" button.

### Manual Input for Shifts
1. Navigate to the "Manual Input Shifts" page.
2. Fill in the shift details, including shift name, max nurses, start time, end time, break time, break duration, weight, and active days.
3. Click "Add Shift" to add the shift to the DataFrame.
4. The current shifts will be displayed in a table below the form.
5. You can download the shifts as a CSV file using the "Download Data as CSV" button.

### Schedule Overview
1. Navigate to the "Schedule" page.
2. Select a day to view the tasks scheduled for that day.
3. The tasks will be displayed in a timeline chart.
4. You can view the raw data by checking the "Show raw data" checkbox.

### Show Input Files
1. Navigate to the "Show Input Files" page.
2. The uploaded shifts and tasks files will be displayed in tables.
3. If no files are uploaded, you will see a message indicating that the files have not been uploaded yet.

## Solver
1. Navigate to the main page.
2. Upload the shifts and tasks files using the sidebar.
3. Enter the maximum time for the solver (in seconds) and the minimum number of nurses required.
4. Click "Generate Schedule" to run the solver.
5. The results will be displayed in tables below the form.

## Downloading Results
1. After generating the schedule, the results will be displayed on the main page.
2. You can download the shifts and tasks results as CSV files using the "Download Results" section.
