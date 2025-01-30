"""
cp_solver.py

This file defines a CP-SAT solver class that uses the preprocessed data
from NurseSchedulingPreprocessor (including task_map). It builds a constraint
programming model and returns the final solution with references to task_map.
"""

import time
from ortools.sat.python import cp_model
import pandas
from code.processing.preprocess import (
    N_BLOCKS,
    block_to_minute,
    block_to_timestr,
    NurseSchedulingPreprocessor  # optionally used if we want to import
)

class IntermediateSolutionCallback(cp_model.CpSolverSolutionCallback):
    """Callback to capture intermediate solutions with their objective and solve times.

    Attributes:
        _start_time (float): Time when solver started.
        solutions (list of (float, float)): (objective_value, time_elapsed).
    """

    def __init__(self, start_time: float):
        super().__init__()
        self._start_time = start_time
        self.solutions = []

    def OnSolutionCallback(self):
        current_objective = self.ObjectiveValue()
        elapsed = time.time() - self._start_time
        print(f"Intermediate CP solution found. Cost={current_objective}, Time={elapsed:.2f}s")
        self.solutions.append((current_objective, elapsed))


class OptimalNurseSchedulerCP:
    """Builds and solves the nurse scheduling problem in CP-SAT using preprocessed data.

    Attributes:
        shift_info (list): Data about each shift (coverage, weight, length, etc.).
        shift_start_blocks (dict): Maps block -> list of shift indices starting at that block.
        tasks_info (list): Expanded day-specific tasks.
        task_map (list of tuple): (original_task_idx, day_index) for each task in tasks_info.
        min_nurses_anytime (int): Minimum required nurses at any time.
        max_solve_time (float): Maximum solver runtime in seconds.
    """

    def __init__(
        self,
        shift_info,
        shift_start_blocks,
        tasks_info,
        task_map,
        shifts_df_original,  # <-- NEW: pass the original shifts_df
        min_nurses_anytime: int = 0,
        max_solve_time: float = 60.0
    ):
        """Initialize the CP solver with preprocessed data and the original shifts_df.

        Args:
            shift_info (list): Preprocessed data about shifts (coverage arrays, etc.).
            shift_start_blocks (dict): Maps block -> list of shift indices that start there.
            tasks_info (list): Day-specific tasks data.
            task_map (list): (original_task_idx, day_index) for each tasks_info entry.
            shifts_df_original (pd.DataFrame): The complete original shifts DataFrame.
            min_nurses_anytime (int, optional): Global minimum nurses. Defaults to 0.
            max_solve_time (float, optional): CP solver time limit. Defaults to 60.
        """
        self.model = cp_model.CpModel()

        # Preprocessed data
        self.shift_info = shift_info
        self.shift_start_blocks = shift_start_blocks
        self.tasks_info = tasks_info
        self.task_map = task_map

        # Store the full original shifts DataFrame for final solution output
        self.shifts_df_original = shifts_df_original.copy()

        # Solver parameters
        self.min_nurses_anytime = min_nurses_anytime
        self.max_solve_time = max_solve_time

        # Internal lists for CP variables
        self.shift_usage_vars = []
        self.task_start_vars = []
        self.task_end_vars = []
        self.task_covers_bool = []

        # Build model constraints
        self._build_model()

    def _build_model(self):
        """Constructs the CP-SAT model: shift usage vars, coverage constraints,
        handover logic, minimum nurse requirements, and objective.
        """

        # 0) Adjust earliest/latest block ranges for tasks that span midnight on sunday
        # We handle this by adding N_BLOCKS to the latest block if it's less than the earliest block.
        # This way, we can treat the task as a contiguous range from earliest to latest block.
        # When adding the task coverage booleans, we'll wrap around the block index using %.
        self.adjusted_ranges = []
        for i, t in enumerate(self.tasks_info):
            e_b = t["earliest_block"]
            l_b = t["latest_block"]
            if l_b < e_b:
                l_b += N_BLOCKS 
            # store (e_b, l_b) so we can reuse them
            self.adjusted_ranges.append( (e_b, l_b) )

        # 1) SHIFT usage variables
        for s_idx, sh in enumerate(self.shift_info):
            # (Var1) SHIFT USAGE: integer var for how many nurses are assigned to shift s_idx.
            usage_var = self.model.NewIntVar(0, sh["max_nurses"], f"shift_{s_idx}_usage")
            self.shift_usage_vars.append(usage_var)

        # 2) TASK variables (start/end, coverage booleans)
        for i, t in enumerate(self.tasks_info):

            # (Var2) For each feasible block in [earliest_block .. latest_block + duration],
            # create a Boolean var indicating if the task covers block b.
            e_b, l_b = self.adjusted_ranges[i]
            d_b = t["duration_blocks"]
            covers_b = {}
            for b in range(e_b, l_b + d_b):
                b_mod = b % N_BLOCKS # wrap around
                covers_b[b_mod] = self.model.NewBoolVar(f"task_{i}_covers_{b_mod}")

            self.task_covers_bool.append(covers_b)

            # (Var3) For each day-specific task i, define start block
            start_var = self.model.NewIntVar(e_b, l_b, f"task_{i}_start")
            self.task_start_vars.append(start_var)

                
        # 3) Reify coverage booleans
        # (C1) If covers_b[b] = 1, it means the task i is active at block b:
        #       => start_var <= b < start_var + duration
        for i, t in enumerate(self.tasks_info):
            e_b, l_b = self.adjusted_ranges[i]  # same adjusted values
            d_b = t["duration_blocks"]
            covers_b = self.task_covers_bool[i] # dictionary we built in the previous step

            startv = self.task_start_vars[i]
            d_b = t["duration_blocks"]
            for ext_b in range(e_b, l_b + d_b):
                b_mod = ext_b % N_BLOCKS 
                boolvar = covers_b[b_mod]  # same dictionary from the creation step

                aux1 = self.model.NewBoolVar(f"aux1_{i}_{ext_b}") # startv <= b
                aux2 = self.model.NewBoolVar(f"aux2_{i}_{ext_b}") # b < startv + d_b

                # covers_b[b_mod] <=> (start_var <= ext_b < start_var + d_b)
                self.model.Add(startv <= ext_b).OnlyEnforceIf(aux1)
                self.model.Add(startv > ext_b).OnlyEnforceIf(aux1.Not())

                self.model.Add(ext_b < startv + d_b).OnlyEnforceIf(aux2) 
                self.model.Add(ext_b >= startv + d_b).OnlyEnforceIf(aux2.Not())

                self.model.AddBoolAnd([aux1, aux2]).OnlyEnforceIf(boolvar)
                self.model.AddBoolOr([aux1.Not(), aux2.Not()]).OnlyEnforceIf(boolvar.Not())

        # 4) HANDOVER logic
        # (Var4) starts_at[b] = sum( usage_s for all shifts that start at block b )
        starts_at = [0]*N_BLOCKS
        max_possible_usage_per_block = [0]*N_BLOCKS

        for b in range(N_BLOCKS):
            if b in self.shift_start_blocks:
                max_possible_usage_per_block[b] = sum(
                    self.shift_info[s]["max_nurses"] for s in self.shift_start_blocks[b]
                )

        for b in range(N_BLOCKS):
            if b in self.shift_start_blocks:
                starts_at[b] = cp_model.LinearExpr.Sum(
                    [self.shift_usage_vars[s] for s in self.shift_start_blocks[b]]
                )
            else:
                starts_at[b] = 0

        # (Var5) h[b] = 1 if any nurse starts at block b, else 0
        h = []
        for b in range(N_BLOCKS):
            hb = self.model.NewBoolVar(f"handover_{b}")
            h.append(hb)
            M = max_possible_usage_per_block[b]
            # (C3a) If sum usage >=1 => h[b]=1, else h[b]=0
            if M > 0:
                self.model.Add(starts_at[b] <= M * hb)
                self.model.Add(starts_at[b] >= hb)
            else:
                self.model.Add(hb == 0)

        # 5) COVERAGE constraints
        # (C2) Effective coverage(b) = sum( shift usage active at b ) - starts_at[b] - h[b]
        #      must be >= tasks demand(b) and >= min_nurses_anytime
        for b in range(N_BLOCKS):
            coverage_terms = []
            for s_idx, sh in enumerate(self.shift_info):
                if sh["coverage"][b] > 0:
                    coverage_terms.append(self.shift_usage_vars[s_idx])

            # sum of tasks demands in block b
            task_demands = []
            for i, t in enumerate(self.tasks_info):
                if b in self.task_covers_bool[i]:
                    req = t["required_nurses"]
                    boolvar = self.task_covers_bool[i][b]
                    task_demands.append(req * boolvar)

            effective_coverage = (
                cp_model.LinearExpr.Sum(coverage_terms)
                - starts_at[b]
                - h[b]
            )

            demand_expr = cp_model.LinearExpr.Sum(task_demands)

            # (C3) coverage >= sum of task demands
            self.model.Add(effective_coverage >= demand_expr)

            # (C4) coverage >= global min nurses (if set)
            if self.min_nurses_anytime > 0:
                self.model.Add(cp_model.LinearExpr.Sum(coverage_terms) >= self.min_nurses_anytime) 

        # 6) OBJECTIVE: Minimize total cost
        # (C5) cost = sum( usage_s * length_blocks_s * weight_s )
        cost_terms = []
        for s_idx, sh in enumerate(self.shift_info):
            usage_var = self.shift_usage_vars[s_idx]
            blocks_count = sh["length_blocks"]
            w_scaled = sh["weight_scaled"]
            cost_terms.append(usage_var * blocks_count * w_scaled)

        self.model.Minimize(cp_model.LinearExpr.Sum(cost_terms))


    def solve(self):
        """
        Solve the CP model and return the final solution as:
            total_cost (float),
            shifts_solution_df (DataFrame),
            tasks_solution_df (DataFrame),
            intermediate_solutions (list of (objective, time_s)).
        """
        import pandas as pd
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 8
        solver.parameters.max_time_in_seconds = self.max_solve_time

        start_time = time.time()
        callback = IntermediateSolutionCallback(start_time)

        status = solver.SolveWithSolutionCallback(self.model, callback)
        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print("No solution found.")
            return (None, None, None, [])

        # 1) Extract cost (scaled)
        total_cost_scaled = solver.ObjectiveValue()
        total_cost = total_cost_scaled / 100.0

        # 2) SHIFT usage solution
        usage_values = [solver.Value(var) for var in self.shift_usage_vars]

        # Create a complete shifts DataFrame from the original input, adding "usage"
        # We assume shift_info[i] corresponds to row i in self.shifts_df_original.
        shifts_solution_df = self.shifts_df_original.copy()
        shifts_solution_df["usage"] = usage_values

        # 3) TASKS solution
        task_records = []
        for i, tinfo in enumerate(self.tasks_info):
            start_block = solver.Value(self.task_start_vars[i])
            earliest_b  = tinfo["earliest_block"]
            latest_b    = tinfo["latest_block"]
            dur_b       = tinfo["duration_blocks"]
            (orig_task_idx, day_index) = self.task_map[i]

            record = {
                "original_task_idx": orig_task_idx,
                "day_index": day_index,
                "task_name": tinfo["task_name"],
                "start_window": block_to_timestr(earliest_b),
                "end_window": block_to_timestr(latest_b),
                "solution_start": block_to_timestr(start_block),
                "duration": block_to_minute(dur_b),
                "required_nurses": tinfo["required_nurses"]
            }
            task_records.append(record)

        tasks_solution_df = pd.DataFrame(task_records)

        # 4) Collect intermediate solutions
        intermediate_solutions = callback.solutions
        print(f"Final CP solution: cost={total_cost:.2f}, status={solver.StatusName(status)}")

        return (total_cost, shifts_solution_df, tasks_solution_df, intermediate_solutions)

