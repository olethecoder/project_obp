from input_parser import InputParser
from cp_solver import OptimalNurseSchedulerCP
from preprocess import NurseSchedulingPreprocessor
from gurobi_solver import GurobiNurseSolver

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

class ResultAnalyzer:

    def __init__(self,cp_solver, gurobi_solver):
        self.cp_solver = cp_solver
        self.gurobi_solver = gurobi_solver

        self.cp_results = pd.DataFrame(columns = ['Run', 'Costs', 'Time'])
        self.gurobi_results = pd.DataFrame(columns = ['Run', 'Costs', 'Time'])

    

    def _generate_cpresults(self, number_iterations):


        for i in range(number_iterations):
            total_cost_CP, shift_usages_CP, task_solution_CP, intermediate_solutions_CP = self.cp_solver.solve()
            
            costs, time = ResultAnalyzer.extract_elements(intermediate_solutions_CP)
            
            new_data = pd.DataFrame({'Run': [i + 1 for x in range(len(intermediate_solutions_CP))], 
                         'Costs': costs, 
                         'Time': time})
            
            if i ==0:
                self.cp_results = new_data
            else:
                self.cp_results = pd.concat([self.cp_results, new_data], ignore_index=True)


            # self.cp_results._append(pd.DataFrame({'Run': [i+1 for x in range(len(intermediate_solutions_CP))], 'Costs': costs, 'Time': time}), ignore_index = True)

        print(self.cp_results)
        self.cp_results = ResultAnalyzer.bin_results(self.cp_results)
        print(self.cp_results)


    @staticmethod
    def extract_elements(intermediate_solutions_CP):
        return [objective for (objective, time) in intermediate_solutions_CP], [time for (objective, time) in intermediate_solutions_CP]
        
    @staticmethod
    def bin_results(df):
        # Define bin size (e.g., 1-second bins)
        bin_size = 1  # Adjust this value as needed

        # Calculate bin edges based on the minimum and maximum of the Time column
        min_time = df['Time'].min()
        max_time = df['Time'].max()
        bin_edges = np.arange(min_time, max_time + bin_size, bin_size)

        # Create a new column for binned time
        df['Time_Bin'] = pd.cut(df['Time'], bins=bin_edges, labels=bin_edges[:-1], include_lowest=True)

        # Group by the new bins and calculate aggregated costs
        aggregated = df.groupby('Time_Bin').agg(
                                                Mean_Costs=('Costs', 'mean'),
                                                Std_Dev_Costs=('Costs', 'std'),
                                                Run_Count=('Run', 'count')).reset_index()
        
        return aggregated
            

    def _generate_gurobiresults(self, number_iterations):
        pass

    def _visualise_results(self):
    
        # Plot
        plt.figure(figsize=(10, 6))
        plt.errorbar(
            self.cp_results['Time_Bin'],
            self.cp_results['Mean_Costs'],
            yerr=self.cp_results['Std_Dev_Costs'],
            fmt='-o',
            ecolor='gray',
            capsize=5,
            label='Mean Costs with Std Dev'
        )

        # Labels and Title
        plt.xlabel('Time Bins')
        plt.ylabel('Mean Costs')
        plt.title('Mean Costs over Time with Error Bounds (Std Dev)')
        plt.grid(True)
        plt.legend()

        # Show Plot
        plt.tight_layout()
        plt.show()


        
if __name__ == '__main__':
    # 1) parse data
    # --------------------------------------------------
    parser = InputParser("data")
    shifts = parser.parse_input("shifts_hard")
    tasks = parser.parse_input("tasks_hard")

    # 2) Preprocess
    preprocessor = NurseSchedulingPreprocessor(shifts, tasks)
    preprocessor.process_data()

    shift_info = preprocessor.get_shift_info()
    shift_start_blocks = preprocessor.get_shift_start_blocks()
    tasks_info = preprocessor.get_tasks_info()
    task_map = preprocessor.get_task_map() 

    # 3a) Solve with CP solver
    cp_solver = OptimalNurseSchedulerCP(
        shift_info=shift_info,
        shift_start_blocks=shift_start_blocks,
        tasks_info=tasks_info,
        task_map=task_map,
        shifts_df_original=shifts,
        min_nurses_anytime=1,
        max_solve_time=30.0
    )

    # Visualise results over 100 iterations on hard instance

    analyzer = ResultAnalyzer(cp_solver, None)
    analyzer._generate_cpresults(2)
    analyzer._visualise_results()