from input_parser import InputParser
from solver import OptimalNurseScheduler

def main():
    # import data

    # parse input
    parser = InputParser("data")
    shifts = parser.parse_input('shifts')
    tasks = parser.parse_input('tasks')
    print(shifts)
    print(tasks)
    
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