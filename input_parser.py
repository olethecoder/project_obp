import os
import pandas as pd

class InputParser:
    """
    To parse shifts and tasks into a usable DataFrame format.
    """

    def __init__(self, data_directory="data"):
        """Initialize parser with a directory for data files."""
        self.data_dir = data_directory
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"Data directory does not exist: {self.data_dir}")

    def parse_input(self, filename: str) -> pd.DataFrame:
        """Returns a dataframe from a CSV or Excel table."""
        
        extensions = ['.csv', '.xlsx', '.xls', '.xlsm', '.ods']
        
        for ext in extensions:
            file_path = os.path.join(self.data_dir, filename + ext)
            print(f"Checking: {file_path}")

            if os.path.exists(file_path):
                if ext == '.csv':
                    df = pd.read_csv(file_path, sep=',')
                    if df.shape[1] == 1:  # Handle possible incorrect separator
                        df = pd.read_csv(file_path, sep=';')
                    return df
                else:
                    return pd.read_excel(file_path, sheet_name=0)

        raise FileNotFoundError(f"No readable file found for {filename} in {self.data_dir} with extensions: {extensions}")

# Run this only in a script (not Jupyter Notebook)
if __name__ == '__main__':
    parser = InputParser()  # Create an instance
    shifts = parser.parse_input("shifts")  # No need for "data/" prefix
    tasks = parser.parse_input("tasks")

    print("Shifts DataFrame:\n", shifts.head())
    print("\nTasks DataFrame:\n", tasks.head())
