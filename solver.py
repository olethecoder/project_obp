from ortools.sat.python import cp_model
import math

# Global constants
WEEK_MINUTES = 7 * 24 * 60      # 10080 minutes in a week
TIME_GRAN = 15                  # 15-minute blocks
N_BLOCKS = WEEK_MINUTES // TIME_GRAN  # 672 blocks in a week

def minute_to_block(m):
    return m // TIME_GRAN

def add_coverage_blocks(cover_array, start_min, end_min):
    if end_min <= WEEK_MINUTES:
        s_block = minute_to_block(start_min)
        e_block = max(s_block, minute_to_block(end_min - 1))
        for b in range(s_block, min(e_block + 1, N_BLOCKS)):
            cover_array[b] = 1
    else:
        s_block = minute_to_block(start_min)
        for b in range(s_block, N_BLOCKS):
            cover_array[b] = 1
        end2 = end_min - WEEK_MINUTES
        e_block2 = minute_to_block(end2 - 1)
        for b in range(0, min(e_block2 + 1, N_BLOCKS)):
            cover_array[b] = 1

def remove_coverage_blocks(cover_array, start_min, end_min):
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

class OptimalNurseScheduler:
    def __init__(self, shifts_df, tasks_df, max_nurses_per_shift=30):
        self.model = cp_model.CpModel()
        self.shifts_df = shifts_df
        self.tasks_df = tasks_df
        self.max_nurses = max_nurses_per_shift

        self.shift_info = []         # List of shift templates with aggregated coverage
        self.shift_usage_vars = []   # Decision variables per shift template
        self.tasks_info = []         # Task data
        self.task_start_vars = []    # Start block variables for tasks
        self.task_covers_bool = []   # Boolean variables linking tasks to blocks

        self._prepare_shifts()
        self._prepare_tasks()
        self._build_model()

    def _prepare_shifts(self):
        # For each shift template, create a single coverage array covering all active days
        for idx, row in self.shifts_df.iterrows():
            start_str = row['Start']
            end_str = row['End']
            brk_str = row['Break']
            brk_dur = int(row['Break Duration'])
            raw_weight = float(row['Weight'])
            # Day flags: active days of the week for this shift template
            day_flags = [int(row[d]) for d in ['Mo','Tue','Wed','Thu','Fri','Sat','Sun']]

            # Initialize coverage array for the entire week for this shift template
            coverage_arr = [0] * N_BLOCKS

            # Loop over each day of the week for which the shift is active
            for day_index, active in enumerate(day_flags):
                if not active:
                    continue

                day_offset = day_index * 1440  # minutes offset for the day
                s_h, s_m = map(int, start_str.split(':'))
                e_h, e_m = map(int, end_str.split(':'))

                start_min = day_offset + s_h * 60 + s_m

                # Handle overnight shift crossing midnight
                if e_h * 60 + e_m < s_h * 60 + s_m:
                    # Shift ends on next day
                    end_min = start_min + ((24*60 - (s_h*60+s_m)) + (e_h*60+e_m))
                else:
                    end_min = day_offset + e_h * 60 + e_m

                bh, bm = map(int, brk_str.split(':'))
                break_start = day_offset + bh * 60 + bm
                if break_start < start_min:
                    break_start += 1440
                break_end = break_start + brk_dur

                # Clamp break within shift boundaries
                if break_start < start_min:
                    break_start = start_min
                if break_end > end_min:
                    break_end = end_min

                # Update coverage array for this day's portion of the shift
                add_coverage_blocks(coverage_arr, start_min, end_min)
                remove_coverage_blocks(coverage_arr, break_start, break_end)

            weight_scaled = int(round(raw_weight * 100))
            shift_len_blocks = sum(coverage_arr)
            self.shift_info.append({
                "coverage": coverage_arr,
                "weight_scaled": weight_scaled,
                "length_blocks": shift_len_blocks
            })

    def _prepare_tasks(self):
        # Prepare tasks for each active day (similar to before)
        for idx, row in self.tasks_df.iterrows():
            name = row['tasks']
            start_str = row['start']
            end_str = row['end']
            duration = int(row['duration_min'])
            raw_req = float(row['# Nurses'])
            required = int(round(raw_req)) if abs(raw_req - round(raw_req)) < 1e-9 else int(round(raw_req))
            day_flags = [int(row[d]) for d in ['ma','di','wo','do','vri','za','zo']]

            for day_index, active in enumerate(day_flags):
                if not active:
                    continue

                day_offset = day_index * 1440
                sh, sm = map(int, start_str.split(':'))
                eh, em = map(int, end_str.split(':'))
                earliest_min = day_offset + sh * 60 + sm
                latest_min = day_offset + eh * 60 + em
                if latest_min < earliest_min:
                    latest_min += WEEK_MINUTES

                duration_blocks = duration // TIME_GRAN
                earliest_block = earliest_min // TIME_GRAN
                latest_block = latest_min // TIME_GRAN

                self.tasks_info.append({
                    "name": name,
                    "earliest_block": earliest_block,
                    "latest_block": latest_block,
                    "duration_blocks": duration_blocks,
                    "required_nurses": required
                })

    def _build_model(self):
        # Create one variable for each shift template
        for s_idx, _ in enumerate(self.shift_info):
            var = self.model.NewIntVar(0, self.max_nurses, f"shift_{s_idx}_usage")
            self.shift_usage_vars.append(var)

        # Create task start variables and booleans for each block
        for i, t in enumerate(self.tasks_info):
            e_b = t["earliest_block"]
            l_b = t["latest_block"]
            d_b = t["duration_blocks"]

            start_var = self.model.NewIntVar(e_b, l_b, f"task_{i}_start")
            self.task_start_vars.append(start_var)

            bools_b = []
            for b in range(N_BLOCKS):
                boolvar = self.model.NewBoolVar(f"task_{i}_covers_{b}")
                bools_b.append(boolvar)
            self.task_covers_bool.append(bools_b)

        # Reification constraints: link task coverage booleans with task start times
        for i, t in enumerate(self.tasks_info):
            d_b = t["duration_blocks"]
            startv = self.task_start_vars[i]
            for b in range(N_BLOCKS):
                boolvar = self.task_covers_bool[i][b]
                aux1 = self.model.NewBoolVar(f"aux1_{i}_{b}")
                aux2 = self.model.NewBoolVar(f"aux2_{i}_{b}")

                self.model.Add(startv <= b).OnlyEnforceIf(aux1)
                self.model.Add(startv > b).OnlyEnforceIf(aux1.Not())

                self.model.Add(b < startv + d_b).OnlyEnforceIf(aux2)
                self.model.Add(b >= startv + d_b).OnlyEnforceIf(aux2.Not())

                self.model.AddBoolAnd([aux1, aux2]).OnlyEnforceIf(boolvar)
                self.model.AddBoolOr([aux1.Not(), aux2.Not()]).OnlyEnforceIf(boolvar.Not())

        # Coverage constraints per block
        for b in range(N_BLOCKS):
            left_expr = []
            for s_idx, sh in enumerate(self.shift_info):
                if sh["coverage"][b] > 0:
                    left_expr.append(self.shift_usage_vars[s_idx] * sh["coverage"][b])
            right_expr = []
            for i, t in enumerate(self.tasks_info):
                req = t["required_nurses"]
                boolvar = self.task_covers_bool[i][b]
                right_expr.append(req * boolvar)
            self.model.Add(sum(left_expr) >= sum(right_expr))

        # Objective: minimize total cost
        cost_terms = []
        for s_idx, sh in enumerate(self.shift_info):
            usage_var = self.shift_usage_vars[s_idx]
            blocks_count = sh["length_blocks"]
            w_scaled = sh["weight_scaled"]
            cost_terms.append(usage_var * blocks_count * w_scaled)
        self.model.Minimize(sum(cost_terms))

    def solve(self):
        solver = cp_model.CpSolver()
        status = solver.Solve(self.model)
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print("Solution found!")
            for s_idx, var in enumerate(self.shift_usage_vars):
                print(f"Shift {s_idx} usage: {solver.Value(var)}")
            print("Total cost:", solver.ObjectiveValue()/100.0)
        else:
            print("No solution found.")
