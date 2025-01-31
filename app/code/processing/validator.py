import numpy as np
import pandas as pd

class Validator():
    """
    A Validator class to check and validate schedules for shifts and tasks.
    It helps to ensure that nurse coverage meets the required tasks coverage, 
    tasks are within their allowable time windows, and that constraints such as 
    maximum nurses allowed are not exceeded.
    """

    def __init__(self, shifts_df, tasks_df):
        """
        Constructor for the Validator class.

        Parameters:
        shifts_df (DataFrame): DataFrame containing shift information.
        tasks_df (DataFrame): DataFrame containing task information.

        Initializes:
        - self.shifts: only the shifts with non-zero 'usage'.
        - self.tasks: all tasks passed.
        - self.days: list of days for a week (monday to sunday).
        - self.shifts_coverage: an array tracking coverage from shifts over each quarter.
        - self.tasks_coverage: an array tracking coverage needed for tasks over each quarter.
        - self.N: total number of 15-minute intervals in a week (7 days * 24 hours * 4 quarters = 672).
        """
        self.shifts = shifts_df[shifts_df["usage"] != 0].copy()
        self.tasks = tasks_df
        self.days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        self.shifts_coverage = np.zeros((7 * 24 * 4), dtype=int)
        self.tasks_coverage = np.zeros((7 * 24 * 4), dtype=int)
        self.N = self.shifts_coverage.shape[0]

    @staticmethod
    def time_length(length):
        """
        Converts a length in minutes to the number of 15-minute intervals.
        Example: 30 minutes -> 2 intervals of 15 minutes each.
        """
        return int(length // 15)
    
    @staticmethod
    def to_quarter_of_day(time_str):
        """
        Converts a time string (HH:MM) into a quarter index of the day.
        For example, "01:00" -> 4 (since 1 hour = 4 * 15min).
        """
        hh, mm = time_str.split(":")
        hour = int(hh)
        minute = int(mm)
        return hour * 4 + minute // 15

    @staticmethod
    def get_end_day(start_time, end_time, start_day_index):
        """
        Determines the end day index for a shift that may cross midnight.

        If end_quarter < start_quarter, it means the shift passes midnight,
        so the end day is the next day; otherwise, it's the same day.
        """
        start_quarter = Validator.to_quarter_of_day(start_time)
        end_quarter = Validator.to_quarter_of_day(end_time)
        
        if end_quarter < start_quarter:  
            return (start_day_index + 1) % 7
        else:
            return start_day_index

    @staticmethod
    def get_shift_index(start_time, end_time, start_day_index, start_time_break, break_duration):
        """
        Returns the indices (start_index, end_index, start_break_index, end_break_index)
        representing quarters for shift and break times. Handles shifts that may cross midnight.
        """
        start_quarter = Validator.to_quarter_of_day(start_time)
        end_quarter = Validator.to_quarter_of_day(end_time)
        
        # Calculate end day index (handles midnight crossing)
        end_day_index = Validator.get_end_day(start_time, end_time, start_day_index)
        
        # Calculate actual working start index (add 1 for briefing)
        start_index = (start_day_index * 96 + start_quarter + 1) % 672
        end_index = (end_day_index * 96 + end_quarter + 1) % 672
        
        # Handle break times (calculate day index and quarter indices)
        start_break_quarter = Validator.to_quarter_of_day(start_time_break)
        start_break_day_index = Validator.get_end_day(start_time, start_time_break, start_day_index)
        
        # Calculate break start and end indices
        start_break_index = (start_break_day_index * 96 + start_break_quarter) % 672
        end_break_index = (start_break_index + Validator.time_length(break_duration) + 1) % 672
        
        return start_index, end_index, start_break_index, end_break_index

    def shift_coverage(self):
        """
        Populates self.shifts_coverage with the total coverage provided by all shifts.
        Each element in self.shifts_coverage represents the number of nurses available 
        in that 15-minute interval.
        """
        self.shifts_coverage = np.zeros((7 * 24 * 4), dtype=int)
        
        for _, shift in self.shifts.iterrows():
            for day in self.days:
                if shift[day] == 1:
                    # usage is how many nurses are assigned to the shift
                    usage = int(shift["usage"])
                    start_index, end_index, start_break_index, end_break_index = Validator.get_shift_index(
                        shift["start"], 
                        shift["end"], 
                        self.days.index(day), 
                        shift["break"], 
                        shift["break_duration"]
                    )
                    
                    # Check if there is a break in the shift
                    if break_duration := shift["break_duration"]:
                        if start_index < end_index:  
                            # Shift doesn't cross midnight
                            if start_break_index < end_break_index:  
                                # Break doesn't cross midnight
                                self.shifts_coverage[start_index:start_break_index] += usage
                                self.shifts_coverage[end_break_index:end_index] += usage
                            else:  
                                # Break crosses midnight
                                self.shifts_coverage[start_index:start_break_index] += usage
                                self.shifts_coverage[end_break_index:] += usage
                                self.shifts_coverage[:end_index] += usage
                        else:  
                            # Shift crosses midnight
                            if start_break_index < end_break_index:  
                                # Break doesn't cross midnight
                                if start_break_index > start_index:  
                                    # Break starts same day
                                    self.shifts_coverage[start_index:start_break_index] += usage
                                    self.shifts_coverage[end_break_index:] += usage
                                    self.shifts_coverage[:end_index] += usage
                                else:  
                                    # Break starts next day
                                    self.shifts_coverage[start_index:] += usage
                                    self.shifts_coverage[:start_break_index] += usage
                                    self.shifts_coverage[end_break_index:end_index] += usage
                            else:  
                                # Break crosses midnight
                                self.shifts_coverage[start_index:] += usage
                                self.shifts_coverage[:end_index] += usage
                    else:
                        # No break in the shift
                        if start_index < end_index:  
                            # Shift doesn't cross midnight
                            self.shifts_coverage[start_index:end_index] += usage
                        else:  
                            # Shift crosses midnight
                            self.shifts_coverage[start_index:] += usage
                            self.shifts_coverage[:end_index] += usage
        
        return self.shifts_coverage
    
    def get_unique_start_times(self, df):
        """
        Extracts unique (day, start_time) combinations from the DataFrame.
        This is used to add 1 nurse at the start of each shift for briefing.
        """
        combinations = []
        
        for _, row in df.iterrows():
            start_time = row['start'] 
            
            for day in self.days:
                # If the shift occurs on this day
                if row[day] == 1.0:
                    combinations.append({
                        'day': day,
                        'start_time': start_time
                    })
        
        result_df = pd.DataFrame(combinations).drop_duplicates()
        return result_df
    
    def get_task_index(start_window, solution_start, start_day_index, duration):
        """
        Calculates the start and end index for a given task based on its 
        start window, chosen solution start, and duration.
        """
        solution_start_quarter = Validator.to_quarter_of_day(solution_start)
        solution_start_day_index = Validator.get_end_day(start_window, solution_start, start_day_index)

        start_index = solution_start_day_index * 96 + solution_start_quarter
        end_index = (start_index + Validator.time_length(duration)) % 672
        
        return start_index, end_index

    def task_coverage(self):
        """
        Populates self.tasks_coverage with the total coverage required by all tasks
        in their chosen intervals. Each element in self.tasks_coverage represents 
        the number of nurses needed for tasks in that 15-minute interval.
        """
        for _, task in self.tasks.iterrows():
            required_nurses = task["required_nurses"]
            
            # Calculate the coverage interval based on start_window, solution_start, and day_index
            start_index, end_index = Validator.get_task_index(
                task["start_window"], 
                task["solution_start"], 
                task["day_index"], 
                task["duration"]
            )
            
            if start_index < end_index:
                # Task does not cross midnight
                self.tasks_coverage[start_index:end_index] += required_nurses
            else:
                # Task crosses midnight
                self.tasks_coverage[start_index:] += required_nurses
                self.tasks_coverage[:end_index] += required_nurses 
        
        # Add 1 nurse to brief the starting shifts
        shift_briefing = Validator.get_unique_start_times(self, self.shifts)       
        for _, row in shift_briefing.iterrows():
            start_index, _ = Validator.get_task_index(
                row['start_time'], 
                row['start_time'], 
                self.days.index(row['day']), 
                0
            )
            self.tasks_coverage[start_index] += 1
        
        return self.tasks_coverage

    def check_coverage(self):
        """
        Checks if the shift coverage meets or exceeds the tasks coverage
        at all times. Prints where more nurses are needed if coverage is insufficient.
        Returns True if coverage is sufficient everywhere, otherwise False.
        """
        all_valid = True
        coverage = self.shifts_coverage - self.tasks_coverage

        for i in range(self.N):
            if coverage[i] < 0:
                # Negative coverage means tasks require more nurses than provided
                print(f"{-coverage[i]} more nurses needed at index {i}")
                all_valid = False

        if all_valid:
            print("Shift coverage is valid")
        return all_valid
    
    def task_in_window(self):
        """
        Checks if each task's chosen start time (solution_start) falls within
        its allowable start window. If start_window <= end_window, it's a normal interval.
        Otherwise, it implies the window crosses midnight.
        Prints tasks which are out of the allowable window.
        Returns True if all tasks are in their window, otherwise False.
        """
        all_valid = True

        for _, task in self.tasks.iterrows():
            start_window = task["start_window"]
            end_window = task["end_window"]
            start_solution = task["solution_start"]

            # If the window doesn't cross midnight
            if start_window <= end_window:
                if start_window <= start_solution <= end_window:
                    continue
                else:
                    print(f"Task {task['original_task_idx']} not in window")
                    all_valid = False
            else:
                # Window crosses midnight scenario
                if start_window <= start_solution or start_solution <= end_window:
                    continue
                else:
                    print(f"Task {task['original_task_idx']} not in window")
                    all_valid = False
        if all_valid:
            print("All tasks are in window")
        return all_valid
    
    def check_max_nurses(self):
        """
        Ensures that for each shift, the number of nurses used (usage) 
        does not exceed the maximum number allowed (max_nurses).
        Prints if any shift exceeds the limit.
        Returns True if no shift exceeds its limit, otherwise False.
        """
        all_valid = True
        for _, shift in self.shifts.iterrows():
            usage = int(shift["usage"])
            max_nurses = shift["max_nurses"]
            if usage > max_nurses:
                print(f"Shift {shift['original_shift_idx']} has more nurses than allowed")
                all_valid = False
        if all_valid:
            print("All shifts don't exceed maximum number of nurses")
        return all_valid
    
    def always_nurses_available(self):
        """
        Checks if there is at least one nurse available at the any moment
        Prints if no nurse is available at index i.
        Returns True if there's always at least one nurse, otherwise False.
        """
        all_valid = True
        for i in range(0, self.N):
            if self.shifts_coverage[i] == 0:
                print(f"No nurses at index {i}")
                all_valid = False
        if all_valid:
            print("There are always 1 nurse available")
        return all_valid
    
    def validate_schedule(shifts, tasks):
        """
        Main method to validate the schedule. It performs:
        - Shift coverage calculation
        - Task coverage calculation
        - Checking of coverage sufficiency
        - Checking tasks' start times are within their windows
        - Checking for max nurses constraint
        - Checking for always available nurses (at each day's start)

        Prints validation results for each check.
        Returns True if the schedule is valid, otherwise False.
        """
        validator = Validator(shifts, tasks)
        validator.shift_coverage()
        validator.task_coverage()
        
        print("Checking nurses coverage:")
        coverage_valid = validator.check_coverage()
        print()

        print("Checking tasks in window:")
        window_valid = validator.task_in_window()
        print()

        print("Checking maximum number of nurses")
        max_nurses_valid = validator.check_max_nurses()
        print()

        print("Checking if there are always 1 nurse available")
        always_nurses_valid = validator.always_nurses_available()

        # Final determination based on the checks
        all_valid = coverage_valid and window_valid and max_nurses_valid and always_nurses_valid
        if all_valid:
            print("Schedule is valid")
            return True
        else:
            print("Schedule is invalid")
            return False
