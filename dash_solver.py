
import pandas as pd
from solver import NurseSchedulingSolver

def dash_solver(shifts, tasks):

    # 2) Instantiate solver
    solver = NurseSchedulingSolver(
        shifts, 
        tasks,
        max_nurses_per_shift = 100
    )

    # 3) Solve
    solver.solve()

    # 4) Print solution
    solver.print_solution()

    # 5) Extract usage
    usage = solver.get_solution_usage()
    return usage


if __name__ == "__main__":
    shifts_df = pd.read_csv('data/shifts.csv')
    tasks_df = pd.read_csv('data/tasks.csv')
    result = dash_solver(shifts_df, tasks_df)
    print(type(result))
    print(result)