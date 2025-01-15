from input_parser import InputParser
from solver import OptimalNurseSchedulerCP

def main():
    # import data

    # parse input
    parser = InputParser("data")
    shifts = parser.parse_input("shifts_hard")
    tasks = parser.parse_input("tasks_hard")
    
    # Example usage
    scheduler = OptimalNurseSchedulerCP(shifts, tasks)
    total_cost, tasks_solution_df, shifts_solution_df = scheduler.solve()

    print("Total cost is:", total_cost)
    print("\nAugmented tasks DataFrame:\n", tasks_solution_df)
    print("\nAugmented shifts DataFrame:\n", shifts_solution_df)

    # Dashboard

if __name__ == "__main__":
    main()