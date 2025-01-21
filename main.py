from input_parser import InputParser
from cp_solver import OptimalNurseSchedulerCP
from preprocess import NurseSchedulingPreprocessor
from gurobi_solver import GurobiNurseSolver

def main():
    # import data

    # --------------------------------------------------
    # 1) parse data
    # --------------------------------------------------
    parser = InputParser("data")
    shifts = parser.parse_input("shifts_hard")
    tasks = parser.parse_input("tasks")
    
    # 2) Preprocess
    preprocessor = NurseSchedulingPreprocessor(shifts, tasks)
    preprocessor.process_data()

    shift_info = preprocessor.get_shift_info()
    shift_start_blocks = preprocessor.get_shift_start_blocks()
    tasks_info = preprocessor.get_tasks_info()
    task_map = preprocessor.get_task_map()  # <--- here's the new map

    # 3a) Solve with CP solver
    cp_solver = OptimalNurseSchedulerCP(
        shift_info=shift_info,
        shift_start_blocks=shift_start_blocks,
        tasks_info=tasks_info,
        task_map=task_map,
        min_nurses_anytime=1,
        max_solve_time=30.0
    )
    total_cost, shift_usages, task_solution, intermediate_solutions = cp_solver.solve()

    if total_cost is not None:
        print("\n--- CP Solver Results ---")
        print(f"Total cost: {total_cost:.2f}")
        print("Shift usages:", shift_usages)
        print("\nTasks solution:")
        for rec in task_solution:
            print(rec)
        print("\nIntermediate solutions:")
        for (obj_val, t) in intermediate_solutions:
            print(f"  cost={obj_val}, time={t:.2f}s")
    else:
        print("No CP solution found.")

    # 3b) Solve with Gurobi solver
    gurobi_solver = GurobiNurseSolver(
        shift_info=shift_info,
        tasks_info=tasks_info,
        task_map=task_map,
        min_nurses_anytime=1,
        max_time_in_seconds=30.0,
    )
    shifts_solution_df, tasks_solution_df = gurobi_solver.solve()
    if shifts_solution_df is not None:
        print("\n--- Gurobi Solver Results ---")
        print("Shifts solution:\n", shifts_solution_df)
        print("\nTasks solution:\n", tasks_solution_df)
    else:
        print("No Gurobi solution found.")


if __name__ == "__main__":
    main()