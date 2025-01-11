from input_parser import InputParser
from solver import NurseSchedulingSolver

def main():
    # import data

    # parse input
    shifts = InputParser.parse_input('data/shifts_test.csv')
    tasks = InputParser.parse_input('data/tasks.csv')
    
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
    print("\nUsage data:", usage)

    # Dashboard

if __name__ == "__main__":
    main()