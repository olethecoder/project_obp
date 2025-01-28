# User Guide for Project OBP

## Table of Contents
1. Introduction
2. Setup
3. Importing Data
4. Running the Dashboard
5. Using the Dashboard
    - Manual Input for Tasks
    - Manual Input for Shifts
    - Schedule Overview
    - Show Input Files
6. Solver
7. Downloading Results

## Introduction
Project OBP is a Streamlit-based application designed to help manage and optimize nurse scheduling. The application allows users to input tasks and shifts manually, view schedules, and solve for optimal nurse allocation.

## Setup
1. **Clone the repository**:
    ```
    git clone <repository-url>
    cd <repository-directory>
    ```

2. **Install the required packages**:
    ```
    pip install -r requirements.txt
    ```

3. **Import data from Google Sheets**:
    ```
    python import_data.py
    ```

## Importing Data
To import data from Google Sheets, run the `import_data.py` script:
```
python import_data.py
```
This will download the necessary CSV files into the `data` directory.

## Running the Dashboard
To start the dashboard, run the following command:
```
streamlit run app/app.py
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
