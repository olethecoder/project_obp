import math
import pandas as pd
from ortools.sat.python import cp_model

# -------------------------------------------------------------------
# GLOBALS: 7-day horizon, 15-minute blocks
# -------------------------------------------------------------------
WEEK_MINUTES = 7 * 24 * 60  # 10080
TIME_GRAN = 15              # 15 minutes
N_BLOCKS = WEEK_MINUTES // TIME_GRAN  # 672

def wrap_time(minute):
    return minute % WEEK_MINUTES

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
        last_b  = N_BLOCKS - 1
        for b in range(s_block, last_b+1):
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

class NurseSchedulingSolver:
    def __init__(self, shifts_df, tasks_df, max_nurses_per_shift=30):
        self.model = cp_model.CpModel()
        self.solver = None
        self.status = None

        self.shifts_df = shifts_df
        self.tasks_df  = tasks_df
        self.max_nurses = max_nurses_per_shift

        self.shift_info = []
        self.shift_usage_vars = []

        self.tasks_info = []
        self.task_start_vars = []
        self.task_covers_bool = []

        self._prepare_shifts()
        self._prepare_tasks()
        self._build_model()

    def _prepare_shifts(self):
        for idx, row in self.shifts_df.iterrows():
            start_str = row['Start']
            end_str   = row['End']
            brk_str   = row['Break']
            brk_dur   = int(row['Break Duration'])
            raw_weight= float(row['Weight'])

            day_flags = [
                int(row['Mo']), int(row['Tue']), int(row['Wed']),
                int(row['Thu']), int(row['Fri']), int(row['Sat']),
                int(row['Sun'])
            ]

            for day_index, active in enumerate(day_flags):
                if not active:
                    continue

                day_offset = day_index * 1440  
                s_h, s_m = map(int, start_str.split(':'))
                e_h, e_m = map(int, end_str.split(':'))
                start_min = day_offset + s_h * 60 + s_m

                # Adjust end_min calculation to correctly handle overnight shifts
                if e_h*60 + e_m < s_h*60 + s_m:
                    # Shift crosses midnight: calculate duration until midnight plus time after midnight
                    end_min = start_min + ((24*60 - (s_h*60 + s_m)) + (e_h*60 + e_m))
                else:
                    end_min = day_offset + e_h * 60 + e_m

                # Proceed with break handling and coverage as before
                bh, bm = map(int, brk_str.split(':'))
                break_start = day_offset + bh * 60 + bm
                if break_start < start_min:
                    break_start += 1440  # Adjust by a day if needed
                break_end = break_start + brk_dur

                # Clamp break within shift boundaries
                if break_start < start_min:
                    break_start = start_min
                if break_end > end_min:
                    break_end = end_min

                coverage_arr = [0]*N_BLOCKS
                add_coverage_blocks(coverage_arr, start_min, end_min)
                if break_start < break_end:
                    remove_coverage_blocks(coverage_arr, break_start, break_end)

                weight_scaled = int(round(raw_weight * 100))
                shift_len_blocks = sum(coverage_arr)

                self.shift_info.append({
                    "coverage": coverage_arr,
                    "weight_scaled": weight_scaled,
                    "length_blocks": shift_len_blocks
                })

    def _prepare_tasks(self):
        for idx, row in self.tasks_df.iterrows():
            name      = row['tasks']
            start_str = row['start']
            end_str   = row['end']
            duration  = int(row['duration_min'])
            raw_req   = float(row['# Nurses'])
            required  = int(round(raw_req)) if abs(raw_req - round(raw_req)) < 1e-9 else int(round(raw_req))

            day_flags = [
                int(row['ma']), int(row['di']), int(row['wo']),
                int(row['do']), int(row['vri']), int(row['za']),
                int(row['zo'])
            ]

            for day_index, active in enumerate(day_flags):
                if not active:
                    continue

                day_offset = day_index * 1440
                sh, sm = map(int, start_str.split(':'))
                eh, em = map(int, end_str.split(':'))
                earliest_min = day_offset + sh*60 + sm
                latest_min   = day_offset + eh*60 + em
                if latest_min < earliest_min:
                    latest_min += WEEK_MINUTES

                duration_blocks = duration // TIME_GRAN
                earliest_block = earliest_min // TIME_GRAN
                # Allow tasks to start anywhere in the window, regardless of duration
                latest_block   = latest_min // TIME_GRAN

                self.tasks_info.append({
                    "name": name,
                    "earliest_block": earliest_block,
                    "latest_block": latest_block,
                    "duration_blocks": duration_blocks,
                    "required_nurses": required
                })

    def _build_model(self):
        # 1) SHIFT usage variables
        for s_idx, sh in enumerate(self.shift_info):
            var = self.model.NewIntVar(0, self.max_nurses, f"shift_{s_idx}_usage")
            self.shift_usage_vars.append(var)

        # 2) TASK intervals: integer start var + boolean coverage for each block
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

        # 3) Reify: "block b is covered by task i" <=> start_i <= b < start_i+duration
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

        # 4) Coverage constraints at each block b
        for b in range(N_BLOCKS):
            left_expr = []
            for s_idx, sh in enumerate(self.shift_info):
                if sh["coverage"][b] > 0:
                    left_expr.append(self.shift_usage_vars[s_idx])

            right_expr = []
            for i, t in enumerate(self.tasks_info):
                req = t["required_nurses"]
                boolvar = self.task_covers_bool[i][b]
                right_expr.append(req * boolvar)

            self.model.Add(sum(left_expr) >= sum(right_expr))

        # 5) Minimize cost
        cost_terms = []
        for s_idx, sh in enumerate(self.shift_info):
            usage_var    = self.shift_usage_vars[s_idx]
            blocks_count = sh["length_blocks"]
            w_scaled     = sh["weight_scaled"]
            cost_terms.append(usage_var * blocks_count * w_scaled)

        self.model.Minimize(sum(cost_terms))

    def solve(self):
        self.solver = cp_model.CpSolver()
        self.status = self.solver.Solve(self.model)

    def print_solution(self):
        if self.status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print(f"Solution status: {self.solver.StatusName(self.status)}")
            total_cost_int = self.solver.ObjectiveValue()
            cost_float = total_cost_int/100.0
            print(f"Minimal total cost = {cost_float:.2f}\n")

            print("Shift usage:")
            for s_idx, sh in enumerate(self.shift_info):
                val = self.solver.Value(self.shift_usage_vars[s_idx])
                if val>0:
                    length_blk = sh["length_blocks"]
                    w_scaled   = sh["weight_scaled"]
                    partial_cost = val*length_blk*w_scaled
                    print(f" Shift {s_idx}: nurses={val}, shift_blocks={length_blk}, "
                          f"weight_scaled={w_scaled}, cost={partial_cost/100:.2f}")

            print("\nTasks schedule:")
            for i, t in enumerate(self.tasks_info):
                start_val = self.solver.Value(self.task_start_vars[i])
                print(f" Task {i} '{t['name']}': start_block={start_val},"
                      f" earliest={t['earliest_block']}, latest={t['latest_block']}, "
                      f"dur_blocks={t['duration_blocks']}, required_nurses={t['required_nurses']}")
                start_min = start_val*TIME_GRAN
                hh = start_min//60
                mm = start_min%60
                print(f"   => starts at day={(hh//24)} h={(hh%24)}:{mm:02d}, length={t['duration_blocks']*15} min")
        else:
            print("No feasible solution found or the solver didn't converge.")

    def get_solution_usage(self):
        if self.status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return None

        usage_data = {
            "shifts": [],
            "tasks": []
        }
        for s_idx, sh in enumerate(self.shift_info):
            val = self.solver.Value(self.shift_usage_vars[s_idx])
            usage_data["shifts"].append(val)

        for i, t in enumerate(self.tasks_info):
            usage_data["tasks"].append(self.solver.Value(self.task_start_vars[i]))

        return usage_data
