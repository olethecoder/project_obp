from ortools.sat.python import cp_model

# Global constants
WEEK_MINUTES = 7 * 24 * 60      # 10080 minutes in a week
TIME_GRAN = 15                  # 15-minute blocks
N_BLOCKS = WEEK_MINUTES // TIME_GRAN  # 672 blocks in a week

def minute_to_block(m):
    """Convert absolute minutes in the week to a 15-min block index."""
    return m // TIME_GRAN

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
    def __init__(self, shifts_df, tasks_df):
        self.model = cp_model.CpModel()
        self.shifts_df = shifts_df
        self.tasks_df = tasks_df

        # Data structures for shifts
        self.shift_info = []           # coverage arrays, weights, etc.
        self.shift_usage_vars = []     # integer usage variables for each shift

        # Data structures for tasks
        self.tasks_info = []           # earliest_block, latest_block, duration_blocks, required_nurses
        self.task_start_vars = []      # start block var
        self.task_end_vars = []        # end block var
        self.task_intervals = []       # interval vars
        # Instead of a 2D list for coverage, we use a list of dicts
        # coverage_booleans[i][b] => bool var for "task i covers block b"
        self.task_covers_bool = []

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
        The columns are:
          [name, max_nurses, start, end, break, break_duration, weight,  
           monday, tuesday, wednesday, thursday, friday, saturday, sunday]
        We ignore max_nurses, because we set a global max in the model.
        """
        day_cols = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for idx, row in self.shifts_df.iterrows():
            shift_name   = row["name"] 
            start_str    = row["start"]
            end_str      = row["end"]
            brk_str      = row["break"]
            brk_dur      = int(row["break_duration"])
            raw_weight   = float(row["weight"])

            coverage_arr = [0] * N_BLOCKS

            day_flags = [int(row[d]) for d in day_cols]
            for day_index, active in enumerate(day_flags):
                if not active:
                    continue

                day_offset = day_index * 1440
                # Parse start
                s_h, s_m = map(int, start_str.split(':'))
                start_min = day_offset + s_h * 60 + s_m

                # Parse end
                e_h, e_m = map(int, end_str.split(':'))
                if (e_h * 60 + e_m) < (s_h * 60 + s_m):
                    # crosses midnight
                    end_min = start_min + (24*60 - (s_h*60 + s_m)) + (e_h*60 + e_m)
                else:
                    end_min = day_offset + e_h * 60 + e_m

                # Parse break
                bh, bm = map(int, brk_str.split(':'))
                break_start = day_offset + bh*60 + bm
                if break_start < start_min:
                    break_start += 1440
                break_end = break_start + brk_dur
                # clamp break if needed
                if break_start < start_min:
                    break_start = start_min
                if break_end > end_min:
                    break_end = end_min

                # Mark coverage
                add_coverage_blocks(coverage_arr, start_min, end_min)
                remove_coverage_blocks(coverage_arr, break_start, break_end)

            weight_scaled = int(round(raw_weight * 100))
            length_blocks = sum(coverage_arr)

            self.shift_info.append({
                "name": shift_name,
                "coverage": coverage_arr,
                "weight_scaled": weight_scaled,
                "length_blocks": length_blocks,
            })

    # ----------------------------------------------------------------------
    # Prepare TASK data
    # ----------------------------------------------------------------------
    def _prepare_tasks(self):
        """
        Read tasks_df, assumed columns something like:
          [task, start, end, duration_min,
           monday, tuesday, wednesday, thursday, friday, saturday, sunday,
           nurses_required]
        For each day that is active, we create an entry in self.tasks_info.
        """
        day_cols = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        for idx, row in self.tasks_df.iterrows():
            task_name  = row["task"]
            start_str  = row["start"]
            end_str    = row["end"]
            duration   = int(row["duration_min"])
            required   = int(row["nurses_required"])

            day_flags = [int(row[d]) for d in day_cols]

            for day_index, active in enumerate(day_flags):
                if not active:
                    continue

                day_offset = day_index * 1440
                s_h, s_m = map(int, start_str.split(':'))
                e_h, e_m = map(int, end_str.split(':'))

                earliest_min = day_offset + s_h*60 + s_m
                latest_min   = day_offset + e_h*60 + e_m
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

    # ----------------------------------------------------------------------
    # Build the model
    # ----------------------------------------------------------------------
    def _build_model(self):
        max_shift_usage = 30
        for s_idx, sh in enumerate(self.shift_info):
            var = self.model.NewIntVar(0, max_shift_usage, f"shift_{s_idx}_usage")
            self.shift_usage_vars.append(var)

        # TASK variables: create start, end, interval
        for i, t in enumerate(self.tasks_info):
            e_b = t["earliest_block"]
            l_b = t["latest_block"]
            d_b = t["duration_blocks"]

            # Start var: can start anywhere in [earliest_block, latest_block]
            start_var = self.model.NewIntVar(e_b, l_b, f"task_{i}_start")
            self.task_start_vars.append(start_var)

            # End var: [ earliest + d_b, latest + d_b ], but we'll tie it to start_var
            end_var = self.model.NewIntVar(e_b + d_b, l_b + d_b, f"task_{i}_end")
            self.task_end_vars.append(end_var)

            # Add the equality: end_var == start_var + duration_blocks
            self.model.Add(end_var == start_var + d_b)

            # (3) Interval var for each task
            interval_var = self.model.NewIntervalVar(start_var, d_b, end_var, f"task_{i}_interval")
            self.task_intervals.append(interval_var)

            # (4) Coverage booleans restricted to [e_b, l_b + d_b)
            covers_b = {}
            for b in range(e_b, l_b + d_b):
                if 0 <= b < N_BLOCKS:
                    boolvar = self.model.NewBoolVar(f"task_{i}_covers_{b}")
                    covers_b[b] = boolvar
            self.task_covers_bool.append(covers_b)

        # Reification constraints with aux1/aux2 for coverage:
        #   boolvar = 1 iff (startv <= b < startv + d_b)
        # We only create constraints for b in [e_b, l_b + d_b).
        for i, t in enumerate(self.tasks_info):
            d_b = t["duration_blocks"]
            startv = self.task_start_vars[i]
            covers_dict = self.task_covers_bool[i]  # dict of {b: boolvar}
            for b, boolvar in covers_dict.items():
                # We'll create two new booleans for the reification:
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
        Solve the model and report results.
        """
        solver = cp_model.CpSolver()
        # optional multi-thread or time-limit
        solver.parameters.num_search_workers = 8
        # solver.parameters.max_time_in_seconds = 10

        status = solver.Solve(self.model)
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print("Solution found!")
            for s_idx, var in enumerate(self.shift_usage_vars):
                val = solver.Value(var)
                print(f"Shift {s_idx} ({self.shift_info[s_idx]['name']}) usage: {val}")
            print("Total cost:", solver.ObjectiveValue() / 100.0)
        else:
            print("No solution found.")
