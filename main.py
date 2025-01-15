from input_parser import InputParser
from solver import OptimalNurseScheduler

def main():
    # import data

    # parse input
    shifts = InputParser.parse_input('data/shifts.csv')
    tasks = InputParser.parse_input('data/tasks.csv')
    
    # 2) Instantiate solver
    solver = OptimalNurseScheduler(
        shifts, 
        tasks,
        max_nurses_per_shift = 100
    )

    # 3) Solve
    solver.solve()

    # Dashboard

if __name__ == "__main__":
    main()