import simpy
import random
import matplotlib.pyplot as plt

RUN_TIMES = int(input("numbers of time to run simulation ---> "))
GREEN_TIME = int(input("number of seconds for green light ---> "))

# Globala variabler
NUM_CARS = 600          
GREEN_TIME_NS = GREEN_TIME      
GREEN_TIME_EW = GREEN_TIME
RED_TIME = 2            
ARRIVAL_MEAN = 1        
SIMULATION_TIME = 600   
DRIVE_TIME = 0.5        


class TrafficLight:
    def __init__(self, env):
        self.env = env
        self.state = 'GREEN'  # Startar med rött ljus
        self.queue_ns = 0   # Kö för nord-syd
        self.queue_ew = 0   # Kö för öst-väst

    def run(self):
        while True:
            self.state = 'GREEN_NS'
            yield self.env.timeout(GREEN_TIME_NS)

            self.state = 'RED_NS'
            yield self.env.timeout(RED_TIME)

            self.state = 'GREEN_EW'
            yield self.env.timeout(GREEN_TIME_EW)

            self.state = 'RED_EW'
            yield self.env.timeout(RED_TIME)

class Road:
    def __init__(self, env, stats):
        self.env = env
        self.resource = simpy.Resource(env, capacity=1)  
        self.usage_start_time = None  
        self.stats = stats

    def drive(self, car):
        with self.resource.request() as request:
            yield request  

            yield self.env.timeout(DRIVE_TIME)

class Car:
    def __init__(self, env, name, traffic_light, road, direction, stats):
        self.env = env
        self.name = name
        self.traffic_light = traffic_light
        self.road = road
        self.direction = direction
        self.queue_time = 0  
        self.stats = stats  
        self.arrival_time = None  

    def drive(self):
        self.arrival_time = self.env.now  

        if self.direction in ['NORTH', 'SOUTH']:
            self.traffic_light.queue_ns += 1
            start_queue_time = self.env.now  
            while self.traffic_light.state != 'GREEN_NS':
                yield self.env.timeout(1)

        
            self.queue_time = self.env.now - start_queue_time
            yield from self.road.drive(self)
            self.traffic_light.queue_ns -= 1

        elif self.direction in ['EAST', 'WEST']:
            self.traffic_light.queue_ew += 1
            start_queue_time = self.env.now
            while self.traffic_light.state != 'GREEN_EW':
                yield self.env.timeout(1)

            self.queue_time = self.env.now - start_queue_time
            yield from self.road.drive(self)
            self.traffic_light.queue_ew -= 1

        self.stats['queue_times'].append(self.queue_time)
        self.stats['car_count'] += 1

def car_generator(env, traffic_light, road, stats):
    directions = ['NORTH', 'EAST', 'SOUTH', 'WEST']
    
    for i in range(NUM_CARS):
        direction = random.choice(directions)
        car = Car(env, f'Bil {i + 1}', traffic_light, road, direction, stats)
        env.process(car.drive())
        
        yield env.timeout(ARRIVAL_MEAN)

for i in range(RUN_TIMES):
    print(f"\n--- Simulering {i + 1} ---")

    stats = {
        'car_count': 0,
        'queue_times': []  
    }

    env = simpy.Environment()
    traffic_light = TrafficLight(env)
    road = Road(env, stats)
    env.process(traffic_light.run())
    env.process(car_generator(env, traffic_light, road, stats))

    env.run(until=SIMULATION_TIME)

    if stats['car_count'] > 0:
        average_queue_time = sum(stats['queue_times']) / len(stats['queue_times'])
        print(f'Antal bilar: {stats["car_count"]}')
        print(f'Medelkötid: {average_queue_time:.2f} sekunder')
    else:
        print('Inga bilar har registrerat kötid.')
