from input_parser import InputParser
from solver import NurseSchedulingSolver

def main():
    # import data

    # parse input
    shifts = InputParser.parse_input('data/shifts.csv')
    tasks = InputParser.parse_input('data/tasks_easy.csv')
    
    # 2) Instantiate the solver
    solver = NurseSchedulingSolver(
        shifts_df=shifts,
        tasks_df=tasks,
        time_granularity=15,
        max_nurses_per_shift=30
    )

    # 3) Solve
    solver.solve()

    # 4) Print / analyze solution
    solver.print_solution()

    # 5) Optionally get the solution usage as a dictionary
    usage = solver.get_solution_usage()
    if usage:
        print("\nNon-zero shift usages:", usage)
    
    # Dashboard



if __name__ == "__main__":
    main()