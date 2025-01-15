from gurobipy import Model, GRB
import gurobipy as gp

### Create model
model = Model("Weekly Task Scheduling")

### Sets and Parameters
T = range(1, 673)  # Time blocks (1 to 672)
N = range(1, 5+1)  # Tasks
S = range(1,#shifts) # Number of shifts
M=672
PRICE_HOUR = 30
# a = {i: task_start[i][0] for i in N}  # Start window lower bound
# b = {i: task_start[i][1] for i in N}  # Start window upper bound
# d = {i: task_duration[i] for i in N}  # Task durations
window_start = {1: 10, 2: 20, 3: 15, 4: 5, 5: 0} # Earliest start times
window_end = {1: 18, 2: 640, 3: 650, 4: 660, 5: 668}  # Latest start times
duration = {1: 5, 2: 8, 3: 10, 4: 12, 5: 4}  # Task durations
# Task weight

### Decision Variables
s = model.addVars(N, vtype=GRB.INTEGER, name="start") # INTEGER: Starting time(/block) shift i
y = model.addVars(N, T, vtype=GRB.BINARY, name="active") # BINARY: Task i active time t
x = model.addVars(T, vtype=GRB.CONTINUOUS, name="total_tasks") # (PSEUDO-)INTEGER: Total number of tasks to be covered at time t
k = model.addVars(N, vtype=GRB.INTEGER, name="shift_scheduled")# INTEGER: Number of times shift i is scheduled
n = model.addVars(T, vtype=GRB.CONTINUOUS, name="total_nurses") # (PSEUDO-)INTEGER: Total number of nurses working at time t

### Objective Function

model.setObjective(gp.quicksum(s[i] for i in N), GRB.MINIMIZE)

#### Constraints

# Start time within window
for i in N:
    model.addConstr(s[i] >= window_start[i], name=f"Start_Earliest_{i}")
    model.addConstr(s[i] <= window_end[i], name=f"Start_Latest_{i}")

# Big-M constraints for y
for i in N:
    for t in T:
        model.addConstr(y[i, t] <= 1 - (s[i] - t) / M)
        model.addConstr(y[i, t] <= 1 - (t - (s[i] + duration[i]-1)) / M)

# Task duration
for i in N:
    model.addConstr(gp.quicksum(y[i, t] for t in T) >= duration[i])

# Total number of tasks
for t in T:
    model.addConstr(x[t] >= gp.quicksum(y[i,t] for i in N))

# PSEUDO-TASK: always 1 person present
for t in T:
    model.addConstr(x[t] >= 1)

# Total shift coverage
for t in T:
    continue
    #model.addConstr(z[t]<=)

# Every task covered:
for t in T:
    model.addConstr(z[t]>=x[t])

# Solve
model.optimize()

if model.status == GRB.OPTIMAL:
    print("\nOptimal Schedule:")
    for i in N:
        print(f"Task {i} starts at time {int(s[i].x)}")
        active_blocks = [t for t in T if y[i, t].x > 0.5]
        print(f"  Active in time blocks: {active_blocks}")
        all_vars = model.getVars()
    # values = model.getAttr("X", all_vars)
    # names = model.getAttr("VarName", all_vars)

    # for name, val in zip(names, values):
    #     print(f"{name} = {val}")

else:
    print("No optimal solution found.")
