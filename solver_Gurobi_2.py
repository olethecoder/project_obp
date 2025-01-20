from gurobipy import Model, GRB
import gurobipy as gp
from input_parser import InputParser
from Preprocess import Preprocessor

# 1) Parse input
parser = InputParser("data")
shifts_df = parser.parse_input('shifts_hard')
tasks_df = parser.parse_input('tasks_easy')

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

# Candidate task blocks
candidate_blocks = []
for i in N:
    candidate_blocks.append([])
    for j in range(1,tasks[i-1]['latest_block']-tasks[i-1]['earliest_block']+2):
        candidate_blocks[i-1].append([])
        for k in range(1,tasks[i-1]['duration_blocks']+1):
            candidate_blocks[i-1][j-1].append(tasks[i-1]['earliest_block']+j-1+k-1)

# Candidate task i block j covers time block t
g = {}
for i in N:
    for j in range(1,len(candidate_blocks[i-1])+1):
        for t in T:
            if t in candidate_blocks[i-1][j-1]:
                g[i,j,t] = 1
            else:
                g[i,j,t] = 0

# Shift j covers time block t
e = {}
for j in S:
    for t in T:
        e[j,t] = shifts[j-1]['coverage'][t-1]


### Create model
model = Model("Nurse Scheduling")

### Decision Variables
x = model.addVars(T, vtype=GRB.CONTINUOUS, name="total_tasks") # (PSEUDO-)INTEGER: Total number of tasks to be covered at time t
f = {}
for i in N:
    for j in range(1,len(candidate_blocks[i-1])+1):
        f[i,j] = model.addVar(0,1,0,GRB.BINARY,name="block_active")
u = model.addVars(N,T, vtype=GRB.BINARY, name="active")

k = model.addVars(S, vtype=GRB.INTEGER, name="shift_scheduled")# INTEGER: Number of times shift i is scheduled
n = model.addVars(T, vtype=GRB.CONTINUOUS, name="total_nurses") # (PSEUDO-)INTEGER: Total number of nurses working at time t


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


# Total number of tasks at time t
for t in T:
    model.addConstr(x[t] >= gp.quicksum(u[i,t]*tasks[i-1]["required_nurses"] for i in N))

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
    model.addConstr(n[t]<= gp.quicksum(e[j,t]*k[j] for j in S))

# Max number of nurses per shift
for j in S:
    model.addConstr(k[j]<= shifts[j-1]["max_nurses"])

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
