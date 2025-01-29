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
    tasks = parser.parse_input("tasks_500")

    # 2) Preprocess
    preprocessor = NurseSchedulingPreprocessor(shifts, tasks)
    preprocessor.process_data()

    shift_info = preprocessor.get_shift_info()
    shift_start_blocks = preprocessor.get_shift_start_blocks()
    tasks_info = preprocessor.get_tasks_info()
    task_map = preprocessor.get_task_map() 

    # 3a) Solve with CP solver
    cp_solver = OptimalNurseSchedulerCP(
        shift_info=shift_info,
        shift_start_blocks=shift_start_blocks,
        tasks_info=tasks_info,
        task_map=task_map,
        shifts_df_original=shifts,
        min_nurses_anytime=1,
        #max_solve_time=5.0
    )
    total_cost_CP, shift_usages_CP, task_solution_CP, intermediate_solutions_CP = cp_solver.solve()
    
    task_solution_CP.to_csv("data/tasks_solution_CP.csv", index=False)
    shift_usages_CP.to_csv("data/shifts_solution_CP.csv", index=False)

    if total_cost_CP is not None:
        print("\n--- CP Solver Results ---")
        print(f"Total cost: {total_cost_CP:.2f}")
        print("Shift usages:\n", shift_usages_CP)
        print("\nTasks solution:", task_solution_CP)
        # print("\nIntermediate solutions:")
        # for (obj_val, t) in intermediate_solutions_CP:
        #     print(f"  cost={obj_val}, time={t:.2f}s")
    else:
        print("No CP solution found.")

    # 3b) Solve with Gurobi solver
    gurobi_solver = GurobiNurseSolver(
        shift_info=shift_info,
        starting_blocks=shift_start_blocks,
        tasks_info=tasks_info,
        task_map=task_map,
        min_nurses_anytime=1,
        #max_time_in_seconds=30.0,
        shifts_df = shifts
    )
    total_cost_gurobi, shifts_solution_gurobi, tasks_solution_gurobi, intermediate_solutions_gurobi = gurobi_solver.solve()
    
    tasks_solution_gurobi.to_csv("data/tasks_solution_Gurobi.csv", index=False)
    shifts_solution_gurobi.to_csv("data/shifts_solution_Gurobi.csv", index=False)
    
    if shifts_solution_gurobi is not None:
        print("\n--- Gurobi Solver Results ---")
        print(f"Total cost: {total_cost_gurobi:.2f}")
        print("Shifts usages:\n", shifts_solution_gurobi)
        print("\nTasks solution:\n", tasks_solution_gurobi)
    else:
        print("No Gurobi solution found.")



if __name__ == "__main__":
    main()