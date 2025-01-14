import pandas as pd

class InputParser:
    """
    To parse shifts and tasks into usable dataframe format. 
    """
    
    def __init__(self):
        pass

    @staticmethod
    def parse_input(path_to_file: str) -> pd.DataFrame:

        "Returns dataframe from csv (excel) table"

        df = pd.read_csv(path_to_file)

        return df
    

    if __name__ == '__main__':
        shifts = parse_input('data/shifts.csv')
        tasks = parse_input('data/tasks.csv')

        print(shifts)
        print(tasks)
    



