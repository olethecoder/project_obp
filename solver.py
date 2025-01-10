from ortools.sat.python import cp_model

def hhmm_to_minutes(hhmm: str) -> int:
    """
    Convert 'HH:MM' to total minutes from 00:00.
    Special handling for '0:00' => 24*60 (midnight at end of day).
    """
    hh, mm = hhmm.split(':')
    hh = int(hh)
    mm = int(mm)
    if hh == 0 and mm == 0:
        return 24 * 60
    return hh * 60 + mm

class NurseSchedulingSolver:
    """
    A class to build and solve the CP-SAT model for nurse-shift-task scheduling.
    """

    def __init__(
        self,
        shifts_df,
        tasks_df,
        time_granularity=15,
        max_nurses_per_shift=30
    ):
        """
        Args:
            shifts_df (pd.DataFrame):
                DataFrame with columns:
                  ['Start','End','Break','Break Duration','Weight','Mo','Tue','Wed','Thu','Fri','Sat','Sun']
            tasks_df (pd.DataFrame):
                DataFrame with columns:
                  ['tasks','start','end','duration_min','ma','di','wo','do','vri','za','zo','# Nurses']
            time_granularity (int):
                The size of each time block in minutes (default 15).
            max_nurses_per_shift (int):
                An upper bound on how many nurses can be assigned to one shift pattern in one day.
        """
        self.shifts_df  = shifts_df
        self.tasks_df   = tasks_df
        self.time_gran  = time_granularity
        self.max_nurses = max_nurses_per_shift

        # Internal: will be populated when building the model
        self.model            = None
        self.shift_usage_vars = {}  # (day, shift_id) -> IntVar
        self.shifts           = []  # list of shift dict
        self.tasks            = []  # list of task dict

        # The solver and status
        self.solver = None
        self.status = None

        # Prepare data structures and build the model right away
        self._build_model()

    def _build_model(self):
        """
        Build the CP-SAT model with coverage constraints and cost minimization.
        """
        model = cp_model.CpModel()

        # ----------------------------------------------------------------
        # 1) Preprocess SHIFT data
        # ----------------------------------------------------------------
        # SHIFT DF columns: ['Start','End','Break','Break Duration','Weight','Mo','Tue','Wed','Thu','Fri','Sat','Sun']

        for idx, row in self.shifts_df.iterrows():
            shift_start = hhmm_to_minutes(row['Start'])
            shift_end   = hhmm_to_minutes(row['End'])
            break_start = hhmm_to_minutes(row['Break'])
            break_dur   = int(row['Break Duration'])
            break_end   = break_start + break_dur
            weight      = float(row['Weight'])

            days_active = [
                int(row['Mo']),
                int(row['Tue']),
                int(row['Wed']),
                int(row['Thu']),
                int(row['Fri']),
                int(row['Sat']),
                int(row['Sun']),
            ]

            self.shifts.append({
                'start': shift_start,
                'end'  : shift_end,
                'break_start': break_start,
                'break_end'  : break_end,
                'weight': weight,
                'days'  : days_active
            })

        # ----------------------------------------------------------------
        # 2) Preprocess TASK data
        # ----------------------------------------------------------------
        # TASK DF columns: ['tasks','start','end','duration_min','ma','di','wo','do','vri','za','zo','# Nurses']

        for idx, row in self.tasks_df.iterrows():
            earliest = hhmm_to_minutes(row['start'])
            latest   = hhmm_to_minutes(row['end'])
            duration = int(row['duration_min'])
            required = int(row['# Nurses'])

            days_active = [
                int(row['ma']),
                int(row['di']),
                int(row['wo']),
                int(row['do']),
                int(row['vri']),
                int(row['za']),
                int(row['zo']),
            ]

            self.tasks.append({
                'name'           : row['tasks'],
                'earliest_start' : earliest,
                'latest_start'   : latest,
                'duration'       : duration,
                'required_nurses': required,
                'days'           : days_active
            })

        # ----------------------------------------------------------------
        # 3) Create shift usage decision variables
        # ----------------------------------------------------------------
        # shift_usage[d, s_idx] = # nurses using shift s_idx on day d

        for d in range(7):
            for s_idx, s in enumerate(self.shifts):
                if s['days'][d] == 1:
                    var = model.NewIntVar(
                        0,
                        self.max_nurses,
                        f'shift_{s_idx}_day_{d}'
                    )
                else:
                    # If shift is not active that day => usage must be 0
                    var = model.NewIntVar(0, 0, f'shift_{s_idx}_day_{d}')

                self.shift_usage_vars[(d, s_idx)] = var

        # ----------------------------------------------------------------
        # 4) Coverage constraints
        # ----------------------------------------------------------------
        # We'll discretize each day into 15-min blocks. For each block,
        # figure out how many nurses might be needed. Then ensure
        # sum(shift_usage) across all shifts >= coverage_needed.

        # total blocks in one day
        minutes_in_day = 24 * 60
        n_blocks       = minutes_in_day // self.time_gran

        # coverage_needed[(d,b)] = integer number of nurses needed in day d, block b
        coverage_needed = {(d, b): 0 for d in range(7) for b in range(n_blocks)}

        # 4a) Sum up (worst-case) coverage for tasks on each day d
        for d in range(7):
            day_tasks = [t for t in self.tasks if t['days'][d] == 1]
            for t in day_tasks:
                # The earliest the task can start is t['earliest_start']
                # The latest it can start is (t['latest_start'] - t['duration'])
                feasible_start_min = t['earliest_start']
                feasible_end_min   = max(
                    feasible_start_min,
                    t['latest_start'] - t['duration']
                )

                # For simplicity, we assume tasks might run at any point
                # in [feasible_start_min, t['latest_start']].
                # We add the required nurses to coverage_needed for all
                # 15-min blocks that *could* be overlapped.

                for minute in range(feasible_start_min, t['latest_start']):
                    block = minute // self.time_gran
                    if block < n_blocks:
                        coverage_needed[(d, block)] += t['required_nurses']

        # 4b) Precompute coverage_of_shift[s_idx][block] = 1 if shift s_idx covers block (minus break), else 0
        coverage_of_shift = []
        for s_idx, s in enumerate(self.shifts):
            coverage_array = [0]*n_blocks

            shift_start_block = s['start'] // self.time_gran
            # Carefully handle 'end' for midnight or next-day
            # minus 1 minute so that if end=480 (8:00), block ends at 479 => block 31
            shift_end_block   = (s['end'] - 1) // self.time_gran if s['end'] > 0 else (24*60 - 1)//self.time_gran

            break_start_block = s['break_start'] // self.time_gran
            break_end_block   = (s['break_end'] - 1) // self.time_gran if s['break_end'] > 0 else break_start_block

            for b in range(n_blocks):
                if shift_start_block <= b <= shift_end_block:
                    # Check if in break
                    if not (break_start_block <= b <= break_end_block):
                        coverage_array[b] = 1

            coverage_of_shift.append(coverage_array)

        # 4c) For each day d, each block b => sum of shift_usage[d,s] must be >= coverage_needed[d,b]
        for d in range(7):
            for b in range(n_blocks):
                req = coverage_needed[(d, b)]
                if req > 0:
                    model.Add(
                        sum(
                            self.shift_usage_vars[(d, s_idx)] * coverage_of_shift[s_idx][b]
                            for s_idx in range(len(self.shifts))
                        ) >= req
                    )

        # ----------------------------------------------------------------
        # 5) Objective: Minimize total cost
        # ----------------------------------------------------------------
        # total cost = sum_{d=0..6} sum_{s_idx} ( shift_usage[d,s_idx] * shift_weight[s_idx] )
        cost_terms = []
        for d in range(7):
            for s_idx, s in enumerate(self.shifts):
                if s['days'][d] == 1:
                    cost_terms.append(
                        self.shift_usage_vars[(d, s_idx)] * s['weight']
                    )

        model.Minimize(sum(cost_terms))

        # Store model for later usage in solve()
        self.model = model

    def solve(self):
        """
        Solve the built CP-SAT model. 
        Stores the status and the solver, so you can retrieve results.
        """
        self.solver = cp_model.CpSolver()
        self.status = self.solver.Solve(self.model)

    def print_solution(self):
        """
        Print a summary of the solution if feasible/optimal.
        """
        if self.status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print(f"Solution status = {self.solver.StatusName(self.status)}")
            print(f"Minimal total cost = {self.solver.ObjectiveValue():.2f}")
            print("Shift usage summary (#nurses each day):")
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

            for d in range(7):
                day_str = day_names[d]
                for s_idx, s in enumerate(self.shifts):
                    usage_val = self.solver.Value(self.shift_usage_vars[(d, s_idx)])
                    if usage_val > 0:
                        start_h = s['start'] // 60
                        start_m = s['start'] % 60
                        end_h   = s['end'] // 60
                        end_m   = s['end'] % 60 if s['end'] != 1440 else 0

                        print(f"  {day_str} | Shift {s_idx}: "
                              f"{usage_val} nurses, "
                              f"time={start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}, "
                              f"weight={s['weight']}")
        else:
            print("No feasible solution found.")

    def get_solution_usage(self):
        """
        Return a dictionary with usage:
            {
              (day, shift_idx): number_of_nurses_assigned,
              ...
            }
        Only valid if self.status is FEASIBLE/OPTIMAL.
        """
        if self.status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return None

        usage = {}
        for key, var in self.shift_usage_vars.items():
            val = self.solver.Value(var)
            if val > 0:
                usage[key] = val
        return usage
