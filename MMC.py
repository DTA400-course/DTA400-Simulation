import simpy
import random
import itertools

RUN_TIMES = int(input("number of times to run simulation ---> "))
THRESHOLD_PICK = int(input("threshold of cars before switching ---> "))

# Globala variabler
NUM_CARS = 600  # Totalt antal bilar som ska simuleras
GREEN_TIME_NS = 60  # Grön tid för nord-syd (sekunder)
GREEN_TIME_EW = 60  # Grön tid för öst-väst (sekunder)
RED_TIME = 2  # Rödljus tid (sekunder)
ARRIVAL_MEAN = 1  # Genomsnittlig ankomsttid mellan bilar (sekunder)
SIMULATION_TIME = 600  # Total simuleringstid (sekunder)
DRIVE_TIME = 0.5  # Tiden det tar för en bil att köra genom korsningen (sekunder)
QUEUE_THRESHOLD = THRESHOLD_PICK  # Tröskel för att växla grönljus
INITIAL_CARS = 1  # Antal initiala bilar


# Bilnumrering med itertools
car_id_counter = itertools.count(1)

class TrafficLight:
    def __init__(self, env):
        self.env = env
        self.current_state = 'NS'  # Starta med grön ljus för nord-syd
        self.queue_north = []  # Kö för nord
        self.queue_east = []   # Kö för öst
        self.queue_south = []  # Kö för syd
        self.queue_west = []   # Kö för väst

        # Starta trafikljuset som grönt för NS
        self.env.process(self.green_light_duration(GREEN_TIME_NS))

    def run(self):
        while True:
            # Kontrollera köer och växla ljus vid behov
            self.check_queues()

            # Vänta en sekund innan nästa cykel
            yield self.env.timeout(1)

    def check_queues(self):
        # Växla ljus om någon kö når tröskeln
        if (len(self.queue_north) >= QUEUE_THRESHOLD or len(self.queue_south) >= QUEUE_THRESHOLD) and self.current_state != 'NS':
            self.switch_to_ns()
        elif (len(self.queue_east) >= QUEUE_THRESHOLD or len(self.queue_west) >= QUEUE_THRESHOLD) and self.current_state != 'EW':
            self.switch_to_ew()

    def switch_to_ns(self):
        self.current_state = 'NS'
        self.env.process(self.green_light_duration(GREEN_TIME_NS))

    def switch_to_ew(self):
        self.current_state = 'EW'
        self.env.process(self.green_light_duration(GREEN_TIME_EW))

    def green_light_duration(self, duration):
        yield self.env.timeout(duration)
        yield self.env.timeout(RED_TIME)  # Röd ljus tid

class Car:
    def __init__(self, env, car_id, traffic_light, direction, stats, road):
        self.env = env
        self.car_id = car_id  # Unik identifierare för bilen
        self.traffic_light = traffic_light
        self.direction = direction
        self.wait_time = 0
        self.queue_time = 0  # Tid i kön
        self.stats = stats  # Referens till statistikobjektet
        self.arrival_time = None  # Ankomsttid
        self.departure_time = None  # Avgångstid
        self.road = road  # Referens till vägen

    def drive(self):
        self.arrival_time = self.env.now  # Registrera ankomsttid
        yield self.env.timeout(0.5)  # Ingen väntan för de första bilarna

        # Vänta på trafikljuset och lägg till bilen i rätt kö
        if self.direction == 'NORTH':
            self.traffic_light.queue_north.append(self)  # Lägg till bilen i nord-kön

            # Kolla om bilen ska passera
            while self.traffic_light.current_state != 'NS':
                yield self.env.timeout(1)  # Vänta på grönt ljus
            yield self.env.process(self.cross_intersection())

        elif self.direction == 'EAST':
            self.traffic_light.queue_east.append(self)  # Lägg till bilen i öst-kön

            while self.traffic_light.current_state != 'EW':
                yield self.env.timeout(1)
            yield self.env.process(self.cross_intersection())

        elif self.direction == 'SOUTH':
            self.traffic_light.queue_south.append(self)  # Lägg till bilen i syd-kön

            while self.traffic_light.current_state != 'NS':
                yield self.env.timeout(1)
            yield self.env.process(self.cross_intersection())

        elif self.direction == 'WEST':
            self.traffic_light.queue_west.append(self)  # Lägg till bilen i väst-kön

            while self.traffic_light.current_state != 'EW':
                yield self.env.timeout(1)
            yield self.env.process(self.cross_intersection())

    def cross_intersection(self):
        # Väntar på vägen innan den passerar korsningen
        with self.road.request() as request:
            yield request  # Vänta på att vägen är tillgänglig
            yield self.env.timeout(DRIVE_TIME)  # Tid för att köra genom korsningen

        # Registrera avgångstid och kötid
        self.departure_time = self.env.now  # Registrera avgångstid
        self.queue_time = self.departure_time - self.arrival_time  # Total kötid
        self.wait_time = self.queue_time + DRIVE_TIME  # Total väntetid (inklusiv kötid och körtid)

        # Ta bort bilen från kön
        if self.direction == 'NORTH':
            self.traffic_light.queue_north.remove(self)
        elif self.direction == 'EAST':
            self.traffic_light.queue_east.remove(self)
        elif self.direction == 'SOUTH':
            self.traffic_light.queue_south.remove(self)
        elif self.direction == 'WEST':
            self.traffic_light.queue_west.remove(self)

        # Spara väntetid och kötid i statistik
        self.stats['total_wait_time'] += self.wait_time
        self.stats['queue_times'].append(self.queue_time)
        self.stats['car_count'] += 1  # Öka antalet bilar


# Setup-process för att skapa bilar och trafikljus
def setup(env, initial_cars, arrival_mean):
    global stats
    traffic_light = TrafficLight(env)
    road = simpy.Resource(env, capacity=2)  # Vägen kan bara ta en bil åt gången
    env.process(traffic_light.run())  # Starta trafikljusets process

    # Statistik för väntetider
    stats = {
        'total_wait_time': 0,
        'car_count': 0,
        'wait_times': [],  # Lista för att lagra väntetider
        'queue_times': []   # Lista för att lagra kötid
    }

    # Skapa initiala bilar
    car_count = itertools.count()  # Täljare för bil-ID
    for _ in range(initial_cars):
        env.process(Car(env, f'Car {next(car_count)}', traffic_light, 'NORTH', stats, road).drive())

    # Skapa bilar under simulationstiden
    while True:
        yield env.timeout(random.expovariate(1.0 / arrival_mean))
        env.process(Car(env, f'Car {next(car_count)}', traffic_light, random.choice(['NORTH', 'EAST', 'SOUTH', 'WEST']), stats, road).drive())


# Kör simuleringen 15 gånger och skriv ut resultaten för varje körning
for i in range(RUN_TIMES):
    print(f"\n--- Simulering {i + 1} ---")
    env = simpy.Environment()
    env.process(setup(env, INITIAL_CARS, ARRIVAL_MEAN))
    env.run(until=SIMULATION_TIME)

    # Beräkna och skriv ut medelväntetid och medelkötid
    if stats['car_count'] > 0:
        average_wait_time = stats['total_wait_time'] / stats['car_count']
        average_queue_time = sum(stats['queue_times']) / len(stats['queue_times']) if stats['queue_times'] else 0
        print(f'Medelväntetid: {average_wait_time:.2f} sekunder')
        print(f'Medelkötid: {average_queue_time:.2f} sekunder')
    else:
        print("Inga bilar passerade korsningen.")
