from input_parser import InputParser
from solver import OptimalNurseSchedulerCP

def main():
    # import data

    # parse input
    parser = InputParser("data")
    shifts = parser.parse_input("shifts_hard")
    tasks = parser.parse_input("tasks")
    
    # Example usage
    scheduler = OptimalNurseSchedulerCP(shifts, tasks, min_nurses_anytime = 2, max_solve_time = 30)
    total_cost, tasks_solution_df, shifts_solution_df, intermediate_solutions = scheduler.solve()
    print("Intermediate solutions:", intermediate_solutions[0])
    print("Total cost is:", total_cost)
    print("\nAugmented tasks DataFrame:\n", tasks_solution_df)
    print("\nAugmented shifts DataFrame:\n", shifts_solution_df)
    
    # Dashboard

if __name__ == "__main__":
    main()