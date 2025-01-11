import pandas as pd
from ortools.sat.python import cp_model

def hhmm_to_minutes(hhmm: str) -> int:
    """
    Convert 'HH:MM' to total minutes from 00:00.
    Special handling for '0:00' => 24*60 (end of day).
    """
    hh, mm = hhmm.split(':')
    hh = int(hh)
    mm = int(mm)
    if hh == 0 and mm == 0:
        return 24 * 60
    return hh * 60 + mm

class NurseSchedulingSolver:
    """
    A CP-SAT solver that:
      - Uses 'use-once' shift activation with a binary variable.
      - Assigns an integer #nurses to each activated shift.
      - Coverage is enforced in 15-minute blocks.
      - Cost is computed in '15-minute units' times scaled weight.
        => shift_length_units = (shift_minutes - break_minutes)/15 (rounded),
           weight_scaled = round(weight * 100)
        => cost = shift_length_units * weight_scaled * nurses * days_active
      - We interpret cost/100 if you want to see a float cost. 
    """

    def __init__(self, shifts_df, tasks_df, time_granularity=15, max_nurses=30):
        """
        Args:
          shifts_df (pd.DataFrame):
            Columns: [Start, End, Break, Break Duration, Weight, Mo, Tue, Wed, Thu, Fri, Sat, Sun]
          tasks_df (pd.DataFrame):
            Columns: [tasks, start, end, duration_min, ma, di, wo, do, vri, za, zo, # Nurses]
          time_granularity (int):
            Typically 15 => coverage blocks of 15 minutes.
          max_nurses (int):
            The maximum integer #nurses allowed for one shift.
        """
        self.shifts_df       = shifts_df
        self.tasks_df        = tasks_df
        self.time_gran       = time_granularity
        self.max_nurses      = max_nurses

        self.model           = None
        self.solver          = None
        self.status          = None

        self.shifts          = []
        self.tasks           = []

        self.activate_vars   = []
        self.nurses_vars     = []
        self.coverage_matrix = []
        self.coverage_needed = {}

        # Build the CP model immediately
        self._build_model()

    def _build_model(self):
        model = cp_model.CpModel()

        # ---------------------------------------------------------
        # 1) Process SHIFT data
        # ---------------------------------------------------------
        for idx, row in self.shifts_df.iterrows():
            s_start = hhmm_to_minutes(row['Start'])
            s_end   = hhmm_to_minutes(row['End'])
            b_start = hhmm_to_minutes(row['Break'])
            b_dur   = int(row['Break Duration'])  # break in minutes
            b_end   = b_start + b_dur

            weight_raw = float(row['Weight'])
            # Scale weight by 100 => store as integer
            weight_scaled = int(round(weight_raw * 100))

            days_arr = [
                int(row['Mo']),
                int(row['Tue']),
                int(row['Wed']),
                int(row['Thu']),
                int(row['Fri']),
                int(row['Sat']),
                int(row['Sun']),
            ]

            # shift_minutes = (end - start) - break_duration
            shift_minutes = (s_end - s_start) - b_dur
            if shift_minutes < 0:
                # Could happen if crossing midnight or break > shift. We'll clamp to 0.
                shift_minutes = 0

            # Convert shift_minutes to # of 15-min units
            # e.g., 450 minutes => 450/15=30 units
            # Use rounding in case it's not multiple of 15
            shift_length_units = int(round(shift_minutes / 15.0))
            if shift_length_units < 0:
                shift_length_units = 0

            self.shifts.append({
                'start' : s_start,
                'end'   : s_end,
                'break_start': b_start,
                'break_end'  : b_end,
                'days'  : days_arr,
                'weight_scaled': weight_scaled,  # integer
                'shift_length_units': shift_length_units
            })

        # ---------------------------------------------------------
        # 2) Process TASK data
        # ---------------------------------------------------------
        for idx, row in self.tasks_df.iterrows():
            earliest = hhmm_to_minutes(row['start'])
            latest   = hhmm_to_minutes(row['end'])
            duration = int(row['duration_min'])

            # Possibly float # Nurses => round to int
            raw_req = float(row['# Nurses'])
            if abs(raw_req - round(raw_req)) < 1e-9:
                required = int(round(raw_req))
            else:
                required = int(round(raw_req))

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

        # ---------------------------------------------------------
        # 3) Build coverage_needed per (day, block)
        # ---------------------------------------------------------
        n_blocks = (24 * 60) // self.time_gran
        for d in range(7):
            for b in range(n_blocks):
                self.coverage_needed[(d, b)] = 0

        # Fill coverage from tasks
        for d in range(7):
            day_tasks = [t for t in self.tasks if t['days'][d] == 1]
            for t in day_tasks:
                earliest_min = t['earliest_start']
                latest_min   = t['latest_start']
                req_nurses   = t['required_nurses']

                # We'll just cover [earliest_min..latest_min) block-wise
                start_block = earliest_min // self.time_gran
                end_block   = (latest_min - 1)//self.time_gran if latest_min>0 else (24*60 - 1)//self.time_gran

                for b in range(start_block, end_block+1):
                    if 0 <= b < n_blocks:
                        self.coverage_needed[(d, b)] += req_nurses

        # ---------------------------------------------------------
        # 4) coverage_of_shift[s][d][b] => 1 if shift covers block
        # ---------------------------------------------------------
        self.coverage_matrix = []
        for s_idx, s in enumerate(self.shifts):
            cov_2d = [[0]*n_blocks for _ in range(7)]

            shift_start_block = s['start'] // self.time_gran
            # end_block = (end-1)//time_gran if end>0 else (24*60-1)//time_gran
            shift_end_block   = (s['end'] - 1)//self.time_gran if s['end']>0 else (24*60-1)//self.time_gran

            # We do a single break range:
            # but we actually don't need break for coverage if we already subtracted break minutes from shift length.
            # However, if you do want coverage gaps, you can set coverage_2d=0 in the break range:
            # for now let's do as usual:
            b_start_block = s['break_start'] // self.time_gran
            b_end_block   = (s['break_end'] - 1)//self.time_gran if s['break_end']>0 else b_start_block

            for d in range(7):
                if s['days'][d] == 1:
                    for b in range(n_blocks):
                        if shift_start_block <= b <= shift_end_block:
                            # exclude break blocks
                            if not (b_start_block <= b <= b_end_block):
                                cov_2d[d][b] = 1
            self.coverage_matrix.append(cov_2d)

        # ---------------------------------------------------------
        # 5) Decision variables: activate[s], nurses[s]
        # ---------------------------------------------------------
        self.activate_vars = []
        self.nurses_vars  = []
        for s_idx, s in enumerate(self.shifts):
            activate_var = model.NewBoolVar(f"activate_shift_{s_idx}")
            nurses_var   = model.NewIntVar(0, self.max_nurses, f"nurses_shift_{s_idx}")

            # if not activated => #nurses=0
            model.Add(nurses_var <= self.max_nurses * activate_var)

            self.activate_vars.append(activate_var)
            self.nurses_vars.append(nurses_var)

        # ---------------------------------------------------------
        # 6) Coverage constraints
        # ---------------------------------------------------------
        for d in range(7):
            for b in range(n_blocks):
                needed = self.coverage_needed[(d, b)]
                if needed > 0:
                    model.Add(
                        sum(
                            self.nurses_vars[s_idx] * self.coverage_matrix[s_idx][d][b]
                            for s_idx in range(len(self.shifts))
                        ) >= needed
                    )

        # ---------------------------------------------------------
        # 7) Objective: cost in 15-min units
        # ---------------------------------------------------------
        # cost = sum_{s} ( shift_length_units[s] * weight_scaled[s] * #nurses[s] * sum(days[s]) )
        cost_terms = []
        for s_idx, s in enumerate(self.shifts):
            days_count = sum(s['days'])
            length_units = s['shift_length_units']     # number of 15-min blocks
            w_scaled     = s['weight_scaled']          # weight*100

            expr = self.nurses_vars[s_idx] * w_scaled * length_units * days_count
            cost_terms.append(expr)

        model.Minimize(sum(cost_terms))

        self.model = model

    def solve(self):
        """Run the CP-SAT solver."""
        self.solver = cp_model.CpSolver()
        self.status = self.solver.Solve(self.model)

    def print_solution(self):
        """Print solution details if feasible."""
        if self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f"Solution: {self.solver.StatusName(self.status)}")
            raw_obj = self.solver.ObjectiveValue()  # integer
            # We can interpret cost as raw_obj / 100 => cost in "weight-units of 15-min blocks"
            cost_float = raw_obj / 100.0
            print(f"Minimal cost = {cost_float:.2f} (scaled by /100)")

            print("Activated shifts:")
            for s_idx, s in enumerate(self.shifts):
                active = self.solver.Value(self.activate_vars[s_idx])
                nurses = self.solver.Value(self.nurses_vars[s_idx])
                if active == 1 and nurses > 0:
                    days_count   = sum(s['days'])
                    length_units = s['shift_length_units']
                    w_scaled     = s['weight_scaled']
                    partial_cost = nurses * w_scaled * length_units * days_count
                    print(f"  Shift {s_idx}: {nurses} nurses, "
                          f"{length_units} *15-min blocks/day, "
                          f"days={days_count}, "
                          f"weight_scaled={w_scaled}, "
                          f"cost_contrib={partial_cost/100:.2f}")
        else:
            print("No feasible solution found.")

    def get_shift_usage(self):
        """
        Returns a list of dicts describing each shift usage.
        'partial_cost_int' is the scaled integer cost, 
        'partial_cost_float' = partial_cost_int / 100 => real cost in '15-min weight' units.
        """
        if self.status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return []

        usage = []
        for s_idx, s in enumerate(self.shifts):
            active = self.solver.Value(self.activate_vars[s_idx])
            nurses = self.solver.Value(self.nurses_vars[s_idx])
            days_count = sum(s['days'])
            cost_int = active * nurses * s['weight_scaled'] * s['shift_length_units'] * days_count

            usage.append({
                "shift_idx": s_idx,
                "activated": active,
                "nurses": nurses,
                "days_active": s["days"],
                "shift_length_15min_units": s["shift_length_units"],
                "weight_scaled": s["weight_scaled"],
                "partial_cost_int": cost_int,
                "partial_cost_float": cost_int / 100.0
            })
        return usage
