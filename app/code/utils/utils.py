import pandas as pd
from typing import List
import os
from io import BytesIO
from code.solvers.cp_solver import OptimalNurseSchedulerCP
from code.solvers.gurobi_solver import GurobiNurseSolver
from code.processing.preprocess import NurseSchedulingPreprocessor


def solver_combined(shifts_df: pd.DataFrame, tasks_df: pd.DataFrame, max_time: int, min_nursers: int, solver: str) -> List[pd.DataFrame]:
    """
    This function takes in the shifts and tasks dataframes and returns the results of the solver.
    # Example of accessing the dataframes
    shifts_df_copy = shifts_df.copy()
    tasks_df_copy = tasks_df.copy()
    return [shifts_df_copy, tasks_df_copy]
    """

    if solver == "cp":
        return call_cp_solver(shifts_df, tasks_df, max_time, min_nursers)
    else:
        return call_gurobi_solver(shifts_df, tasks_df, max_time, min_nursers)
        #raise NotImplementedError("Only CP solver is implemented for now.")

    # time.sleep(5)
    
    # # return two placeholder dataframes

    # # return the shifts_df dataframe 
    # shifts_df_copy = shifts_df.copy()
    # tasks_df_copy = tasks_df.copy()


def call_gurobi_solver(shifts_df: pd.DataFrame, tasks_df: pd.DataFrame, max_time: int, min_nursers: int):
    
    # 2) Preprocess
    preprocessor = NurseSchedulingPreprocessor(shifts_df, tasks_df)
    preprocessor.process_data()

    shift_info = preprocessor.get_shift_info()
    shift_start_blocks = preprocessor.get_shift_start_blocks()
    tasks_info = preprocessor.get_tasks_info()
    task_map = preprocessor.get_task_map() 
    
    gurobi_solver = GurobiNurseSolver(
        shift_info=shift_info,
        starting_blocks=shift_start_blocks,
        tasks_info=tasks_info,
        task_map=task_map,
        min_nurses_anytime=min_nursers,
        max_time_in_seconds=max_time,
        shifts_df = shifts_df
    )

    total_cost_gurobi, shifts_solution_gurobi, tasks_solution_gurobi, intermediate_solutions_gurobi = gurobi_solver.solve()

    return shifts_solution_gurobi, tasks_solution_gurobi, total_cost_gurobi, intermediate_solutions_gurobi

def call_cp_solver(shifts_df: pd.DataFrame, tasks_df: pd.DataFrame, max_time: int, min_nursers: int):

    # 2) Preprocess
    preprocessor = NurseSchedulingPreprocessor(shifts_df, tasks_df)
    preprocessor.process_data()

    shift_info = preprocessor.get_shift_info()
    shift_start_blocks = preprocessor.get_shift_start_blocks()
    tasks_info = preprocessor.get_tasks_info()
    task_map = preprocessor.get_task_map() 

    cp_solver = OptimalNurseSchedulerCP(
        shift_info=shift_info,
        shift_start_blocks=shift_start_blocks,
        tasks_info=tasks_info,
        task_map=task_map,
        shifts_df_original=shifts_df,
        min_nurses_anytime=min_nursers,
        max_solve_time=max_time
    )

    total_cost, shifts_result_df, tasks_result_df, intermediate_solutions = cp_solver.solve()

    return shifts_result_df, tasks_result_df, total_cost, intermediate_solutions

class InputParser:
    """
    To parse shifts and tasks into a usable DataFrame format.
    """

    def __init__(self, data_directory="data"):
        """Initialize parser with a directory for data files."""
        self.data_dir = data_directory
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"Data directory does not exist: {self.data_dir}")

    def parse_input(self, file_input) -> pd.DataFrame:
        """Returns a dataframe from a CSV or Excel table."""
        
        extensions = ['.csv', '.xlsx', '.xls', '.xlsm', '.ods']
        
        if isinstance(file_input, str):
            # file_input is a file path
            for ext in extensions:
                file_path = os.path.join(self.data_dir, file_input + ext)
                print(f"Checking: {file_path}")

                if os.path.exists(file_path):
                    if ext == '.csv':
                        df = pd.read_csv(file_path, sep=',')
                        if df.shape[1] == 1:  # Handle possible incorrect separator
                            df = pd.read_csv(file_path, sep=';')
                        return df
                    else:
                        return pd.read_excel(file_path, sheet_name=0)
        elif isinstance(file_input, bytes):
            # file_input is file content
            return pd.read_csv(BytesIO(file_input))
        else:
            raise ValueError("Invalid file input type. Expected str or bytes.")

        raise FileNotFoundError(f"No readable file found for {file_input} in {self.data_dir} with extensions: {extensions}")
