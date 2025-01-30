import numpy as np
import pandas as pd

class Validator():

    def __init__(self, shifts_df, tasks_df):
        self.shifts = shifts_df[shifts_df["usage"] != 0].copy()
        self.tasks = tasks_df
        self.days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        self.shifts_coverage = np.zeros((7 * 24 * 4), dtype=int)
        self.tasks_coverage = np.zeros((7 * 24 * 4), dtype=int)
        self.N = self.shifts_coverage.shape[0]

    @staticmethod
    def time_length(length):
        return int(length // 15)
    
    @staticmethod
    def to_quarter_of_day(time_str):
        hh, mm = time_str.split(":")
        hour = int(hh)
        minute = int(mm)
        return hour * 4 + minute // 15

    @staticmethod
    def get_end_day(start_time, end_time, start_day_index):
        start_quarter = Validator.to_quarter_of_day(start_time)
        end_quarter = Validator.to_quarter_of_day(end_time)
        
        if end_quarter < start_quarter:  
            return (start_day_index + 1) % 7
        else:
            return start_day_index

    @staticmethod
    def get_shift_index(start_time, end_time, start_day_index, start_time_break, break_duration):
        start_quarter = Validator.to_quarter_of_day(start_time)
        end_quarter = Validator.to_quarter_of_day(end_time)
        
        # Calculate end day index (for shifts crossing midnight)
        end_day_index = Validator.get_end_day(start_time, end_time, start_day_index)
        
        # Calculate actual working start index (after briefing quarter)
        start_index = (start_day_index * 96 + start_quarter + 1) % 672  # +1 for briefing
        end_index = (end_day_index * 96 + end_quarter+1) % 672
        
        # Handle break times
        start_break_quarter = Validator.to_quarter_of_day(start_time_break)
        start_break_day_index = Validator.get_end_day(start_time, start_time_break, start_day_index)
        
        # Calculate break indices
        start_break_index = (start_break_day_index * 96 + start_break_quarter) % 672
        end_break_index = (start_break_index + Validator.time_length(break_duration)+1) % 672
        
        return start_index, end_index, start_break_index, end_break_index

    def shift_coverage(self):
        self.shifts_coverage = np.zeros((7 * 24 * 4), dtype=int)
        
        for _, shift in self.shifts.iterrows():
            for day in self.days:
                if shift[day] == 1:
                    usage = int(shift["usage"])
                    start_index, end_index, start_break_index, end_break_index = Validator.get_shift_index(
                        shift["start"], 
                        shift["end"], 
                        self.days.index(day), 
                        shift["break"], 
                        shift["break_duration"]
                    )
                    
                    # Handle different cases for shift periods
                    if break_duration := shift["break_duration"]:  # If there is a break
                        if start_index < end_index:  # Shift doesn't cross midnight
                            if start_break_index < end_break_index:  # Break doesn't cross midnight
                                self.shifts_coverage[start_index:start_break_index] += usage
                                self.shifts_coverage[end_break_index:end_index] += usage
                            else:  # Break crosses midnight
                                self.shifts_coverage[start_index:start_break_index] += usage
                                self.shifts_coverage[end_break_index:] += usage
                                self.shifts_coverage[:end_index] += usage
                        else:  # Shift crosses midnight
                            if start_break_index < end_break_index:  # Break doesn't cross midnight
                                if start_break_index > start_index:  # Break starts same day
                                    self.shifts_coverage[start_index:start_break_index] += usage
                                    self.shifts_coverage[end_break_index:] += usage
                                    self.shifts_coverage[:end_index] += usage
                                else:  # Break starts next day
                                    self.shifts_coverage[start_index:] += usage
                                    self.shifts_coverage[:start_break_index] += usage
                                    self.shifts_coverage[end_break_index:end_index] += usage
                            else:  # Break crosses midnight
                                self.shifts_coverage[start_index:] += usage
                                self.shifts_coverage[:end_index] += usage
                    else:  # No break
                        if start_index < end_index:  # Shift doesn't cross midnight
                            self.shifts_coverage[start_index:end_index] += usage
                        else:  # Shift crosses midnight
                            self.shifts_coverage[start_index:] += usage
                            self.shifts_coverage[:end_index] += usage
        
        return self.shifts_coverage
    
    def get_unique_start_times(self, df):
       
        combinations = []
        
        for _, row in df.iterrows():
            start_time = row['start'] 
            
            for day in self.days:
                if row[day] == 1.0:  
                    combinations.append({
                        'day': day,
                        'start_time': start_time
                    })
        
        result_df = pd.DataFrame(combinations).drop_duplicates()
        return result_df
    

    
    def get_task_index(start_window, solution_start, start_day_index, duration):

        solution_start_quarter = Validator.to_quarter_of_day(solution_start)
        solution_start_day_index = Validator.get_end_day(start_window, solution_start, start_day_index)

        start_index = solution_start_day_index * 96 + solution_start_quarter
        end_index = (start_index + Validator.time_length(duration)) % 672
        
        return start_index, end_index


    def task_coverage(self):
        for _, task in self.tasks.iterrows():

            required_nurses = task["required_nurses"]
            
            start_index, end_index = Validator.get_task_index(task["start_window"], task["solution_start"], task["day_index"], task["duration"])
            if start_index < end_index:
                self.tasks_coverage[start_index:end_index] += required_nurses
            else:
                self.tasks_coverage[start_index:] += required_nurses
                self.tasks_coverage[:end_index] += required_nurses
        
        shift_briefing = Validator.get_unique_start_times(self, self.shifts)       #1 nurse to brief the starting shifts
        for _, row in shift_briefing.iterrows():
            start_index, _ = Validator.get_task_index(row['start_time'], row['start_time'], self.days.index(row['day']), 0)
            self.tasks_coverage[start_index] += 1
        
        return self.tasks_coverage

    def check_coverage(self):
        all_valid = True
        coverage = self.shifts_coverage - self.tasks_coverage

        for i in range(self.N):
            if coverage[i] < 0:
                print(f"{-coverage[i]} more nurses needed at index {i}")
                all_valid = False

        if all_valid:
            print("Shift coverage is valid")
        return all_valid
    
    def task_in_window(self):
        all_valid = True

        for _, task in self.tasks.iterrows():
            start_window = task["start_window"]
            end_window = task["end_window"]
            start_solution = task["solution_start"]

            if start_window <= end_window:
                if start_window <= start_solution <= end_window:
                    continue
                else:
                    print(f"Task {task['original_task_idx']} not in window")
                    all_valid = False
            else:
                if start_window <= start_solution or start_solution <= end_window:
                    continue
                else:
                    print(f"Task {task['original_task_idx']} not in window")
                    all_valid = False
        if all_valid:
            print("All tasks are in window")
        return all_valid
    
    def check_max_nurses(self):

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
        all_valid = True
        for i in range(0, self.N, 96):
            if self.shifts_coverage[i] == 0:
                print(f"No nurses at index {i}")
                all_valid = False
        if all_valid:
            print("There are always nurses")
        return all_valid
    
    def validate_schedule(shifts, tasks):
        validator = Validator(shifts, tasks)
        cov_shifts = validator.shift_coverage()
        cov_tasks = validator.task_coverage()
        
        print("Checking nurses coverage:")
        coverage_valid = validator.check_coverage()
        print()

        print("Checking tasks in window:")
        window_valid = validator.task_in_window()
        print()

        print("Checking maximum number of nurses")
        max_nurses_valid = validator.check_max_nurses()
        print()

        print("Checking if there are always nurses available")
        always_nurses_valid = validator.always_nurses_available()

        all_valid = coverage_valid and window_valid and max_nurses_valid
        if all_valid:
            print("Schedule is valid")
            return True
        else:
            print("Schedule is invalid")
            return False