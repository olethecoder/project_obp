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
from code.processing.preprocess import (
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
            starting_blocks (list): For each shift, list of N_BLOCKS indicating for each t whether shift has starting point using 0 or 1.
            tasks_info (list): Preprocessed data about tasks.
            task_map (list of tuple): (original_task_idx, day_index) for each tasks_info entry.
            min_nurses_anytime (int, optional): The minimal coverage at any time. Defaults to 1.
            max_time_in_seconds (float, optional): Gurobi time limit in seconds. Defaults to 1e10.
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
        """Build all constants, variables, objective, and constraints in the Gurobi model."""
        
        ### CONSTANTS ###

        # Binary constants indicating whether shift j covers time block t
        self.e = {}
        for j in self.S:
            coverage_array = self.shift_info[j - 1]["coverage"]
            for t in self.T:
                self.e[j, t] = coverage_array[t - 1] if (t - 1 < len(coverage_array)) else 0

        # Binary constants indicating whether shift j has a starting point at time block t
        self.h = {}
        for t in self.T:
            for j in self.S:
                self.h[j,t] = 1 if j-1 in self.starting_blocks[t-1] else 0

        # Build candidate blocks for tasks
        self.candidate_blocks = []
        max_T = max(self.T)
        for i in self.N:
            self.candidate_blocks.append([])
            c_idx = 0
            task = self.tasks_info[i - 1]
            eb = task['earliest_block']
            lb = task['latest_block']
            if lb >= eb:
                for j in range(eb,lb+1):
                    self.candidate_blocks[i-1].append([])
                    for k in range(0,task['duration_blocks']):
                        if k + j <= max_T - 1:
                            self.candidate_blocks[i-1][c_idx].append(j+k)
                        else: self.candidate_blocks[i-1][c_idx].append(j+k - max_T) 
                    c_idx += 1
            else:
                for j in range(eb,max_T-1+1):
                    self.candidate_blocks[i-1].append([])
                    for k in range(0,task['duration_blocks']):
                        if k + j <= max_T - 1:
                            self.candidate_blocks[i-1][c_idx].append(j+k)
                        else: self.candidate_blocks[i-1][c_idx].append(j+k - max_T)               
                    c_idx += 1
                for j in range(0,lb+1):
                    self.candidate_blocks[i-1].append([])
                    for k in range(0,task['duration_blocks']):
                       self. candidate_blocks[i-1][c_idx].append(j+k)
                    c_idx += 1
        print(self.candidate_blocks[4])

        # Binary constants indicating whether candidate task block b for task i covers time block t
        self.g = {}
        for i in self.N:
            c_size = len(self.candidate_blocks[i - 1])
            for b in range(c_size):
                covered_list = self.candidate_blocks[i - 1][b]
                for t in self.T:
                    self.g[i, b + 1, t] = 1 if t-1 in covered_list else 0

        # Adaptive "Big_M" for calculating whether nurse needs to *provide* handover
        self.max_starting_nurses = {}
        for t in self.T:
           self.max_starting_nurses[t] = sum(self.h[j,t] * self.shift_info[j-1]["max_nurses"] for j in self.S)
        self.Big_M = max(self.max_starting_nurses.values())

        ### DECISION VARIABLES ###

        # Decision variables indicating whether candidate time block b for task i is activated
        self.f = {}
        for i in self.N:
            c_size = len(self.candidate_blocks[i - 1])
            for b in range(1, c_size + 1):
                self.f[i, b] = self.model.addVar(
                    vtype=GRB.BINARY, name=f"f_{i}_{b}"
                )

        # Decision variables indicating whehther task i is active at time block t
        self.u = {}
        for i in self.N:
            for t in self.T:
                self.u[i, t] = self.model.addVar(
                    vtype=GRB.BINARY, name=f"u_{i}_{t}"
                )

        # Decision variables indicating how many times shift schedule j is scheduled
        self.k = {}
        for j in self.S:
            self.k[j] = self.model.addVar(
                vtype=GRB.INTEGER,
                lb=0,
                ub=self.shift_info[j - 1]["max_nurses"],
                name=f"k_{j}"
            )

        # Decision variables indicating required coverage (required number of nurses) at time t
        self.x = {}
        for t in self.T:
            self.x[t] = self.model.addVar(
                vtype=GRB.INTEGER, name=f"x_{t}"
            )

        # Decision variables indicating number of nurses present at time t
        self.n = {}
        for t in self.T:
            self.n[t] = self.model.addVar(
                vtype=GRB.INTEGER, name=f"n_{t}"
            )

        # Decision variables indicating number of nurses that need to *receive* a handover (briefing) at time t
        self.r = {}
        for t in self.T:
            self.r[t] = self.model.addVar(
                vtype=GRB.INTEGER, name=f"r_{t}"
            )

        # Decision variables indicating whether a nurse needs to *provide* a handover (briefing) at time t
        self.p = {}
        for t in self.T:
            self.p[t] = self.model.addVar(
                vtype=GRB.BINARY, name=f"p_{t}"
            )

        ### OBJECTIVE ###

        obj_expr = gp.quicksum(
            self.k[j]
            * self.shift_info[j - 1]["weight_scaled"] / 100.0
            * self.shift_info[j - 1]["length_blocks"]
            for j in self.S
        )
        self.model.setObjective(obj_expr, GRB.MINIMIZE)

        ###  CONSTRAINTS ###   
        
        # 1) Each task picks exactly one candidate time block
        for i in self.N:
            c_size = len(self.candidate_blocks[i - 1])
            self.model.addConstr(gp.quicksum(self.f[i, b] for b in range(1, c_size + 1)) == 1)

        # 2) Task i is active at time block t if the chosen time block for task i covers time block t
        for i in self.N:
            c_size = len(self.candidate_blocks[i - 1])
            for t in self.T:
                self.model.addConstr(self.u[i, t] >= gp.quicksum(self.f[i, b] * self.g[i, b, t] for b in range(1, c_size + 1)))

        # 3) Number of nurses *receiving* handover (briefing) at time block t equals number of scheduled nurses that have a shift start in their schedules at time block t
        for t in self.T:
            self.model.addConstr(self.r[t] == gp.quicksum(self.k[j] * self.h[j, t] for j in self.S)) 
        
        # 4) 1 nurse needs to *provide* handover (briefing) if there are 1 or more nurses that need to *receive* handover
        for t in self.T:
            self.model.addConstr(self.p[t] >= self.r[t]/self.Big_M) 

        # 5) Required nurse coverage at time block t is greater or equal than task demand at time block t + nurses that receive handover at time block t + nurse that provides handover at time block t
        for t in self.T:
            self.model.addConstr(self.x[t] >= gp.quicksum(self.u[i, t] * self.tasks_info[i - 1]["required_nurses"] for i in self.N) + self.r[t] + self.p[t])

        # 6) PSEUDO-TASK: Required nurse coverage is always greater or equal than the minimum nurses present at all time
        for t in self.T:
            self.model.addConstr(self.x[t] >= self.min_nurses_anytime)

        # 7) Nurses present at time t is equal to sum of present nurses at time t for all active nurse schedules
        for t in self.T:
            self.model.addConstr(self.n[t] == gp.quicksum(self.e[j, t] * self.k[j] for j in self.S))

        # 8) Nurses present at time block t needs to cover the required nurse coverage at time block t
        for t in self.T:
            self.model.addConstr(self.n[t] >= self.x[t])

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

        # Shift schedules usage solution
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
            for b in range(1, c_size + 1):
                if self.f[i, b].X > 0.5:
                    offset = (b - 1)
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

