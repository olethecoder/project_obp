from ortools.sat.python import cp_model
import pandas as pd

# ----------------------------------------------------------------------
# Global constants
# ----------------------------------------------------------------------
WEEK_MINUTES = 7 * 24 * 60      # 10080 minutes in a week
TIME_GRAN = 15                  # 15-minute blocks
N_BLOCKS = WEEK_MINUTES // TIME_GRAN  # 672 blocks in a week

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def minute_to_block(m: int) -> int:
    """
    Convert an absolute minute in the week to a 15-minute block index.
    """
    return m // TIME_GRAN

def block_to_minute(b: int) -> int:
    """
    Convert a 15-minute block index back to an absolute minute in the week.
    """
    return b * TIME_GRAN

def block_to_timestr(b: int) -> str:
    """
    Convert a block index into an HH:MM string (mod 24 hours). 
    This ignores the day of the week and just returns the 
    time in 0-23:59 format.
    """
    blocks_per_day = 1440 // TIME_GRAN
    minute_of_day = block_to_minute(b % blocks_per_day)
    hh = minute_of_day // 60
    mm = minute_of_day % 60
    return f"{hh:02d}:{mm:02d}"

def add_coverage_blocks(cover_array, start_min, end_min):
    """
    Mark coverage_arr[b] = 1 for blocks in [start_min, end_min),
    wrapping if needed from Sunday -> Monday.
    """
    if end_min <= WEEK_MINUTES:
        s_block = minute_to_block(start_min)
        e_block = max(s_block, minute_to_block(end_min - 1))
        for b in range(s_block, min(e_block + 1, N_BLOCKS)):
            cover_array[b] = 1
    else:
        # crosses boundary from Sunday into Monday
        s_block = minute_to_block(start_min)
        for b in range(s_block, N_BLOCKS):
            cover_array[b] = 1
        end2 = end_min - WEEK_MINUTES
        e_block2 = minute_to_block(end2 - 1)
        for b in range(0, min(e_block2 + 1, N_BLOCKS)):
            cover_array[b] = 1

def remove_coverage_blocks(cover_array, start_min, end_min):
    """
    Mark coverage_arr[b] = 0 for blocks in [start_min, end_min),
    wrapping if needed.
    """
    if end_min <= WEEK_MINUTES:
        s_block = minute_to_block(start_min)
        e_block = max(s_block, minute_to_block(end_min - 1))
        for b in range(s_block, min(e_block + 1, N_BLOCKS)):
            cover_array[b] = 0
    else:
        s_block = minute_to_block(start_min)
        for b in range(s_block, N_BLOCKS):
            cover_array[b] = 0
        end2 = end_min - WEEK_MINUTES
        e_block2 = minute_to_block(end2 - 1)
        for b in range(0, min(e_block2 + 1, N_BLOCKS)):
            cover_array[b] = 0


class OptimalNurseSchedulerCP:
    """
    This class builds and solves a shift-allocation + task-scheduling problem
    using Google's OR-Tools CP-SAT solver.

    The solution can return:
      1) The total cost (float).
      2) An augmented tasks DataFrame, containing each day-specific subtask,
         along with its assigned start time in HH:MM format.
      3) The original shifts DataFrame with an added 'usage' column
         indicating how many nurses are assigned to each shift.
    """

    def __init__(self, shifts_df: pd.DataFrame, tasks_df: pd.DataFrame):
        self.model = cp_model.CpModel()

        # Make local copies so original data is not mutated
        self.shifts_df = shifts_df.copy()
        self.tasks_df = tasks_df.copy()

        # Data structures for SHIFT
        self.shift_info = []           # List of dicts: coverage arrays, shift name, weight, etc.
        self.shift_usage_vars = []     # Each shift gets one integer variable for usage

        # Data structures for TASK
        self.tasks_info = []           # Each row is one "day-specific" task
        self.task_start_vars = []      # Start block var
        self.task_end_vars = []        # End block var
        self.task_intervals = []       # Interval var
        self.task_covers_bool = []     # List of dicts {block_index: boolvar} indicating coverage in each block

        # We'll store (original_task_idx, day_index) for each day-specific task
        # so we can reconstruct solutions in a DataFrame
        self.task_map = []

        # Build data, then model
        self._prepare_shifts()
        self._prepare_tasks()
        self._build_model()

    # ----------------------------------------------------------------------
    # Prepare SHIFT data
    # ----------------------------------------------------------------------
    def _prepare_shifts(self):
        """
        For each row in shifts_df, build a coverage array for the entire week.
        We also store the 'max_nurses' directly from the DataFrame.
        """
        day_cols = [
            "monday", "tuesday", "wednesday", 
            "thursday", "friday", "saturday", "sunday"
        ]

        for idx, row in self.shifts_df.iterrows():
            shift_name   = row["name"] 
            max_nurses   = int(row["max_nurses"])  # Use the shift-specific max
            start_str    = row["start"]
            end_str      = row["end"]
            brk_str      = row["break"]
            brk_dur      = int(row["break_duration"])
            raw_weight   = float(row["weight"])

            coverage_arr = [0] * N_BLOCKS
            day_flags = [int(row[d]) for d in day_cols]

            for day_index, active in enumerate(day_flags):
                if not active:
                    continue  # if the shift isn't active on that day, skip

                day_offset = day_index * 1440

                # Parse start time
                s_h, s_m = map(int, start_str.split(':'))
                start_min = day_offset + s_h * 60 + s_m

                # Parse end time
                e_h, e_m = map(int, end_str.split(':'))
                if (e_h * 60 + e_m) < (s_h * 60 + s_m):
                    # crosses midnight
                    end_min = start_min + (24*60 - (s_h*60 + s_m)) + (e_h*60 + e_m)
                else:
                    end_min = day_offset + e_h * 60 + e_m

                # Parse break time
                bh, bm = map(int, brk_str.split(':'))
                break_start = day_offset + bh*60 + bm
                # if break_start is before shift start, roll over to next day
                if break_start < start_min:
                    break_start += 1440
                break_end = break_start + brk_dur
                # clamp break if it exceeds shift bounds
                if break_start < start_min:
                    break_start = start_min
                if break_end > end_min:
                    break_end = end_min

                # Mark coverage
                add_coverage_blocks(coverage_arr, start_min, end_min)
                remove_coverage_blocks(coverage_arr, break_start, break_end)

            # Convert weight to an integer scale
            weight_scaled = int(round(raw_weight * 100))
            length_blocks = sum(coverage_arr)

            self.shift_info.append({
                "name": shift_name,
                "coverage": coverage_arr,
                "weight_scaled": weight_scaled,
                "length_blocks": length_blocks,
                "max_nurses": max_nurses
            })

    # ----------------------------------------------------------------------
    # Prepare TASK data
    # ----------------------------------------------------------------------
    def _prepare_tasks(self):
        """
        For each day the task is active, we create one entry in tasks_info
        with earliest_block, latest_block, etc. Also record (row_idx, day_index)
        for reconstructing the final solution.
        """
        day_cols = [
            "monday", "tuesday", "wednesday", 
            "thursday", "friday", "saturday", "sunday"
        ]

        for idx, row in self.tasks_df.iterrows():
            task_name  = row["task"]
            start_str  = row["start"]
            end_str    = row["end"]
            duration   = int(row["duration_min"])
            required   = int(row["nurses_required"])

            day_flags = [int(row[d]) for d in day_cols]

            for day_index, active in enumerate(day_flags):
                if not active:
                    continue  # skip if task is not active on that day

                day_offset = day_index * 1440

                # Parse earliest time
                s_h, s_m = map(int, start_str.split(':'))
                earliest_min = day_offset + s_h * 60 + s_m

                # Parse latest time
                e_h, e_m = map(int, end_str.split(':'))
                latest_min = day_offset + e_h * 60 + e_m

                # If end < start, assume it crosses midnight => + WEEK_MINUTES
                if latest_min < earliest_min:
                    latest_min += WEEK_MINUTES

                duration_blocks = duration // TIME_GRAN
                earliest_block  = earliest_min // TIME_GRAN
                latest_block    = latest_min // TIME_GRAN

                self.tasks_info.append({
                    "task_name": task_name,
                    "earliest_block": earliest_block,
                    "latest_block": latest_block,
                    "duration_blocks": duration_blocks,
                    "required_nurses": required
                })

                # Link this subtask back to the original tasks_df row
                self.task_map.append((idx, day_index))

    # ----------------------------------------------------------------------
    # Build the model
    # ----------------------------------------------------------------------
    def _build_model(self):
        """
        Build the CP-SAT model:
          - Create usage variables for each shift, bounded by each shift's 'max_nurses'.
          - Create interval and coverage boolean variables for each task.
          - Impose coverage constraints.
          - Define objective to minimize total cost.
        """

        # Create SHIFT usage variables, each bounded by shift_info["max_nurses"]
        for s_idx, sh in enumerate(self.shift_info):
            max_usage = sh["max_nurses"]
            var = self.model.NewIntVar(0, max_usage, f"shift_{s_idx}_usage")
            self.shift_usage_vars.append(var)

        # Create TASK variables: start, end, interval, coverage booleans
        for i, t in enumerate(self.tasks_info):
            e_b = t["earliest_block"]
            l_b = t["latest_block"]
            d_b = t["duration_blocks"]

            # Start var
            start_var = self.model.NewIntVar(e_b, l_b, f"task_{i}_start")
            self.task_start_vars.append(start_var)

            # End var
            end_var = self.model.NewIntVar(e_b + d_b, l_b + d_b, f"task_{i}_end")
            self.task_end_vars.append(end_var)

            # Link start and end: end_var == start_var + duration
            self.model.Add(end_var == start_var + d_b)

            # Interval var
            interval_var = self.model.NewIntervalVar(start_var, d_b, end_var, f"task_{i}_interval")
            self.task_intervals.append(interval_var)

            # Build coverage booleans
            covers_b = {}
            for b in range(e_b, l_b + d_b):
                if 0 <= b < N_BLOCKS:
                    boolvar = self.model.NewBoolVar(f"task_{i}_covers_{b}")
                    covers_b[b] = boolvar
            self.task_covers_bool.append(covers_b)

        # Reification: covers_b[b] <=> start_var <= b < (start_var + d_b)
        for i, t in enumerate(self.tasks_info):
            d_b = t["duration_blocks"]
            startv = self.task_start_vars[i]
            covers_dict = self.task_covers_bool[i]
            for b, boolvar in covers_dict.items():
                aux1 = self.model.NewBoolVar(f"aux1_{i}_{b}")
                aux2 = self.model.NewBoolVar(f"aux2_{i}_{b}")

                # aux1 => (startv <= b)
                self.model.Add(startv <= b).OnlyEnforceIf(aux1)
                self.model.Add(startv > b).OnlyEnforceIf(aux1.Not())

                # aux2 => (b < startv + d_b)
                self.model.Add(b < startv + d_b).OnlyEnforceIf(aux2)
                self.model.Add(b >= startv + d_b).OnlyEnforceIf(aux2.Not())

                # boolvar = aux1 AND aux2
                self.model.AddBoolAnd([aux1, aux2]).OnlyEnforceIf(boolvar)
                self.model.AddBoolOr([aux1.Not(), aux2.Not()]).OnlyEnforceIf(boolvar.Not())

        # Coverage constraints: sum(shift_usage * coverage) >= sum(task demands) per block
        for b in range(N_BLOCKS):
            lhs_terms = []
            for s_idx, sh in enumerate(self.shift_info):
                if sh["coverage"][b] > 0:
                    lhs_terms.append(self.shift_usage_vars[s_idx] * sh["coverage"][b])

            rhs_terms = []
            for i, t in enumerate(self.tasks_info):
                if b in self.task_covers_bool[i]:
                    req = t["required_nurses"]
                    boolvar = self.task_covers_bool[i][b]
                    rhs_terms.append(req * boolvar)

            if lhs_terms or rhs_terms:
                self.model.Add(sum(lhs_terms) >= sum(rhs_terms))

        # Objective: minimize sum(shift usage * length_blocks * weight_scaled)
        cost_terms = []
        for s_idx, sh in enumerate(self.shift_info):
            usage_var = self.shift_usage_vars[s_idx]
            blocks_count = sh["length_blocks"]
            w_scaled = sh["weight_scaled"]
            cost_terms.append(usage_var * blocks_count * w_scaled)

        self.model.Minimize(sum(cost_terms))

    # ----------------------------------------------------------------------
    # Solve
    # ----------------------------------------------------------------------
    def solve(self):
        """
        Solve the model. Return a tuple:
            (total_cost, tasks_solution_df, shifts_solution_df).

        - total_cost (float): the final cost of the solution.
        - tasks_solution_df (DataFrame): one row per day-specific subtask,
          with columns including 'solution_start' in HH:MM format.
        - shifts_solution_df (DataFrame): the original shifts_df plus a 'usage' column.
        """
        solver = cp_model.CpSolver()
        # Optional solver parameters
        solver.parameters.num_search_workers = 8
        solver.parameters.max_time_in_seconds = 20

        status = solver.Solve(self.model)
        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print("No solution found.")
            return (None, None, None)

        # ---------------------------
        # Extract solution
        # ---------------------------
        total_cost_scaled = solver.ObjectiveValue()
        total_cost = total_cost_scaled / 100.0

        # 1) SHIFT usage solutions
        usage_values = []
        for s_idx, var in enumerate(self.shift_usage_vars):
            val = solver.Value(var)
            usage_values.append(val)
        # Add usage column to shifts_df
        self.shifts_df["usage"] = usage_values

        # 2) TASKS solution DataFrame (day-specific tasks)
        day_specific_records = []
        for i, tinfo in enumerate(self.tasks_info):
            start_block = solver.Value(self.task_start_vars[i])
            end_block   = solver.Value(self.task_end_vars[i])
            solution_start_str = block_to_timestr(start_block)

            orig_task_idx, day_index = self.task_map[i]
            day_specific_records.append({
                "original_task_idx": orig_task_idx,
                "day_index": day_index,
                "task_name": tinfo["task_name"],
                "solution_start_block": start_block,
                "solution_end_block": end_block,
                "solution_start": solution_start_str,
                "required_nurses": tinfo["required_nurses"]
            })

        tasks_solution_df = pd.DataFrame(day_specific_records)

        # Print some info
        # print("Solution found!")
        # print("Total cost:", total_cost)
        # for s_idx, sh in enumerate(self.shift_info):
        #     print(f"Shift {s_idx} ({sh['name']}) usage: {usage_values[s_idx]}")

        return (total_cost, tasks_solution_df, self.shifts_df)

