import random
from datetime import datetime, timedelta
from input_parser import InputParser
import pandas as pd

class GeneticNurseScheduler:

    def __init__(self, shifts_df, tasks_df):
        self.shifts_df = shifts_df
        self.tasks_df = tasks_df

    def parse_time(self, time_str):
        """Convert time string (e.g., '8:00') to a datetime.time object."""
        return datetime.strptime(time_str, '%H:%M').time()

    def parse_duration(self, duration):
        """Convert duration in minutes to a timedelta object."""
        return timedelta(minutes=int(duration))

    def time_difference_minutes(self, time1, time2):
        """Calculate the difference in minutes between two time objects."""
        delta = datetime.combine(datetime.min, time2) - datetime.combine(datetime.min, time1)
        return delta.total_seconds() / 60

    def generate_individual(self, tasks, shifts):
            """Generate a random individual schedule."""
            individual = {}
            for task_id, task in tasks.iterrows():
                valid_shifts = [shift_id for shift_id, shift in shifts.iterrows() if self.is_valid_assignment(task, shift)]
                if valid_shifts:
                    individual[task_id] = random.choice(valid_shifts)
                else:
                    individual[task_id] = None  # No valid assignment
            return individual
    
    def is_valid_assignment(self, task, shift):
        """Check if a task can be assigned to a shift."""
        task_start = self.parse_time(task['start'])
        task_end = self.parse_time(task['end'])
        task_duration = self.parse_duration(task['duration_min'])
        task_days = task[['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']].to_numpy()

        shift_start = self.parse_time(shift['start'])
        shift_end = self.parse_time(shift['end'])
        if shift_end == datetime.strptime('00:00', '%H:%M').time():
            shift_end = datetime.strptime('23:59', '%H:%M').time()  # Treat midnight as the end of the same day

        shift_break = self.parse_time(shift['break']) if pd.notna(shift['break']) else None
        break_duration = shift['break_duration']
        shift_days = shift[['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']].to_numpy()

        # Ensure time compatibility with 30-min overlap for handover
        handover_buffer = timedelta(minutes=30)
        time_valid = (
            task_start >= (datetime.combine(datetime.min, shift_start) + handover_buffer).time() and
            task_end <= (datetime.combine(datetime.min, shift_end) - handover_buffer).time() and
            self.time_difference_minutes(task_start, task_end) >= task_duration.total_seconds() / 60
        )

        # # Ensure task does not overlap with breaks
        # if shift_break:
        #     break_start = datetime.combine(datetime.min, shift_break)
        #     break_end = break_start + timedelta(minutes=break_duration)
        #     task_start_time = datetime.combine(datetime.min, task_start)
        #     task_end_time = task_start_time + task_duration

        #     if not (task_end_time <= break_start or task_start_time >= break_end):
        #         return False

        # Ensure overlapping days
        days_valid = any(task_days & shift_days)

      
        return time_valid and days_valid



    def fitness(self, individual, tasks, shifts):
        """Calculate the fitness of an individual based on shift weights."""
        used_shifts = set(individual.values())
        total_cost = sum(shifts.iloc[shift_id]['weight'] for shift_id in used_shifts if shift_id is not None)
        return -total_cost  # Lower cost is better

    def mutate(self, individual, tasks, shifts, mutation_rate=0.1):
        """Mutate an individual by randomly reassigning tasks."""
        for task_id in range(len(tasks)):
            if random.random() < mutation_rate:
                valid_shifts = [shift_id for shift_id, shift in shifts.iterrows() if self.is_valid_assignment(tasks.iloc[task_id], shift)]
                if valid_shifts:
                    individual[task_id] = random.choice(valid_shifts)
        return individual

    def crossover(self, parent1, parent2):
        """Perform crossover between two parents to create an offspring."""
        offspring = {}
        for task_id in parent1:
            offspring[task_id] = parent1[task_id] if random.random() < 0.5 else parent2[task_id]
        return offspring

    def genetic_algorithm(self, tasks, shifts, population_size=50, generations=100, mutation_rate=0.1):
        """Solve the nurse scheduling problem using a genetic algorithm."""
        # Initialize population
        population = [self.generate_individual(tasks, shifts) for _ in range(population_size)]
        for generation in range(generations):
            # Evaluate fitness
            fitness_scores = [(individual, self.fitness(individual, tasks, shifts)) for individual in population]
            fitness_scores.sort(key=lambda x: x[1], reverse=True)  # Sort by fitness

            # Selection (elitism + random selection)
            elite_count = population_size // 10
            new_population = [individual for individual, _ in fitness_scores[:elite_count]]
            while len(new_population) < population_size:
                parent1, parent2 = random.choices([ind for ind, _ in fitness_scores], k=2)
                offspring = self.crossover(parent1, parent2)
                offspring = self.mutate(offspring, tasks, shifts, mutation_rate)
                new_population.append(offspring)

            population = new_population

        # Return the best solution found
        best_individual, best_fitness = max(fitness_scores, key=lambda x: x[1])
        return best_individual, -best_fitness  # Return positive cost

if __name__ == '__main__':
    parser = InputParser()  # Create an instance
    shifts = parser.parse_input("shifts")
    tasks = parser.parse_input("tasks")

    print(shifts)
    print(tasks)
    algo = GeneticNurseScheduler(shifts, tasks)
    individual = algo.generate_individual(tasks, shifts)
    sched, cost  = algo.genetic_algorithm(tasks, shifts)

    print(individual)
    print(sched)
    print(cost)
    # print("Best Schedule:", best_schedule)
    # print("Total Cost:", total_cost)
