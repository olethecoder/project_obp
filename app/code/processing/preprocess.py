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
    if end_min < WEEK_MINUTES:
        s_block = minute_to_block(start_min)
        e_block = max(s_block, minute_to_block(end_min))
        for b in range(s_block, min(e_block + 1, N_BLOCKS)): # e_block + 1 to include final block
            cover_array[b] = 1
    else:
        # crosses boundary from Sunday -> Monday
        s_block = minute_to_block(start_min)
        for b in range(s_block, N_BLOCKS):
            cover_array[b] = 1
        end2 = end_min - WEEK_MINUTES
        e_block2 = minute_to_block(end2)
        for b in range(0, min(e_block2 + 1, N_BLOCKS)):
            cover_array[b] = 1

def remove_coverage_blocks(cover_array, start_min, end_min):
    """Mark cover_array[b] = 0 for blocks in [start_min, end_min).

    Wraps if needed from Sunday -> Monday.

    Args:
        cover_array (list of int): An array of length N_BLOCKS (672).
        start_min (int): Start minute of the interval (>= 0).
        end_min (int): End minute of the interval (exclusive).
    """
    if end_min < WEEK_MINUTES:
        s_block = minute_to_block(start_min)
        e_block = max(s_block, minute_to_block(end_min))
        for b in range(s_block, min(e_block + 1, N_BLOCKS)):
            cover_array[b] = 0
    else:
        # crosses boundary
        s_block = minute_to_block(start_min)
        for b in range(s_block, N_BLOCKS):
            cover_array[b] = 0
        end2 = end_min - WEEK_MINUTES
        e_block2 = minute_to_block(end2)
        for b in range(0, min(e_block2 + 1, N_BLOCKS)):
            cover_array[b] = 0

class NurseSchedulingPreprocessor:
    """Preprocess shifts and tasks into data structures for nurse scheduling.

    Responsibilities:
      - Convert day-of-week + HH:MM times into absolute minutes [0..10080).
      - Handle crossing-midnight logic in start/end times.
      - Construct coverage arrays (15-minute blocks) for each shift,
        including break removal.
      - Expand tasks to day-specific entries with earliest/latest blocks.
      - Record shift start blocks for handover logic.
      - Store a task_map that links day-specific tasks back to their original row index + day index.
    """

    def __init__(self, shifts_df: pd.DataFrame, tasks_df: pd.DataFrame):
        """Constructor. Expects raw DataFrames for shifts and tasks.

        Args:
            shifts_df (pd.DataFrame): The shifts DataFrame with columns such as
              'name', 'start', 'end', 'break', 'break_duration', 'max_nurses',
              'weight', plus boolean columns for each weekday ('monday'..'sunday').
            tasks_df (pd.DataFrame): The tasks DataFrame with columns such as
              'task', 'start', 'end', 'duration_min', 'nurses_required',
              plus weekday columns.
        """
        self.shifts_df = shifts_df.copy()
        self.tasks_df = tasks_df.copy()

        # After calling self.process_data(), these will be populated:
        self.shift_info = []
        self.shift_start_blocks = {}
        self.tasks_info = []
        self.task_map = []   # <--- store (original_task_idx, day_index)

    def _compute_start_end_minutes(self, day_index: int, start_str: str, end_str: str):
        """Compute absolute (start_min, end_min) for a given day_index and times.

        Args:
            day_index (int): 0 (Monday) up to 6 (Sunday).
            start_str (str): e.g. '08:00', '23:45'
            end_str (str): e.g. '17:00', '01:30'

        Returns:
            tuple (start_min, end_min):
                Absolute minutes in [0..10080). If end < start, we add 24h.
        """
        day_offset = day_index * 1440  # each day has 1440 min

        s_h, s_m = map(int, start_str.split(':'))
        start_min = day_offset + s_h * 60 + s_m

        e_h, e_m = map(int, end_str.split(':'))
        end_min = day_offset + e_h * 60 + e_m

        if end_min < start_min:
            # crosses midnight
            end_min += 24 * 60

        return start_min, end_min

    def process_data(self):
        """Perform the full preprocessing of shifts and tasks.

        Populates:
          - self.shift_info: list of dicts for each shift with coverage array, weight, etc.
          - self.shift_start_blocks: block -> list of shift indices for handover logic.
          - self.tasks_info: list of day-specific tasks with earliest/latest blocks, etc.
          - self.task_map: paralleling self.tasks_info, storing (original_idx, day_idx).
        """
        self._process_shifts()
        self._process_tasks()

    def _process_shifts(self):
        """Build coverage arrays for each shift and record where each shift starts."""
        import math
        from collections import defaultdict

        self.shift_start_blocks = defaultdict(list)
        day_cols = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]

        for idx, row in self.shifts_df.iterrows():
            shift_name   = row["name"]
            max_nurses   = int(row["max_nurses"])
            start_str    = row["start"]
            end_str      = row["end"]
            brk_str      = row["break"]
            brk_dur      = int(row["break_duration"])
            raw_weight   = float(row["weight"])

            coverage_arr = [0]*N_BLOCKS
            day_flags = [int(row[d]) for d in day_cols]

            for day_index, active in enumerate(day_flags):
                if not active:
                    continue

                # compute shift's start & end in absolute minutes
                start_min, end_min = self._compute_start_end_minutes(
                    day_index, start_str, end_str
                )

                # compute break interval
                bh, bm = map(int, brk_str.split(':'))
                break_start = day_index * 1440 + bh*60 + bm
                if break_start < start_min:
                    break_start += 24 * 60
                break_end = break_start + brk_dur

                # apply coverage
                add_coverage_blocks(coverage_arr, start_min, end_min)
                remove_coverage_blocks(coverage_arr, break_start, break_end)

                # record shift start block
                s_block = minute_to_block(start_min)
                self.shift_start_blocks[s_block].append(idx)

            weight_scaled = int(round(raw_weight * 100))
            length_blocks = sum(coverage_arr)

            # store shift info
            self.shift_info.append({
                "name": shift_name,
                "coverage": coverage_arr,
                "weight_scaled": weight_scaled,
                "length_blocks": length_blocks,
                "max_nurses": max_nurses
            })

    def _process_tasks(self):
        """Expand tasks to day-specific entries, computing earliest/latest blocks."""
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

                start_min, end_min = self._compute_start_end_minutes(day_index, start_str, end_str)
                earliest_block = start_min // TIME_GRAN
                latest_block   = end_min // TIME_GRAN
                # wrap if crossing Sunday->Monday
                latest_block %= N_BLOCKS

                duration_blocks = duration // TIME_GRAN

                self.tasks_info.append({
                    "task_name": task_name,
                    "earliest_block": earliest_block,
                    "latest_block": latest_block,
                    "duration_blocks": duration_blocks,
                    "required_nurses": required
                })
                self.task_map.append((idx, day_index))

    def get_shift_info(self):
        """Get the preprocessed shift info.

        Returns:
            list: Each element is a dict with keys:
                'name', 'coverage', 'weight_scaled', 'length_blocks', 'max_nurses'.
        """
        return self.shift_info

    def get_shift_start_blocks(self):
        """Get the dictionary of shift start blocks for handover logic.

        Returns:
            dict: block_index -> list of shift indices that begin at that block.
        """
        return self.shift_start_blocks

    def get_tasks_info(self):
        """Get the day-specific tasks info.

        Returns:
            list of dict: Each dict has keys:
                'task_name', 'earliest_block', 'latest_block',
                'duration_blocks', 'required_nurses'.
        """
        return self.tasks_info

    def get_task_map(self):
        """Get the (original_task_idx, day_index) mapping for each tasks_info entry.

        Returns:
            list of tuples: For each entry in self.tasks_info, a tuple (row_idx, day_idx).
        """
        return self.task_map
