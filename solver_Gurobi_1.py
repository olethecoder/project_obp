from gurobipy import Model, GRB
import gurobipy as gp
from input_parser import InputParser
from Preprocess import Preprocessor

# 1) Parse input
parser = InputParser("data")
shifts_df = parser.parse_input('shifts')
tasks_df = parser.parse_input('tasks')

# 2) Preprocess data
prepped = Preprocessor(
    shifts_df, 
    tasks_df,
)


### Sets and Parameters
shifts = prepped.shift_info

tasks = prepped.tasks_info
T = range(1, 673) # Time blocks (1 to 672)
N = range(1, len(tasks)+1) # Tasks 
S = range(1,len(shifts)+1) # Shifts

M = 672 # Big M

e = {}
for j in S:
    for t in T:
        e[j,t] = shifts[j-1]['coverage'][t-1]


### Create model
model = Model("Nurse Scheduling")

### Decision Variables
s = model.addVars(N, vtype=GRB.INTEGER, name="start") # INTEGER: Starting time(/block) task i
y = model.addVars(N, T, vtype=GRB.BINARY, name="active") # BINARY: Task i active time t
x = model.addVars(T, vtype=GRB.CONTINUOUS, name="total_tasks") # (PSEUDO-)INTEGER: Total number of tasks to be covered at time t
k = model.addVars(S, vtype=GRB.INTEGER, name="shift_scheduled")# INTEGER: Number of times shift i is scheduled
n = model.addVars(T, vtype=GRB.CONTINUOUS, name="total_nurses") # (PSEUDO-)INTEGER: Total number of nurses working at time t
u = model.addVars(N,T, vtype=GRB.CONTINUOUS, name="total_needed")

### Objective Function

model.setObjective(gp.quicksum(k[j] * shifts[j-1]['weight_scaled']/100 * shifts[j-1]['length_blocks'] for j in S), GRB.MINIMIZE)

#### Constraints

# Start time within window
for i in N:
    model.addConstr(s[i] >= tasks[i-1]['earliest_block'], name=f"Start_Earliest_{i}")
    model.addConstr(s[i] <= tasks[i-1]['latest_block'], name=f"Start_Latest_{i}")

# Big-M constraints for y
for i in N:
    for t in T:
        model.addConstr(y[i, t] <= 1 - (s[i] - t) / M)
        model.addConstr(y[i, t] <= 1 - (t - (s[i] + tasks[i-1]['duration_blocks']-1)) / M)

# Task duration
for i in N:
    model.addConstr(gp.quicksum(y[i, t] for t in T) == tasks[i-1]['duration_blocks'])

# Active * required nurses
for i in N:
    for t in T:
        model.addConstr(u[i,t] == y[i,t]*tasks[i-1]["required_nurses"])

# Total number of tasks
for t in T:
    model.addConstr(x[t] >= gp.quicksum(u[i,t] for i in N))

# PSEUDO-TASK 1: always 1 person present
for t in T:
    model.addConstr(x[t] >= 1)

# # PSEUDO-TASK 2: handover at first block of each shift
# for j in S:
#     for t in T:
#         model.addConstr(h[j, t] <= 1 - (start_time[q] - t) / M)
#         model.addConstr(h[j, t] <= 1 - (t - start_time[q]) / M)

# Total shift coverage
for t in T:
    model.addConstr(n[t]== gp.quicksum(e[j,t]*k[j] for j in S))

# Every task covered:
for t in T:
    model.addConstr(n[t]>=x[t])

# Solve
model.optimize()

if model.status == GRB.OPTIMAL:
    print("\nOptimal Schedule:")
    for i in N:
        print(f"Task {i} starts at time {int(s[i].x)}")
        active_blocks = [t for t in T if y[i, t].x > 0.5]
        print(f"  Active in time blocks: {active_blocks}")
    
    # all_vars = model.getVars()
    # values = model.getAttr("X", all_vars)
    # names = model.getAttr("VarName", all_vars)

    # for name, val in zip(names, values):
    #     print(f"{name} = {val}")

else:
    print("No optimal solution found.")
