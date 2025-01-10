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
    A CP-SAT solver demonstrating the 'use-once, pay-for-all-days' approach:
      - We have a set of SHIFT PATTERNS that might span multiple days in the week.
      - If we 'activate' a shift pattern, we pay for it across all days that pattern is valid.
      - We decide how many nurses to assign to that pattern (0 to some max).
      - Tasks coverage is checked day-by-day, but the shift nurse count is a single integer.
    """

    def __init__(self, shifts_df, tasks_df, time_granularity=15, max_nurses=30):
        """
        Args:
          shifts_df (pd.DataFrame):
            Columns:
              [Start, End, Break, Break Duration, Weight, Mo, Tue, Wed, Thu, Fri, Sat, Sun]
            Each row is a single SHIFT pattern that might repeat across multiple days.

          tasks_df (pd.DataFrame):
            Columns:
              [tasks, start, end, duration_min, ma, di, wo, do, vri, za, zo, # Nurses]

          time_granularity (int):
            In minutes, default 15 => discretize day in 96 blocks.

          max_nurses (int):
            The maximum # of nurses you can assign to any one shift pattern.
        """
        self.shifts_df       = shifts_df
        self.tasks_df        = tasks_df
        self.time_gran       = time_granularity
        self.max_nurses      = max_nurses

        # Data structures for the model
        self.model           = None
        self.solver          = None
        self.status          = None

        self.shifts          = []  # Will hold shift info as dict
        self.tasks           = []  # Will hold task info as dict

        self.activate_vars   = []  # activate[s] => whether shift s is used
        self.nurses_vars     = []  # shift_nurses[s] => how many nurses assigned to shift s
        self.coverage_matrix = []  # coverage_of_shift[s][d][b] => 0 or 1
        self.coverage_needed = {}  # coverage_needed[(d,b)]

        # Build everything
        self._build_model()

    def _build_model(self):
        model = cp_model.CpModel()

        # 1) Preprocess SHIFT data
        #    Each shift is valid on some subset of days. We'll gather:
        #     - start, end, break window
        #     - weight
        #     - days array [Mo..Sun]
        #     - active_days_count = sum of days
        for idx, row in self.shifts_df.iterrows():
            s_start = hhmm_to_minutes(row['Start'])
            s_end   = hhmm_to_minutes(row['End'])
            b_start = hhmm_to_minutes(row['Break'])
            b_dur   = int(row['Break Duration'])
            b_end   = b_start + b_dur
            weight  = float(row['Weight'])

            days_arr = [
                int(row['Mo']),
                int(row['Tue']),
                int(row['Wed']),
                int(row['Thu']),
                int(row['Fri']),
                int(row['Sat']),
                int(row['Sun']),
            ]
            active_days_count = sum(days_arr)

            self.shifts.append({
                'start': s_start,
                'end'  : s_end,
                'break_start': b_start,
                'break_end'  : b_end,
                'weight': weight,
                'days'  : days_arr,
                'active_days_count': active_days_count
            })

        # 2) Preprocess TASK data
        #    Each task has earliest_start, latest_start, duration, required_nurses, days [ma..zo].
        for idx, row in self.tasks_df.iterrows():
            earliest = hhmm_to_minutes(row['start'])
            latest   = hhmm_to_minutes(row['end'])
            duration = int(row['duration_min'])
            required = int(row['# Nurses'])

            days_arr = [
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
                'days'           : days_arr
            })

        # 3) Prepare coverage_needed[(d,b)]
        n_blocks = (24 * 60) // self.time_gran
        for d in range(7):
            for b in range(n_blocks):
                self.coverage_needed[(d,b)] = 0

        # For each task that is active on day d, from earliest_start..latest_start
        # we add the required nurses to coverage_needed. (Same "worst-case" approach.)
        for d in range(7):
            day_tasks = [t for t in self.tasks if t['days'][d] == 1]
            for t in day_tasks:
                earliest = t['earliest_start']
                latest   = t['latest_start']
                duration = t['duration']
                required = t['required_nurses']

                # The latest the task can start is (latest - duration)
                feasible_end = max(earliest, latest - duration)

                # Let's keep it simple: we assume the task might occupy ANY block from earliest..latest-1
                start_block = earliest // self.time_gran
                end_block   = (latest - 1) // self.time_gran  # inclusive

                # Increment coverage_needed by 'required' for each block in [start_block..end_block]
                for block in range(start_block, end_block + 1):
                    if 0 <= block < n_blocks:
                        self.coverage_needed[(d, block)] += required

        # 4) Build coverage_of_shift[s][d][b] => 0 or 1
        #    If shift s covers day d (days[s][d] == 1) and block b, excluding break, then =1
        self.coverage_matrix = []
        for s_idx, s in enumerate(self.shifts):
            coverage_2d = [[0]*n_blocks for _ in range(7)]  # coverage_2d[d][b]
            shift_start_block = s['start'] // self.time_gran
            shift_end_block   = (s['end'] - 1)//self.time_gran if s['end']>0 else 95
            break_start_block = s['break_start'] // self.time_gran
            break_end_block   = (s['break_end'] - 1)//self.time_gran if s['break_end']>0 else break_start_block

            for d in range(7):
                if s['days'][d] == 1:
                    for b in range(n_blocks):
                        if (shift_start_block <= b <= shift_end_block):
                            # exclude break
                            if not (break_start_block <= b <= break_end_block):
                                coverage_2d[d][b] = 1
                else:
                    # shift not active that day => coverage_2d[d][b] = 0
                    pass

            self.coverage_matrix.append(coverage_2d)

        # 5) Create decision variables
        #    - activate[s] in {0,1}
        #    - shift_nurses[s] in [0, max_nurses]
        self.activate_vars = []
        self.nurses_vars  = []
        for s_idx, s in enumerate(self.shifts):
            activate_var = model.NewBoolVar(f"activate_shift_{s_idx}")
            nurses_var   = model.NewIntVar(0, self.max_nurses, f"shift_nurses_{s_idx}")

            # link them: if not activated => 0 nurses
            model.Add(nurses_var <= self.max_nurses * activate_var)
            self.activate_vars.append(activate_var)
            self.nurses_vars.append(nurses_var)

        # 6) Coverage constraint
        # For each day d, block b => sum over all shifts [ shift_nurses[s] * coverage_of_shift[s][d][b] ] >= coverage_needed
        for d in range(7):
            for b in range(n_blocks):
                req = self.coverage_needed[(d, b)]
                if req > 0:
                    model.Add(
                        sum(
                            self.nurses_vars[s_idx] * self.coverage_matrix[s_idx][d][b]
                            for s_idx in range(len(self.shifts))
                        ) >= req
                    )

        # 7) Cost: sum_{s} ( shift_nurses[s] * weight[s] * active_days_count[s] )
        # We do NOT multiply by activate[s] because shift_nurses[s] cannot be >0 unless activate[s]=1.
        # But it’s often clearer to do: (activate[s]* shift_nurses[s]* weight[s]* days_count[s]).
        cost_terms = []
        for s_idx, s in enumerate(self.shifts):
            # number_of_active_days is how many days shift s covers
            ndays = s['active_days_count']
            w     = s['weight']

            # cost for shift s:
            # shift_nurses[s_idx] * w * ndays
            cost_terms.append(
                self.nurses_vars[s_idx] * w * ndays
            )

        model.Minimize(sum(cost_terms))

        self.model = model

    def solve(self):
        self.solver = cp_model.CpSolver()
        self.status = self.solver.Solve(self.model)

    def print_solution(self):
        if self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f"Solution status: {self.solver.StatusName(self.status)}")
            print(f"Minimal total cost: {self.solver.ObjectiveValue():.2f}")
            print("Activated shifts summary:")
            for s_idx, s in enumerate(self.shifts):
                activated = self.solver.Value(self.activate_vars[s_idx])
                nurse_cnt = self.solver.Value(self.nurses_vars[s_idx])
                if activated == 1 and nurse_cnt > 0:
                    print(
                        f"  Shift {s_idx}: {nurse_cnt} nurses, "
                        f"days active={s['days']}, "
                        f"weight={s['weight']}, "
                        f"active_days_count={s['active_days_count']}"
                    )
        else:
            print("No feasible solution found or the solver didn't converge.")

    def get_shift_usage(self):
        """
        Returns a list of dicts, each describing shift usage:
          [
            {
              "shift_idx": ...,
              "activated": 0 or 1,
              "nurses": number of nurses,
              "days_active": [0..1 for Mo..Sun],
              "weight": ...
            },
            ...
          ]
        """
        if self.status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return []

        usage_info = []
        for s_idx, s in enumerate(self.shifts):
            usage_info.append({
                "shift_idx": s_idx,
                "activated": self.solver.Value(self.activate_vars[s_idx]),
                "nurses"   : self.solver.Value(self.nurses_vars[s_idx]),
                "days_active": s["days"],
                "weight"   : s["weight"],
                "active_days_count": s["active_days_count"]
            })
        return usage_info
