import pandas as pd
from typing import List
import os
import time
from io import BytesIO


def solver_combined(shifts_df: pd.DataFrame, tasks_df: pd.DataFrame) -> List[pd.DataFrame]:
    """
    This function takes in the shifts and tasks dataframes and returns the results of the solver.
    # Example of accessing the dataframes
    shifts_df_copy = shifts_df.copy()
    tasks_df_copy = tasks_df.copy()
    return [shifts_df_copy, tasks_df_copy]
    """

    time.sleep(0.5)
    
    # return two placeholder dataframes

    shifts_df_copy = shifts_df.copy()
    tasks_df_copy = tasks_df.copy()

    return [shifts_df_copy, tasks_df_copy]


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