"""
preprocessing.py

This file contains all preprocessing logic for the nurse scheduling problem.
We convert shifts and tasks into week-based minutes and 15-minute block coverage,
including break handling and wrapping across midnight or Sunday->Monday.
The resulting data structures can be used by different solvers (CP, Gurobi, etc.).
"""

import pandas as pd

# -----------------------------
# Global constants
# -----------------------------
WEEK_MINUTES = 7 * 24 * 60      # 10,080 minutes in a week
TIME_GRAN = 15                  # 15-minute blocks
N_BLOCKS = WEEK_MINUTES // TIME_GRAN  # 672 blocks in a week

def minute_to_block(m: int) -> int:
    """Convert an absolute minute in the week to a block index (15-min increments).

    Args:
        m (int): The minute in [0..10080).

    Returns:
        int: The block index (0 <= block < 672).
    """
    return m // TIME_GRAN

def block_to_minute(b: int) -> int:
    """Convert a 15-minute block index back to an absolute minute in the week.

    Args:
        b (int): The block index (0 <= b < 672).

    Returns:
        int: The corresponding minute in [0..10080).
    """
    return b * TIME_GRAN

def block_to_timestr(b: int) -> str:
    """Convert a block index into an 'HH:MM' string (mod 24 hours),
    ignoring day of the week.

    Args:
        b (int): The block index (0 <= b < 672).

    Returns:
        str: Time in 'HH:MM' format, e.g. '08:15'.
    """
    blocks_per_day = 1440 // TIME_GRAN  # 1440 / 15 = 96
    minute_of_day = block_to_minute(b % blocks_per_day)
    hh = minute_of_day // 60
    mm = minute_of_day % 60
    return f"{hh:02d}:{mm:02d}"

def add_coverage_blocks(cover_array, start_min, end_min):
    """Mark cover_array[b] = 1 for blocks in [start_min, end_min).

    Wraps if needed from Sunday -> Monday.

    Args:
        cover_array (list of int): An array of length N_BLOCKS (672),
            initially filled with 0s.
        start_min (int): Start minute of coverage (>= 0).
        end_min (int): End minute of coverage (exclusive).
    """
    if end_min <= WEEK_MINUTES:
        
        e_block = max(s_block, minute_to_block(end_min - 1))
        for b in range(s_block, min(e_block + 1, N_BLOCKS)):
            cover_array[b] = 1
    else:
      
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

class Preprocessor:
    def __init__(self, shifts_df, tasks_df, max_nurses_per_shift=30):
        self.shifts_df = shifts_df
        self.tasks_df = tasks_df
        self.max_nurses = max_nurses_per_shift

        self.shift_info = []         # List of shift templates with aggregated coverage
        self.shift_usage_vars = []   # Decision variables per shift template
        self.tasks_info = []         # Task data
        self.task_start_vars = []    # Start block variables for tasks
        self.task_covers_bool = []   # Boolean variables linking tasks to blocks

        self.task_map = []

        self._prepare_shifts()
        self._prepare_tasks()

    def _prepare_shifts(self):
        # For each shift template, create a single coverage array covering all active days
        for idx, row in self.shifts_df.iterrows():
            shift_name   = row["name"] 
            max_nurses   = int(row["max_nurses"])
            start_str = row['start']
            end_str = row['end']
            brk_str = row['break']
            brk_dur = int(row['break_duration'])
            raw_weight = float(row['weight'])
            # Day flags: active days of the week for this shift template
            day_flags = [int(row[d]) for d in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']]
            print(day_flags)
            # Initialize coverage array for the entire week for this shift template
            coverage_arr = [0] * 672
            start_arr = [0] * 672 #CHECK

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
                add_coverage_blocks(coverage_arr, start_arr, start_min, end_min)
                remove_coverage_blocks(coverage_arr, break_start, break_end)

            weight_scaled = int(round(raw_weight * 100))
            shift_len_blocks = sum(coverage_arr)
            self.shift_info.append({
                "name": shift_name,
                "coverage": coverage_arr,
                "weight_scaled": weight_scaled,
                "length_blocks": shift_len_blocks,
                "max_nurses": max_nurses,
                "starting_blocks": start_arr
            })

    def _prepare_tasks(self):
        # Prepare tasks for each active day (similar to before)
        for idx, row in self.tasks_df.iterrows():
            name = row['task']
            start_str = row['start']
            end_str = row['end']
            duration = int(row['duration_min'])
            raw_req = float(row['nurses_required'])
            required = int(round(raw_req)) if abs(raw_req - round(raw_req)) < 1e-9 else int(round(raw_req))
            day_flags = [int(row[d]) for d in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']]

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
                    "task_name": name,
                    "earliest_block": earliest_block,
                    "latest_block": latest_block,
                    "duration_blocks": duration_blocks,
                    "required_nurses": required
                })

                self.task_map.append((idx, day_index))
