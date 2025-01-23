"""
gurobi_solver.py

This file defines a Gurobi-based solver for the nurse scheduling problem,
using the preprocessed shift and task data from NurseSchedulingPreprocessor,
including task_map for final solution reconstruction.
"""

import time
import gurobipy as gp
from gurobipy import GRB
import pandas as pd
from preprocess import (
    TIME_GRAN,
    N_BLOCKS,
    block_to_minute,
    block_to_timestr,
)

class SolutionCallback:

    def __init__(self):
        self.solutions = []

    def __call__(self, model, where):
        if where == GRB.Callback.MIPSOL:
            # Query the objective value of the new solution
            best_objective = model.cbGet(GRB.Callback.MIPSOL_OBJ)
            self.solutions.append((best_objective,model.cbGet(GRB.Callback.RUNTIME)))

class GurobiNurseSolver:
    """Builds and solves the nurse scheduling problem in Gurobi,
    using preprocessed data (shift info, task info, and task_map).
    """

    def __init__(
        self,
        shift_info,
        starting_blocks,
        tasks_info,
        task_map,
        shifts_df,
        min_nurses_anytime=1,
        max_time_in_seconds=1e10,
    ):
        """Constructor for the GurobiNurseSolver.

        Args:
            shift_info (list): Preprocessed data about shifts.
            tasks_info (list): Preprocessed data about tasks.
            task_map (list of tuple): (original_task_idx, day_index) for each tasks_info entry.
            min_nurses_anytime (int, optional): The minimal coverage at any time. Defaults to 1.
            max_time_in_seconds (float, optional): Gurobi time limit in seconds. Defaults to 60.0.
        """
        self.shift_info = shift_info
        self.starting_blocks = starting_blocks
        self.tasks_info = tasks_info
        self.task_map = task_map
        self.min_nurses_anytime = min_nurses_anytime
      

        # Create the Gurobi model
        self.model = gp.Model("NurseScheduling_Gurobi")
        self.model.setParam("TimeLimit", max_time_in_seconds)

        # We'll store the final solution here
        self.usage_values = []
        self.shifts_solution_df = shifts_df.copy()
        self.tasks_solution_df = pd.DataFrame()

        # Internal sets
        self.T = range(1, N_BLOCKS + 1)
        self.S = range(1, len(self.shift_info) + 1)
        self.N = range(1, len(self.tasks_info) + 1)

        # Build the model
        self._build_model()

    def _build_model(self):
        """Build all variables, objective, and constraints in the Gurobi model."""
        # e[j, t] = shift coverage
        # h[j, t] = shift start
        self.e = {}
        # self.h = {}
        for j in self.S:
            coverage_array = self.shift_info[j - 1]["coverage"]
            # For the "start" logic, we assume there's a "starting_blocks" array
            # in shift_info or we need a loop to compute it. You might adjust
            # based on how your preprocessor is storing that data.
            # For demonstration, let's assume it stores 'coverage' in coverage_array
            # and 'starting_blocks' in a parallel array:

            # starting_blocks = self.shift_info[j - 1].get("starting_blocks", None)
            # if not starting_blocks:
            #     # If not stored, we can set them to 0 for now
            #     starting_blocks = [0]*N_BLOCKS

            for t in self.T:
                self.e[j, t] = coverage_array[t - 1] if (t - 1 < len(coverage_array)) else 0
                # self.h[j, t] = starting_blocks[t - 1] if (t - 1 < len(starting_blocks)) else 0

        self.h = {}
        for t in self.T:
            for j in self.S:
                self.h[j,t] = 1 if j-1 in self.starting_blocks[t-1] else 0

        # Build candidate blocks for tasks
        self.candidate_blocks = []
        for i in self.N:
            task = self.tasks_info[i - 1]
            eb = task["earliest_block"]
            lb = task["latest_block"]
            dur = task["duration_blocks"]

            c_blocks_for_i = []
            # range of possible starts is [0,lb - eb]
            for offset in range(0, lb - eb + 1):
                actual_start = eb + offset
                covered_list = [actual_start + k for k in range(dur)]
                c_blocks_for_i.append(covered_list)
            self.candidate_blocks.append(c_blocks_for_i)

        # Build g[i, j_idx, t]
        self.g = {}
        for i in self.N:
            c_size = len(self.candidate_blocks[i - 1])
            for j_idx in range(c_size):
                covered_list = self.candidate_blocks[i - 1][j_idx]
                for t in self.T:
                    self.g[i, j_idx + 1, t] = 1 if t-1 in covered_list else 0 ######################CHECK

        # Decision variables
        self.f = {}
        for i in self.N:
            c_size = len(self.candidate_blocks[i - 1])
            for j_idx in range(1, c_size + 1):
                self.f[i, j_idx] = self.model.addVar(
                    vtype=GRB.BINARY, name=f"f_{i}_{j_idx}"
                )

        self.u = {}
        for i in self.N:
            for t in self.T:
                self.u[i, t] = self.model.addVar(
                    vtype=GRB.BINARY, name=f"u_{i}_{t}"
                )

        self.k = {}
        for j in self.S:
            self.k[j] = self.model.addVar(
                vtype=GRB.INTEGER,
                lb=0,
                ub=self.shift_info[j - 1]["max_nurses"],
                name=f"k_{j}"
            )

        self.x = {}
        for t in self.T:
            self.x[t] = self.model.addVar(
                vtype=GRB.INTEGER, name=f"x_{t}"
            )

        self.n = {}
        for t in self.T:
            self.n[t] = self.model.addVar(
                vtype=GRB.INTEGER, name=f"n_{t}"
            )

        # Objective
        obj_expr = gp.quicksum(
            self.k[j]
            * self.shift_info[j - 1]["weight_scaled"] / 100.0
            * self.shift_info[j - 1]["length_blocks"]
            for j in self.S
        )
        self.model.setObjective(obj_expr, GRB.MINIMIZE)

        # Constraints
        # 1) Each task picks exactly one candidate start
        for i in self.N:
            c_size = len(self.candidate_blocks[i - 1])
            self.model.addConstr(
                gp.quicksum(self.f[i, jj] for jj in range(1, c_size + 1)) == 1,
                name=f"OneCandidate_{i}"
            )

        # 2) If task i is active at time t => sum of candidate covering t
        for i in self.N:
            c_size = len(self.candidate_blocks[i - 1])
            for t in self.T:
                self.model.addConstr(
                    self.u[i, t] >= gp.quicksum(
                        self.f[i, jj] * self.g[i, jj, t]
                        for jj in range(1, c_size + 1)
                    ),
                    name=f"TaskActive_{i}_{t}"
                )

        # 3) total tasks plus handover in x[t]
        for t in self.T:
            sum_task_demand = gp.quicksum(
                self.u[i, t] * self.tasks_info[i - 1]["required_nurses"]
                for i in self.N
            )
            sum_starts = gp.quicksum(
                self.k[j] * self.h[j, t]
                for j in self.S
            )
            self.model.addConstr(
                self.x[t] >= sum_task_demand + sum_starts + 1, # +1, as 1 person is doing the handover
                name=f"CoverageReq_{t}"
            )
            # also global min coverage
            self.model.addConstr(
                self.x[t] >= self.min_nurses_anytime,
                name=f"GlobalMin_{t}"
            )

        # 4) coverage from shifts
        for t in self.T:
            self.model.addConstr(
                self.n[t] <= gp.quicksum(
                    self.e[j, t] * self.k[j]
                    for j in self.S
                ),
                name=f"ShiftCoverage_{t}"
            )

        # 5) ensure n[t] >= x[t]
        for t in self.T:
            self.model.addConstr(
                self.n[t] >= self.x[t],
                name=f"NurseCover_{t}"
            )

    def solve(self):
        """Solve the Gurobi model and store the results internally.

        Returns:
            (shifts_solution_df, tasks_solution_df)
                or (None, None) if no solution found.
        """
        callback = SolutionCallback()
        self.model.optimize(callback)

        if self.model.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
            print("No feasible or optimal Gurobi solution found.")
            return (None, None)

        # SHIFT usage solution
        self.usage_values = [int(self.k[j].X) for j in self.S]

        # Alter DataFrame for the shifts solution
        self.shifts_solution_df['usage'] = self.usage_values
        

        # Build a DataFrame for tasks
        day_specific_records = []
        for i in self.N:
            tinfo = self.tasks_info[i - 1]
            # find chosen candidate
            c_size = len(self.candidate_blocks[i - 1])
            chosen_start_block = None
            for j_idx in range(1, c_size + 1):
                if self.f[i, j_idx].X > 0.5:
                    offset = (j_idx - 1)
                    chosen_start_block = tinfo["earliest_block"] + offset
                    break

            if chosen_start_block is None:
                chosen_start_block = tinfo["earliest_block"]

            # Retrieve from task_map
            orig_idx, day_index = self.task_map[i - 1]

            earliest_b = tinfo["earliest_block"]
            latest_b   = tinfo["latest_block"]
            dur_b      = tinfo["duration_blocks"]

            record = {
                "original_task_idx": orig_idx,
                "day_index": day_index,
                "task_name": tinfo["task_name"],
                "start_window": block_to_timestr(earliest_b),
                "end_window": block_to_timestr(latest_b),
                "solution_start": block_to_timestr(chosen_start_block),
                "duration": block_to_minute(dur_b),
                "required_nurses": tinfo["required_nurses"],
            }
            day_specific_records.append(record)

        tasks_solution_df = pd.DataFrame(day_specific_records)

        # Intermediate solutions
        intermediate_solutions = callback.solutions

        if self.model.status == GRB.OPTIMAL:
            print("Optimal Gurobi solution found.")
        else:
            print("Feasible Gurobi solution (not guaranteed optimal).")

        return (self.model.ObjVal,self.shifts_solution_df, tasks_solution_df, intermediate_solutions)

    def get_solution(self):
        """Get the final solution dataframes if solve() was successful.

        Returns:
            (self.shifts_solution_df, self.tasks_solution_df)
        """
        # This presupposes we have solved and stored them as instance variables
        # but for clarity we just re-run solve or store them in solve().
        pass