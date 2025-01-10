from input_parser import InputParser
from solver import NurseSchedulingSolver

def main():
    # import data

    # parse input
    shifts = InputParser.parse_input('data/shifts.csv')
    tasks = InputParser.parse_input('data/tasks_easy.csv')
    
    # 2) Instantiate solver
    solver = NurseSchedulingSolver(
        shifts, 
        tasks,
        time_granularity=15,
        max_nurses=30
    )

    # 3) Solve
    solver.solve()

    # 4) Print solution
    solver.print_solution()

    # 5) Extract usage
    usage = solver.get_shift_usage()
    for info in usage:
        if info["activated"] == 1 and info["nurses"] > 0:
            print(info)
    
    # Dashboard



if __name__ == "__main__":
    main()