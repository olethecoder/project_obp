import numpy as np
import pandas as pd

class UnitTest():

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
        return hour * 4 + (minute // 15)
    
    @staticmethod
    def get_end_day(start_time, end_time, start_day_index):

        start_quarter = UnitTest.to_quarter_of_day(start_time)
        end_quarter = UnitTest.to_quarter_of_day(end_time)

        if end_quarter < start_quarter:
            return (start_day_index + 1) % 7
        else:
            return start_day_index
        
    @staticmethod
    def get_shift_index(start_time, end_time, start_day_index, start_time_break, break_duration):

        start_quarter = UnitTest.to_quarter_of_day(start_time)
        end_quarter   = UnitTest.to_quarter_of_day(end_time)

        end_day_index = UnitTest.get_end_day(start_time, end_time, start_day_index)

        start_index = (start_day_index * 96 + start_quarter + 1) % 672     #+1 because at beginning of shift nurse is briefed
        end_index   = end_day_index * 96 + end_quarter

        #break 
        start_break_quarter = UnitTest.to_quarter_of_day(start_time_break)
        start_break_day_index = UnitTest.get_end_day(start_time, start_time_break, start_day_index)

        start_break_index = start_break_day_index * 96 + start_break_quarter
        end_break_index = (start_break_index + UnitTest.time_length(break_duration)) % 672

        return start_index, end_index, start_break_index, end_break_index
    
    @staticmethod
    def get_task_index(start_time, start_day_index, duration):
        
        start_quarter = UnitTest.to_quarter_of_day(start_time)
        start_index = start_day_index * 96 + start_quarter
        end_index = (start_index + UnitTest.time_length(duration)) % 672
        return start_index, end_index

    
    def shift_coverage(self):
        for _, shift in self.shifts.iterrows():
            for day in self.days:
                if shift[day] == 1:
                    usage = int(shift["usage"])
                    start_index, end_index, start_break_index, end_break_index = UnitTest.get_shift_index(shift["start"], shift["end"], self.days.index(day), shift["break"], shift["break_duration"])
                    if start_index < end_index:
                        self.shifts_coverage[start_index:start_break_index] += usage
                        self.shifts_coverage[end_break_index:end_index] += usage
                    elif start_index < start_break_index and start_break_index < end_break_index:
                        self.shifts_coverage[start_index:start_break_index] += usage
                        self.shifts_coverage[end_break_index:] += usage
                        self.shifts_coverage[:end_index] += usage
                    elif start_index < start_break_index and start_break_index > end_break_index:
                        self.shifts_coverage[start_index:start_break_index] += usage
                        self.shifts_coverage[end_break_index:end_index] += usage
                    else:
                        self.shifts_coverage[start_index:] += usage
                        self.shifts_coverage[:start_break_index] += usage
                        self.shifts_coverage[end_break_index:end_index] += usage
        print(self.shifts_coverage)
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
    
    def task_coverage(self):
        for _, task in self.tasks.iterrows():

            required_nurses = task["required_nurses"]
            
            start_index, end_index = UnitTest.get_task_index(task["solution_start"], task["day_index"], task["duration"])
            if start_index < end_index:
                self.tasks_coverage[start_index:end_index] += required_nurses
            else:
                self.tasks_coverage[start_index:] += required_nurses
                self.tasks_coverage[:end_index] += required_nurses
        
        shift_briefing = UnitTest.get_unique_start_times(self, self.shifts)       #1 nurse to brief the starting shifts
        for _, row in shift_briefing.iterrows():
            start_index, _ = UnitTest.get_task_index(row['start_time'], self.days.index(row['day']), 0)
            self.tasks_coverage[start_index] += 1
        
        print(self.tasks_coverage)
        return self.tasks_coverage

    def check_coverage(self):
        all_valid = True
        coverage = self.shifts_coverage - self.tasks_coverage

        for i in range(self.N):
            if coverage[i] < 0:
                print(f"{-coverage[i]} more nurses needed at index {i}")
                all_valid = False
        return all_valid
