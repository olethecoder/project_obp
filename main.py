from input_parser import InputParser
from solver import OptimalNurseSchedulerCP

def main():
    # import data

    # parse input
    parser = InputParser("data")
    shifts = parser.parse_input("shifts")
    tasks = parser.parse_input("tasks")
    
    # 2) Instantiate solver
    solver = OptimalNurseSchedulerCP(
        shifts,
        tasks,
    )

    # 3) Solve
    solver.solve()

    # Dashboard

if __name__ == "__main__":
    main()