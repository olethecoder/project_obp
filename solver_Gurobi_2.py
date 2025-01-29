from gurobipy import Model, GRB
import gurobipy as gp
from input_parser import InputParser
from Preprocess2 import NurseSchedulingPreprocessor
import pandas as pd

# 1) Parse input
parser = InputParser("data")
shifts_df = parser.parse_input('shifts_hard')
tasks_df = parser.parse_input('tasks_100_rog1')
shifts_solution = shifts_df.copy()
tasks_solution = tasks_df.copy()

# 2) Preprocess data
preprocessor = NurseSchedulingPreprocessor(
    shifts_df, 
    tasks_df,
)
preprocessor.process_data()

### Sets and Parameters
shifts = preprocessor.get_shift_info()
tasks = preprocessor.get_tasks_info()
task_map = preprocessor.get_task_map()
print(shifts[0]["starting_blocks"][32])

print(tasks)

########

# from Preprocess import Preprocessor
# import pandas as pd

# # 1) Parse input
# parser = InputParser("data")
# shifts_df = parser.parse_input('shifts_hard')
# tasks_df = parser.parse_input('tasks')
# shifts_solution = shifts_df.copy()
# tasks_solution = tasks_df.copy()

# # 2) Preprocess data
# prepped = Preprocessor(
#     shifts_df, 
#     tasks_df,
# )

# ### Sets and Parameters
# shifts = prepped.shift_info
# print(shifts)
# tasks = prepped.tasks_info
# task_map = prepped.task_map

TIME_GRAN = 15

T = range(1, 673) # Time blocks (1 to 672)
N = range(1, len(tasks)+1) # Tasks 
S = range(1,len(shifts)+1) # Shifts
MIN_NURSES_PRESENT = 1

# Functions

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

# Candidate task blocks
# candidate_blocks = []
# for i in N:
#     candidate_blocks.append([])
#     for j in range(1,tasks[i-1]['latest_block']-tasks[i-1]['earliest_block']+2):
#         candidate_blocks[i-1].append([])
#         for k in range(1,tasks[i-1]['duration_blocks']+1):
#             print(j)
#             print(k)
#             candidate_blocks[i-1][j-1].append(tasks[i-1]['earliest_block']+j-1+k-1)

candidate_blocks = []
max_T = max(T)
for i in N:
    candidate_blocks.append([])
    c_idx = 0
    eb = tasks[i-1]['earliest_block']
    lb = tasks[i-1]['latest_block']
    if lb >= eb:
        for j in range(eb,lb+1):
            candidate_blocks[i-1].append([])
            for k in range(0,tasks[i-1]['duration_blocks']):
                candidate_blocks[i-1][c_idx].append(j+k)
            c_idx += 1
    else:
        for j in range(eb,max_T-1+1):
            candidate_blocks[i-1].append([])
            for k in range(0,tasks[i-1]['duration_blocks']):
                if k + j <= max_T - 1:
                    candidate_blocks[i-1][c_idx].append(j+k)
                else: candidate_blocks[i-1][c_idx].append(j+k - max_T)               
            c_idx += 1
        for j in range(0,lb+1):
            candidate_blocks[i-1].append([])
            for k in range(0,tasks[i-1]['duration_blocks']):
                candidate_blocks[i-1][c_idx].append(j+k)
            c_idx += 1


print(candidate_blocks)
# BOOLEAN: Candidate task i block j covers time block t
g = {}
for i in N:
    for j in range(1,len(candidate_blocks[i-1])+1):
        for t in T:
            if t-1 in candidate_blocks[i-1][j-1]: #########################CHECK
                g[i,j,t] = 1
            else:
                g[i,j,t] = 0


# BOOLEAN: Candidate shift/schedule j covers time block t
e = {}
for j in S:
    for t in T:
        e[j,t] = shifts[j-1]['coverage'][t-1]

# BOOLEAN: Candidate shift/schedule j has starting point at time block t
h = {}
for j in S:
    for t in T:
        h[j,t] = shifts[j-1]['starting_blocks'][t-1]

### Create model
model = Model("Nurse Scheduling")

### Decision Variables
x = model.addVars(T, vtype=GRB.INTEGER, name="total_tasks") # (PSEUDO-)INTEGER: Total number of tasks to be covered at time t
f = {}
for i in N:
    for j in range(1,len(candidate_blocks[i-1])+1):
        f[i,j] = model.addVar(0,1,0,GRB.BINARY,name="block_active")
u = model.addVars(N,T, vtype=GRB.BINARY, name="active")
r = model.addVars(T,vtype=GRB.INTEGER,name="receiving")
p = model.addVars(T,vtype=GRB.BINARY,name="providing")
k = model.addVars(S, vtype=GRB.INTEGER, name="shift_scheduled")# INTEGER: Number of times shift i is scheduled
n = model.addVars(T, vtype=GRB.INTEGER, name="total_nurses") # (PSEUDO-)INTEGER: Total number of nurses working at time t


### Objective Function

model.setObjective(gp.quicksum(k[j] * shifts[j-1]['weight_scaled']/100 * shifts[j-1]['length_blocks'] for j in S), GRB.MINIMIZE)

#### Constraints

# Each task is fulfilled
for i in N:
    model.addConstr(gp.quicksum(f[i,j] for j in range(1,len(candidate_blocks[i-1])+1)) == 1)

# Task i active at time t
for i in N: 
    for t in T:
        model.addConstr(u[i,t] >= gp.quicksum(f[i,j]*g[i,j,t] for j in range(1,len(candidate_blocks[i-1])+1)))

# PSEUDO-TASK: Total number of nurses to *receive* handover at time t
for t in T:
    model.addConstr(r[t] == gp.quicksum(k[j]*h[j,t] for j in S))

# PSEUDO-TASK: Indicator whether someone needs to *provide* handover at time t (only if arriving nurses need to receive handover)
for t in T:
    model.addConstr(p[t] >= r[t]/50)

# Required coverage at time t
for t in T:
    model.addConstr(x[t] >= gp.quicksum(u[i,t]*tasks[i-1]["required_nurses"] for i in N)+r[t]+p[t])
    # model.addConstr(x[t] >= gp.quicksum(u[i,t]*tasks[i-1]["required_nurses"] for i in N))

# Always minimum number of nurses present
for t in T:
    model.addConstr(x[t] >= MIN_NURSES_PRESENT)

# # PSEUDO-TASK 2: handover at first block of each shift
# for j in S:
#     for t in T:
#         model.addConstr(h[j, t] <= 1 - (start_time[q] - t) / M)
#         model.addConstr(h[j, t] <= 1 - (t - start_time[q]) / M)

# Total shift coverage
for t in T:
    model.addConstr(n[t] == gp.quicksum(e[j,t]*k[j] for j in S))

#######################CHECK: Combineren?

# Max number of nurses per shift
for j in S:
    model.addConstr(k[j]<= shifts[j-1]["max_nurses"])

# Every task covered:
for t in T:
    model.addConstr(n[t]>=x[t])

# Solve
#model.setParam('TimeLimit', 5)
model.optimize()

#if model.status == GRB.TIME_LIMIT:
if model.status == GRB.OPTIMAL:
    usage_values = []
    for i in S:
        val = k[i].x
        usage_values.append(int(val))
    shifts_solution["usage"] = usage_values
    print(shifts_solution)

    day_specific_records = []
    for i, tinfo in enumerate(tasks):
        
        # Extract the earliest/latest from the stored blocks
        earliest_block = tinfo["earliest_block"]
        latest_block   = tinfo["latest_block"]
        duration = tinfo["duration_blocks"]
        earliest_time_str = block_to_timestr(earliest_block)
        latest_time_str   = block_to_timestr(latest_block)
        duration = block_to_minute(duration)
        start_block = 0
        for j in range(1,tasks[i]['latest_block']-tasks[i]['earliest_block']+2):
            if f[i+1,j].x > 0: #CHECK
                start_block = tasks[i]['earliest_block']+j-1
        solution_start_str = block_to_timestr(start_block)

        orig_task_idx, day_index = task_map[i]
        day_specific_records.append({
            "original_task_idx": orig_task_idx,
            "day_index": day_index,
            "task_name": tinfo["task_name"],
            "start_window": earliest_time_str,
            "end_window": latest_time_str,
            "solution_start": solution_start_str,
            "duration": duration,
            "required_nurses": tinfo["required_nurses"]
        })

    tasks_solution = pd.DataFrame(day_specific_records)
    print(tasks_solution)


else:
    print("No optimal solution found.")


tasks_solution.to_csv("data/tasks_solution_Ole.csv", index=False)
shifts_solution.to_csv("data/shifts_solution_Ole.csv", index=False)