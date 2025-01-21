import time
from collections import defaultdict

import pandas as pd
from ortools.sat.python import cp_model

WEEK_MINUTES = 7 * 24 * 60      # 10080 minutes in a week
TIME_GRAN = 15                  # 15-minute blocks
N_BLOCKS = WEEK_MINUTES // TIME_GRAN  # 672 blocks in a week

def minute_to_block(m: int) -> int:
    """Convert an absolute minute in the week to a 15-minute block index.

    Args:
        m (int): The absolute minute in the week (0 <= m < 10080).

    Returns:
        int: The block index (0 <= block < 672).
    """
    return m // TIME_GRAN

def block_to_minute(b: int) -> int:
    """Convert a 15-minute block index back to an absolute minute in the week.

    Args:
        b (int): The 15-minute block index (0 <= b < 672).

    Returns:
        int: The corresponding minute (0 <= minute < 10080).
    """
    return b * TIME_GRAN

def block_to_timestr(b: int) -> str:
    """Convert a block index into an 'HH:MM' string (mod 24 hours).

    Ignores which day of the week and returns just the time in 0-23:59 format.

    Args:
        b (int): Block index (0-based, 15-minute increments).

    Returns:
        str: The corresponding time string, e.g. '08:15'.
    """
    blocks_per_day = 1440 // TIME_GRAN  # 1440 minutes / 15
    minute_of_day = block_to_minute(b % blocks_per_day)
    hh = minute_of_day // 60
    mm = minute_of_day % 60
    return f"{hh:02d}:{mm:02d}"

def add_coverage_blocks(cover_array, start_min, end_min):
    """Mark cover_array[b] = 1 for blocks in [start_min, end_min).

    Wraps if needed from Sunday -> Monday.

    Args:
        cover_array (list of int): The weekly coverage array, length N_BLOCKS (672).
        start_min (int): Start minute of the coverage interval.
        end_min (int): End minute (exclusive) of the coverage interval.
    """
    if end_min <= WEEK_MINUTES:
        s_block = minute_to_block(start_min)
        e_block = max(s_block, minute_to_block(end_min - 1))
        for b in range(s_block, min(e_block + 1, N_BLOCKS)):
            cover_array[b] = 1
    else: 
        # crosses boundary from Sunday -> Monday
        s_block = minute_to_block(start_min)
        for b in range(s_block, N_BLOCKS):
            cover_array[b] = 1
        end2 = end_min - WEEK_MINUTES
        e_block2 = minute_to_block(end2 - 1)
        for b in range(0, min(e_block2 + 1, N_BLOCKS)):
            cover_array[b] = 1

def remove_coverage_blocks(cover_array, start_min, end_min): 
    """Mark cover_array[b] = 0 for blocks in [start_min, end_min).

    Wraps if needed from Sunday -> Monday.

    Args:
        cover_array (list of int): The weekly coverage array, length N_BLOCKS (672).
        start_min (int): Start minute of the coverage interval.
        end_min (int): End minute (exclusive) of the coverage interval.
    """
    if end_min <= WEEK_MINUTES:
        s_block = minute_to_block(start_min)
        e_block = max(s_block, minute_to_block(end_min - 1))
        for b in range(s_block, min(e_block + 1, N_BLOCKS)):
            cover_array[b] = 0
    else:
        # crosses boundary from Sunday -> Monday
        s_block = minute_to_block(start_min)
        for b in range(s_block, N_BLOCKS):
            cover_array[b] = 0
        end2 = end_min - WEEK_MINUTES
        e_block2 = minute_to_block(end2 - 1)
        for b in range(0, min(e_block2 + 1, N_BLOCKS)):
            cover_array[b] = 0


### NEW: A callback to capture intermediate solutions.
class IntermediateSolutionCallback(cp_model.CpSolverSolutionCallback):
    """A callback class that records (objective_cost, elapsed_time) whenever a
    new solution is found.

    Attributes:
        _start_time (float): Wall-clock time when the solve started.
        solutions (list of tuples): Each entry is (objective_value, time_found).
    """

    def __init__(self, start_time):
        """Initialize the callback with the start time of the search.

        Args:
            start_time (float): The time.time() timestamp when the solver started.
        """
        super().__init__()
        self._start_time = start_time
        self.solutions = []

    def OnSolutionCallback(self):
        """Called by the solver when a new solution is found or improved."""
        current_objective = self.ObjectiveValue()
        elapsed_time = time.time() - self._start_time
        # Record and print the intermediate solution details
        print(f"Intermediate solution found. Cost={current_objective}, Time={elapsed_time:.2f}s")
        self.solutions.append((current_objective, elapsed_time))


class OptimalNurseSchedulerCP:
    """Builds and solves a nurse scheduling + task-coverage problem, with
    handover and a global minimum coverage constraint.

    Attributes:
        shifts_df (pd.DataFrame): Original shifts data.
        tasks_df (pd.DataFrame): Original tasks data.
        min_nurses_anytime (int): Minimum required nurses that must be available
            (not handing over or just arrived) at every block, even if no tasks.
        max_solve_time (float): Maximum time (in seconds) to let the solver run.
        shift_info (list): Shift coverage + metadata.
        shift_usage_vars (list of IntVar): The integer variables representing
            the number of nurses assigned to each shift.
        tasks_info (list): Day-specific expansions of tasks.
        task_start_vars (list of IntVar): The starting block for each day-specific task.
        task_end_vars (list of IntVar): The ending block for each task.
        task_covers_bool (list of dict): For each task, a dict {block -> BoolVar}.
        task_map (list of tuple): Mapping back to original tasks (row_idx, day_idx).
        shift_start_blocks (dict): block -> list of shift indices that begin at that block.
        model (CpModel): The OR-Tools CP-SAT model.
    """

    def __init__(
        self,
        shifts_df: pd.DataFrame,
        tasks_df: pd.DataFrame,
        min_nurses_anytime: int = 0,    ### NEW
        max_solve_time: float = 60.0    ### NEW
    ):
        """Initialize and build the nurse scheduler model.

        Args:
            shifts_df (pd.DataFrame): Table of shifts with columns such as
                'name', 'start', 'end', 'break', 'break_duration', 'max_nurses',
                'weight', and boolean 1/0 columns for each weekday.
            tasks_df (pd.DataFrame): Table of tasks with columns such as
                'task', 'start', 'end', 'duration_min', 'nurses_required',
                and boolean 1/0 columns for each weekday.
            min_nurses_anytime (int, optional): A global minimum number of nurses
                that must always be available each time block. Defaults to 0.
            max_solve_time (float, optional): Maximum time in seconds to spend
                in the CP solver. Defaults to 60.0.
        """
        self.model = cp_model.CpModel()

        self.shifts_df = shifts_df.copy()
        self.tasks_df = tasks_df.copy()

        self.min_nurses_anytime = min_nurses_anytime   ### NEW
        self.max_solve_time = max_solve_time           ### NEW

        self.shift_info = []
        self.shift_usage_vars = []
        self.tasks_info = []
        self.task_start_vars = []
        self.task_end_vars = []
        self.task_covers_bool = []
        self.task_map = []

        self.shift_start_blocks = defaultdict(list)  # block -> [shift indices]

        # Prepare data, then build model
        self._prepare_shifts()
        self._prepare_tasks()
        self._build_model()

    def _prepare_shifts(self):
        """Convert shift definitions into coverage arrays and store shift metadata.

        Each shift has a coverage array for all 672 blocks. Also tracks the
        block(s) at which the shift starts for handover logic.
        """
        day_cols = ["monday", "tuesday", "wednesday",
                    "thursday", "friday", "saturday", "sunday"]

        for idx, row in self.shifts_df.iterrows():
            shift_name   = row["name"]
            max_nurses   = int(row["max_nurses"])
            start_str    = row["start"]
            end_str      = row["end"]
            brk_str      = row["break"]
            brk_dur      = int(row["break_duration"])
            raw_weight   = float(row["weight"])

            coverage_arr = [0] * N_BLOCKS
            day_flags = [int(row[d]) for d in day_cols]

            for day_index, active in enumerate(day_flags):
                if not active:
                    continue  # skip if shift isn't active on that day

                day_offset = day_index * 1440

                # parse start/end times
                s_h, s_m = map(int, start_str.split(':'))
                start_min = day_offset + s_h * 60 + s_m

                e_h, e_m = map(int, end_str.split(':'))
                if (e_h * 60 + e_m) < (s_h * 60 + s_m):
                    # crosses midnight
                    end_min = start_min + (24*60 - (s_h*60 + s_m)) + (e_h*60 + e_m)
                else:
                    end_min = day_offset + e_h * 60 + e_m

                # parse break
                bh, bm = map(int, brk_str.split(':'))
                break_start = day_offset + bh * 60 + bm
                if break_start < start_min:
                    break_start += 1440
                break_end = break_start + brk_dur
                # clamp break if it exceeds shift boundaries
                if break_start < start_min:
                    break_start = start_min
                if break_end > end_min:
                    break_end = end_min

                # build coverage
                add_coverage_blocks(coverage_arr, start_min, end_min)
                remove_coverage_blocks(coverage_arr, break_start, break_end)

                # record which block this shift starts at (for the handover logic)
                start_block = minute_to_block(start_min)
                self.shift_start_blocks[start_block].append(idx)

            # convert weight to integer scale
            weight_scaled = int(round(raw_weight * 100))
            length_blocks = sum(coverage_arr)

            self.shift_info.append({
                "name": shift_name,
                "coverage": coverage_arr,
                "weight_scaled": weight_scaled,
                "length_blocks": length_blocks,
                "max_nurses": max_nurses
            })

    def _prepare_tasks(self):
        """Expand each task definition to day-specific subtasks and store feasible blocks."""
        day_cols = ["monday", "tuesday", "wednesday",
                    "thursday", "friday", "saturday", "sunday"]

        for idx, row in self.tasks_df.iterrows():
            task_name  = row["task"]
            start_str  = row["start"]
            end_str    = row["end"]
            duration   = int(row["duration_min"])
            required   = int(row["nurses_required"])

            day_flags = [int(row[d]) for d in day_cols]

            for day_index, active in enumerate(day_flags):
                if not active:
                    continue  # skip if task isn't active this day

                day_offset = day_index * 1440

                s_h, s_m = map(int, start_str.split(':'))
                earliest_min = day_offset + s_h * 60 + s_m

                e_h, e_m = map(int, end_str.split(':'))
                latest_min = day_offset + e_h * 60 + e_m
                if latest_min < earliest_min:
                    # crosses midnight
                    latest_min += 24*60

                duration_blocks = duration // TIME_GRAN
                earliest_block  = earliest_min // TIME_GRAN
                latest_block    = latest_min // TIME_GRAN
                latest_block %= N_BLOCKS  # wrap if crossing Sunday->Monday

                self.tasks_info.append({
                    "task_name": task_name,
                    "earliest_block": earliest_block,
                    "latest_block": latest_block,
                    "duration_blocks": duration_blocks,
                    "required_nurses": required
                })

                # link the subtask back to the original tasks_df
                self.task_map.append((idx, day_index))

    def _build_model(self):
        """Construct the CP-SAT model with coverage, handover logic, and objective.

        The key constraints:
        - Each shift has an integer variable for usage (0..max_nurses).
        - Each task has a start block var and coverage booleans reified.
        - Coverage in each block must meet: 
            (sum of shift usage active in b) 
            - (newly started nurses in b)
            - (1 nurse if any started in b)
          >= max( sum_of_task_demands(b), min_nurses_anytime ).
        - Objective: minimize sum( usage_s * coverage_length_s * weight_s ).
        """
        # 1) SHIFT usage variables
        for s_idx, sh in enumerate(self.shift_info):
            max_usage = sh["max_nurses"]
            usage_var = self.model.NewIntVar(0, max_usage, f"shift_{s_idx}_usage")
            self.shift_usage_vars.append(usage_var)

        # 2) TASK variables: start, end, coverage booleans
        for i, t in enumerate(self.tasks_info):
            e_b = t["earliest_block"]
            l_b = t["latest_block"]
            d_b = t["duration_blocks"]

            start_var = self.model.NewIntVar(e_b, l_b, f"task_{i}_start")
            end_var   = self.model.NewIntVar(e_b + d_b, l_b + d_b, f"task_{i}_end")
            # link end_var == start_var + d_b
            self.model.Add(end_var == start_var + d_b)

            self.task_start_vars.append(start_var)
            self.task_end_vars.append(end_var)

            covers_b = {}
            for b in range(e_b, l_b + d_b):
                if 0 <= b < N_BLOCKS:
                    boolvar = self.model.NewBoolVar(f"task_{i}_covers_{b}")
                    covers_b[b] = boolvar
            self.task_covers_bool.append(covers_b)

        # 2a) Reify coverage booleans:
        #     covers[i][b] <=> (start_var[i] <= b < start_var[i] + duration)
        for i, t in enumerate(self.tasks_info):
            d_b = t["duration_blocks"]
            startv = self.task_start_vars[i]
            for b, boolvar in self.task_covers_bool[i].items():
                aux1 = self.model.NewBoolVar(f"aux1_{i}_{b}")  # startv <= b
                aux2 = self.model.NewBoolVar(f"aux2_{i}_{b}")  # b < startv + d_b

                self.model.Add(startv <= b).OnlyEnforceIf(aux1)
                self.model.Add(startv > b).OnlyEnforceIf(aux1.Not())

                self.model.Add(b < startv + d_b).OnlyEnforceIf(aux2)
                self.model.Add(b >= startv + d_b).OnlyEnforceIf(aux2.Not())

                self.model.AddBoolAnd([aux1, aux2]).OnlyEnforceIf(boolvar)
                self.model.AddBoolOr([aux1.Not(), aux2.Not()]).OnlyEnforceIf(boolvar.Not())

        # 3) HANDOVER LOGIC:
        #    starts_at[b] = sum( shift_usage[s] for s in shift_start_blocks[b] )
        #    handover[b]  = 1 if starts_at[b] >= 1 else 0
        max_possible_usage_per_block = [0]*N_BLOCKS
        for b in range(N_BLOCKS):
            if b in self.shift_start_blocks:
                max_possible_usage_per_block[b] = sum(
                    self.shift_info[s]["max_nurses"] for s in self.shift_start_blocks[b]
                )

        # build the starts_at[b] expressions
        starts_at = [None]*N_BLOCKS
        for b in range(N_BLOCKS):
            if b in self.shift_start_blocks:
                starts_at[b] = cp_model.LinearExpr.Sum(
                    [self.shift_usage_vars[s] for s in self.shift_start_blocks[b]]
                )
            else:
                starts_at[b] = 0

        # create the binary handover variable for each block
        h = []
        for b in range(N_BLOCKS):
            hb = self.model.NewBoolVar(f"handover_{b}")
            h.append(hb)
            M = max_possible_usage_per_block[b]
            if M > 0:
                # if sum usage >= 1 => h[b] = 1
                self.model.Add(starts_at[b] <= M * hb)
                self.model.Add(starts_at[b] >= hb)
            else:
                # no shift can start at b => h[b] = 0
                self.model.Add(hb == 0)

        # 4) COVERAGE CONSTRAINTS:
        #    effective_coverage = sum_of_active_usage - starts_at[b] - h[b]
        #    must be >= sum_of_tasks(b), AND >= min_nurses_anytime.
        for b in range(N_BLOCKS):
            coverage_terms = []
            for s_idx, sh in enumerate(self.shift_info):
                if sh["coverage"][b] > 0:
                    coverage_terms.append(self.shift_usage_vars[s_idx])

            # tasks demand in block b
            task_demands = []
            for i, t in enumerate(self.tasks_info):
                if b in self.task_covers_bool[i]:
                    req = t["required_nurses"]
                    boolvar = self.task_covers_bool[i][b]
                    task_demands.append(req * boolvar)

            # Build the effective coverage expression
            effective_coverage = (
                cp_model.LinearExpr.Sum(coverage_terms)
                - starts_at[b]   # newly started nurses are busy
                - h[b]           # exactly 1 nurse must handle handover if any start
            )

            # tasks sum
            demands_expr = cp_model.LinearExpr.Sum(task_demands)

            # coverage >= tasks demand
            self.model.Add(effective_coverage >= demands_expr)
            # coverage >= global min nurses, if any
            if self.min_nurses_anytime > 0:
                self.model.Add(effective_coverage >= self.min_nurses_anytime)

        # 5) OBJECTIVE: Minimize total cost
        #    cost = sum( usage_s * (shift length in blocks) * scaled_weight_s )
        cost_terms = []
        for s_idx, sh in enumerate(self.shift_info):
            usage_var = self.shift_usage_vars[s_idx]
            blocks_count = sh["length_blocks"]
            w_scaled = sh["weight_scaled"]
            cost_terms.append(usage_var * blocks_count * w_scaled)

        self.model.Minimize(cp_model.LinearExpr.Sum(cost_terms))

    def solve(self):
        """Solve the model within the specified time limit.

        Returns:
            tuple:
                total_cost (float):
                    The final objective cost after scaling down by 100.
                tasks_solution_df (pd.DataFrame):
                    A row per day-specific subtask, indicating the chosen start time, etc.
                shifts_solution_df (pd.DataFrame):
                    The original shifts_df plus a 'usage' column with solution usage.
                intermediate_solutions (list of (float, float)):
                    A list of tuples (objective_cost, time_elapsed_seconds) for each
                    intermediate solution found during the search.
        """
        solver = cp_model.CpSolver()

        # Set parallel workers (optional) and maximum solve time
        solver.parameters.num_search_workers = 8
        solver.parameters.max_time_in_seconds = self.max_solve_time  ### NEW

        # Create an intermediate solution callback
        start_time = time.time()
        solution_callback = IntermediateSolutionCallback(start_time)

        # Solve with callback to capture intermediate solutions
        status = solver.SolveWithSolutionCallback(self.model, solution_callback)

        # If no feasible solution was found
        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print("No solution found.")
            return (None, None, None, [])

        # Final cost (scaled) and de-scale it
        total_cost_scaled = solver.ObjectiveValue()
        total_cost = total_cost_scaled / 100.0

        # SHIFT usage solution
        usage_values = []
        for s_idx, var in enumerate(self.shift_usage_vars):
            usage_values.append(solver.Value(var))
        self.shifts_df["usage"] = usage_values

        # TASKS solution data
        day_specific_records = []
        for i, tinfo in enumerate(self.tasks_info):
            start_block = solver.Value(self.task_start_vars[i])
            earliest_block = tinfo["earliest_block"]
            latest_block   = tinfo["latest_block"]
            duration_blocks = tinfo["duration_blocks"]

            earliest_str = block_to_timestr(earliest_block)
            latest_str   = block_to_timestr(latest_block)
            duration_min = block_to_minute(duration_blocks)
            solution_start_str = block_to_timestr(start_block)

            orig_task_idx, day_index = self.task_map[i]

            day_specific_records.append({
                "original_task_idx": orig_task_idx,
                "day_index": day_index,
                "task_name": tinfo["task_name"],
                "start_window": earliest_str,
                "end_window": latest_str,
                "solution_start": solution_start_str,
                "duration_minutes": duration_min,
                "required_nurses": tinfo["required_nurses"]
            })

        tasks_solution_df = pd.DataFrame(day_specific_records)

        # intermediate solutions are stored in solution_callback.solutions
        intermediate_solutions = [
            (obj_val, t) for (obj_val, t) in solution_callback.solutions
        ]

        # Print final solution details
        print(f"\nFinal solution status: {solver.StatusName(status)}")
        print(f"Final objective cost = {total_cost:.2f}")
        print(f"Number of intermediate solutions found: {len(intermediate_solutions)}")

        return (total_cost, tasks_solution_df, self.shifts_df, intermediate_solutions)
