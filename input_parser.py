import pandas as pd
import os 

class InputParser:
    """
    To parse shifts and tasks into usable dataframe format. 
    """
    
    def __init__(self):
        pass

    @staticmethod
    def parse_input(filename: str) -> pd.DataFrame:

        "Returns dataframe from csv (excel) table"
        extensions = ['.csv', '.xlsx', '.xls',  '.xlsm', '.ods'    
         ]

        for ext in extensions:
            file_path = filename + ext
            print(file_path)
            if os.path.exists(file_path):
                if ext == '.csv':
                        df = pd.read_csv(file_path, sep=',')
                        if df.shape[1] == 1:
                            df = pd.read_csv(file_path, sep=';')
                        return df
                else:
                    return pd.read_excel(file_path, sheet_name=0)

        raise FileNotFoundError(f"No readable file found for {filename} with extensions: {extensions}")
    

    if __name__ == '__main__':
        shifts = parse_input('data/shifts')
        tasks = parse_input('data/tasks')

        print(shifts)
        print(tasks)



