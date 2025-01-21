import numpy as np
import pandas as pd

class UnitTest():
    def __init__(self, shifts_df, tasks_df):
        super().__init__() 
        print("\nInitializing Unit Test...")

        self.shifts = shifts_df[shifts_df["usage"] != 0].copy()
        self.tasks = tasks_df
        self.days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        self.shifts_coverage = np.zeros((7, 24 * 4), dtype=int)
        self.tasks_coverage = np.zeros((7, 24 * 4), dtype=int)
        self.n = self.shifts_coverage.shape[1]
        
        print(f"Loaded {len(self.shifts)} active shifts and {len(self.tasks)} tasks")

    @staticmethod
    def times_to_quarter_index(time_input):
        def convert(time_str):
            try:
                if ':' in time_str:
                    hours, minutes = map(int, time_str.split(':'))
                else:
                    hours, minutes = map(int, time_str.split('.'))
                
                if not (0 <= hours < 24 and 0 <= minutes < 60):
                    raise ValueError(f"Invalid time: {time_str}")
                    
                return (hours * 4) + (minutes // 15)
            except Exception as e:
                print(f"Error converting time '{time_str}': {str(e)}")
                raise
        
        if isinstance(time_input, pd.Series):
            return time_input.map(convert)
        else:
            return convert(time_input)

    @staticmethod
    def quarter_index_to_time(index):
        hours = index // 4
        minutes = (index % 4) * 15
        return f"{hours:02d}:{minutes:02d}"
    
    @staticmethod
    def time_length(length):
        return int(length // 15)
       
    def same_end_day(self):
        print("\nCalculating same-day end flags...")
        try:
            self.shifts["same_end_day"] = self.times_to_quarter_index(self.shifts["end"]) > self.times_to_quarter_index(self.shifts["start"])
            self.tasks["same_end_day"] = self.times_to_quarter_index(self.tasks["end_window"]) > self.times_to_quarter_index(self.tasks["start_window"])
            print("Successfully calculated same-day flags")
        except Exception as e:
            print(f"Error in same_end_day calculation: {str(e)}")
            raise

    def shifts_coverage_matrix(self):
        print("\nCalculating shifts coverage matrix...")
        for _, shift in self.shifts.iterrows():
            for day in self.days:
                if shift[day] == 1:
                    day_idx = self.days.index(day)
                    try:
                        start_shifts_idx = int(self.times_to_quarter_index(shift["start"]))
                        break_shifts_idx = int(self.times_to_quarter_index(shift["break"]))
                        end_shifts_idx = int(self.times_to_quarter_index(shift["end"]))
                        break_length = int(self.time_length(shift["break_duration"]))
                        
                        # Same logic as before, but with integer indices
                        if start_shifts_idx <= break_shifts_idx and start_shifts_idx < end_shifts_idx:
                            self.shifts_coverage[day_idx, start_shifts_idx : break_shifts_idx] += shift["usage"]
                            self.shifts_coverage[day_idx, break_shifts_idx + break_length : end_shifts_idx] += shift["usage"]
                        elif start_shifts_idx <= break_shifts_idx and break_shifts_idx + break_length < self.n and start_shifts_idx >= end_shifts_idx:
                            self.shifts_coverage[day_idx, start_shifts_idx : break_shifts_idx] += shift["usage"]
                            self.shifts_coverage[day_idx, break_shifts_idx : self.n] += shift["usage"]
                            next_day_idx = 0 if day == "sunday" else day_idx + 1
                            self.shifts_coverage[next_day_idx, 0 : end_shifts_idx] += shift["usage"]
                        else:
                            self.shifts_coverage[day_idx, start_shifts_idx : self.n] += shift["usage"]
                            next_day_idx = 0 if day == "sunday" else day_idx + 1
                            self.shifts_coverage[next_day_idx, 0 : break_shifts_idx] += shift["usage"]
                            self.shifts_coverage[next_day_idx, break_shifts_idx + break_length : end_shifts_idx] += shift["usage"]
                    
                    except Exception as e:
                        print(f"Error processing shift on {day}: {str(e)}")
                        print(f"Shift details: start={shift['start']}, break={shift['break']}, end={shift['end']}")
                        raise

        print("Successfully calculated shifts coverage matrix")

    def tasks_coverage_matrix(self):
        print("\nCalculating tasks coverage matrix...")
        for idx, task in self.tasks.iterrows():
            if task["duration"] == 0:
                print(f"Skipping task {idx} with zero duration")
                continue 
            
            try:
                day_idx = int(task["day_index"])
                if not 0 <= day_idx <= 6:
                    raise ValueError(f"Invalid day index {day_idx} for task {idx}")
                
                start_tasks_idx = int(self.times_to_quarter_index(task["solution_start"]))
                end_tasks_idx = int(start_tasks_idx + self.time_length(task["duration"]))
                
                if end_tasks_idx < self.n:
                    self.tasks_coverage[day_idx, start_tasks_idx : end_tasks_idx] += task["required_nurses"]
                else:
                    overlap = end_tasks_idx - self.n
                    self.tasks_coverage[day_idx, start_tasks_idx : self.n] += task["required_nurses"]
                    next_day_idx = 0 if day_idx == 6 else day_idx + 1
                    self.tasks_coverage[next_day_idx, 0 : overlap] += task["required_nurses"]
            
            except Exception as e:
                print(f"Error processing task {idx}: {str(e)}")
                print(f"Task details: day={task['day_index']}, start={task['solution_start']}, duration={task['duration']}")
                raise
        
        print("Successfully calculated tasks coverage matrix")

    def check_coverage_sufficiency(self):
        print("\nChecking coverage sufficiency...")
        shortages = self.tasks_coverage > self.shifts_coverage

        if np.any(shortages):
            print("\nCoverage shortages detected at these times and days:")
            shortage_count = 0
            for day_idx in range(7):
                day_shortages = []
                for time_idx in range(24 * 4):
                    if shortages[day_idx, time_idx]:
                        shortage_count += 1
                        day_shortages.append(
                            f"    {self.quarter_index_to_time(time_idx)}: "
                            f"Need {self.tasks_coverage[day_idx, time_idx]} nurses, "
                            f"Have {self.shifts_coverage[day_idx, time_idx]}"
                        )
                if day_shortages:
                    print(f"\n  {self.days[day_idx].capitalize()}:")
                    print("\n".join(day_shortages))
            
            print(f"\nTotal shortage points: {shortage_count}")
            return False
        else:
            print("All shifts fully cover the task requirements ✓")
            return True

    def check_solution_times(self):
        print("\nChecking if all tasks start within their time windows...")
    
        def is_time_in_window(row):
            # Handle both string and integer inputs
            def get_index(value):
                if isinstance(value, str):
                    return self.times_to_quarter_index(value)
                return int(value)  # Already an index
            
            start = get_index(row['start_window'])
            end = get_index(row['end_window'])
            solution = get_index(row['solution_start'])
            same_day = row['same_end_day']
            
            if same_day:
                return (solution >= start) and (solution <= end)
            else:
                if solution >= start or solution <= end:
                    return True
                return False

        try:
            self.tasks['is_valid'] = self.tasks.apply(is_time_in_window, axis=1)
            
            invalid_tasks = self.tasks[~self.tasks['is_valid']]
            all_valid = len(invalid_tasks) == 0
            
            if all_valid:
                print("All tasks start within their designated time windows ✓")
                return True, "All tasks start within their designated time windows."
            else:
                print(f"\nFound {len(invalid_tasks)} task(s) with invalid start times:")
                invalid_details = []
                for idx, task in invalid_tasks.iterrows():
                    if task['same_end_day']:
                        window = f"[{task['start_window']}-{task['end_window']}]"
                    else:
                        window = f"[{task['start_window']}-96] or [0-{task['end_window']}]"
                    invalid_details.append(f"Task {idx}: Starts at {task['solution_start']} but window is {window}")
                
                message = "\n".join(invalid_details)
                print(message)
                return False, message
                
        except Exception as e:
            print(f"Error checking solution times: {str(e)}")
            raise