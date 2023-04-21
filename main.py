import datetime
import math
import os
import random
import itertools
import matplotlib.pyplot as plt
import pygame

pygame.init()
screen = pygame.display.set_mode((1900, 1000))
# screen = pygame.Surface((1400, 750), pygame.SRCALPHA)
pygame.display.set_caption("Evolution Sim")



# Colors
white = [255, 255, 255]
black = (0, 0, 0)
green = (124, 252, 184)
red = (255, 150, 150)
blue = (150, 255, 150)
sea = (194, 252, 250)

# Set the size and position of the barrier rectangle
barrier_rect = pygame.Rect(700, 00, 15, 700)

# Variabele range instellen
n_lifeforms = 100  # number of life forms
n_vegetation = 100  # number of vegetation
n_dna_profiles = 10  # number of dna profiles
max_lifeforms = 150  # max number of life forms
mutation_chance = 5  # ?% chance of mutation
reproducing_cooldown_value = 80

dna_change_threshold = 0.1  # Change the DNA ID if the DNA has changed more than 50% from the original initialization
color_change_threshold = 0.1

max_width = 20
min_width = 8

max_height = 20
min_height = 8

min_maturity = 100
max_maturity = 500

vision_min = 10
vision_max = 80

degrade_tipping = 3000

spawn_range = 50

lifeform_id_counter = 0

background = white

# Lege lijst voor levensvorm-objecten
lifeforms = []
pheromones = []
dna_profiles = []
plants = []

dna_id_counts = {}


death_ages = []
death_age_avg = 0

total_health = 0
total_vision = 0
total_gen = 0
total_hunger = 0
total_size = 0
total_age = 0
total_maturity = 0
total_speed = 0
total_cooldown = 0

total_spawned_lifeforms = 0

start_time = datetime.datetime.now()
total_time = 0

# Set the frame rate to ? FPS
fps = 30

# Create a clock object
clock = pygame.time.Clock()


starting_screen = True
paused = True
show_debug = False
show_leader = False
show_action = False
show_vision = False
show_dna_id = True
show_dna_info = False

########################################################################################################################

# Klasse voor levensvorm-objecten




class Lifeform:
    def __init__(self, x, y, dna_profile, generation):
        global lifeform_id_counter

        self.x = x
        self.y = y
        self.x_direction = 0
        self.y_direction = 0

        self.dna_id = dna_profile['dna_id']
        self.width = dna_profile['width']
        self.height = dna_profile['height']
        self.color = dna_profile['color']
        self.health = dna_profile['health']
        self.maturity = dna_profile['maturity']
        self.vision = dna_profile['vision']
        self.energy = dna_profile['energy']
        self.longevity = dna_profile['longevity']
        self.generation = generation

        self.initial_height = self.height
        self.initial_width = self.width

        self.id = str(self.dna_id) + "_" + str(lifeform_id_counter)
        lifeform_id_counter += 1

        self.dna_id_count = 0

        self.size = 0
        self.speed = 0
        self.angle = 0
        self.angular_velocity = 0.1

        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

        self.defence_power = dna_profile['defence_power']
        self.attack_power = dna_profile['attack_power']

        self.attack_power_now = self.attack_power
        self.defence_power_now = self.defence_power

        self.age = 0
        self.hunger = 0
        self.wounded = 0
        self.health_now = self.health
        self.energy_now = self.energy

        self.reproduced = 0
        self.reproduced_cooldown = reproducing_cooldown_value

        self.closest_prey = None
        self.closest_enemy = None
        self.closest_partner = None
        self.closest_follower = None
        self.closest_plant = None

        self.follow_range = 30

        self.is_leader = False

        self.search = False
        self.in_group = False

    def movement(self):
        # Determine the direction in which the Lifeform object should move
        self.x += self.x_direction * self.speed
        self.y += self.y_direction * self.speed

        if self.closest_enemy:
            print("closest_enemy " + str(self.closest_enemy.id) + " own number: " + str(self.id))
        if self.closest_prey:
            print("closest_prey " + str(self.closest_prey.id) + " own number: " + str(self.id))
        if self.closest_partner:
            print("closest_partner " + str(self.closest_partner.id) + " own number: " + str(self.id))

        # Check if the object has reached the edges of the screen
        if self.x < 0:
            self.x = 0
            self.x_direction = -self.x_direction  # Reverse the direction of movement along the x-axis
        elif self.x + self.width > screen.get_width():
            self.x = screen.get_width() - self.width
            self.x_direction = -self.x_direction  # Reverse the direction of movement along the x-axis

        if self.y < 0:
            self.y = 0
            self.y_direction = -self.y_direction  # Reverse the direction of movement along the y-axis
        elif self.y + self.height > screen.get_height():
            self.y = screen.get_height() - self.height
            self.y_direction = -self.y_direction  # Reverse the direction of movement along the y-axis

        # Iterate over all lifeform objects in the lifeforms list
        for lifeform in lifeforms:
            if self.distance_to(lifeform) < self.vision and lifeform != self:
                # Update closest enemy if necessary
                if self.size < lifeform.size and self.dna_id != lifeform.dna_id and (
                    self.closest_enemy is None or self.distance_to(lifeform) < self.distance_to(self.closest_enemy)):
                        self.closest_enemy = lifeform
                        print("enemy is set " + str(self.id))
                        print("closest_enemy after set " + str(self.closest_enemy.id) + " own number: " + str(self.id))
                        self.search = False

                # Update closest prey if necessary
                elif self.size >= lifeform.size and self.dna_id != lifeform.dna_id and (
                        self.closest_prey is None or self.distance_to(lifeform) < self.distance_to(self.closest_prey)):
                    self.closest_prey = lifeform
                    print("prey is set " + str(self.id))
                    self.search = False

                # Update closest partner if necessary
                elif lifeform.maturity < lifeform.age and \
                    self.maturity < self.age and \
                    lifeform.dna_id == self.dna_id and \
                    lifeform.health_now > 50 and \
                    (self.closest_partner is None or self.distance_to(lifeform) < self.distance_to(self.closest_partner)):
                    self.closest_partner = lifeform
                    print("partner is set " + str(self.id) + "own id: " + str(self.id))
                    self.search = False

                #update closest follower if necessary
                elif lifeform.dna_id == self.dna_id and lifeform.is_leader or lifeform.closest_follower:
                    self.closest_follower = lifeform

        for plant in plants:
            if self.distance_to(plant) < self.vision and self.hunger > 250:
                self.closest_plant = plant

        # Perform check if closest life forms are still within vision, otherwise reset them to none
        if self.closest_enemy and self.closest_enemy.health_now <= 1 or self.closest_enemy and self.distance_to(self.closest_enemy) > self.vision:
            print("reset enemy" + str(self.id))
            self.closest_enemy = None
        if self.closest_prey and self.closest_prey.health_now <= 1 or self.closest_prey and self.distance_to(self.closest_prey) > self.vision:
            print("reset prey" + str(self.id))
            self.closest_prey = None
        if self.closest_partner and self.closest_partner.health_now <= 1 or self.closest_partner and self.distance_to(self.closest_partner) > self.vision:
            print("reset partner" + str(self.id))
            self.closest_partner = None
        if self.closest_follower and self.closest_follower.health_now <= 20 or self.closest_follower and self.distance_to(self.closest_follower) > self.vision:
            print("reset follower" + str(self.id))
            self.closest_follower = None
        if self.closest_plant and self.closest_plant.resource <= 1 or self.closest_plant and self.distance_to(self.closest_plant) > self.vision:
            print("reset plant" + str(self.id))
            self.closest_plant = None



        # If an enemy object was found, move away from it
        if self.closest_enemy and not self.in_group:
            print("going from enemy " + str(self.id))
            x_diff = self.closest_enemy.x - self.x
            y_diff = self.closest_enemy.y - self.y
            if x_diff == 0 and y_diff == 0:
                self.x_direction = 0
                self.y_direction = 0
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance
                #
                # total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                # target_angle = math.atan2(y_diff, x_diff)
                #
                # angle_diff = target_angle - self.angle
                # angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi
                #
                # if abs(angle_diff) > self.angular_velocity:
                #     angle_diff = math.copysign(self.angular_velocity, angle_diff)
                #
                # self.angle += angle_diff
                # self.x_direction = -math.cos(self.angle)
                # self.y_direction = -math.sin(self.angle)

        if self.closest_enemy and self.distance_to(self.closest_enemy) < 3:
            if self.in_group and self.hunger > 250:
                attack = self.attack_power_now
                self.health_now += attack
                self.closest_enemy.health_now -= self.defence_power_now
                self.energy_now -= 2
                self.hunger -= 25
                print("defended!!.. " + str(self.id))
            else:
                attack = self.closest_enemy.attack_power_now - (0.2 * self.defence_power_now)
                self.energy_now -= 10
                self.health_now -= attack
                self.wounded += 25
                print("ouch.. " + str(self.id))

        if self.closest_enemy and self.in_group:
            print("going to enemy because in group " + str(self.id))
            x_diff = self.closest_enemy.x - self.x
            y_diff = self.closest_enemy.y - self.y
            if x_diff == 0 and y_diff == 0:
                self.x_direction = 0
                self.y_direction = 0
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance
        else:
            if random.randint(0, 100) < 5:
                self.x_direction = random.uniform(-1, 1)
                self.y_direction = random.uniform(-1, 1)


        # If a prey object was found, move towards it
        if self.closest_prey and not self.closest_enemy and not self.closest_partner and self.hunger > 500 and self.age > self.maturity:
            print("going to prey " + str(self.id) + " " + str(self.closest_prey.id))
            x_diff = self.closest_prey.x - self.x
            y_diff = self.closest_prey.y - self.y
            if x_diff == 0 and y_diff == 0:
                self.x_direction = 0
                self.y_direction = 0
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance
        if self.closest_prey and not self.closest_enemy and self.distance_to(self.closest_prey) < 3 and self.hunger > 500:
            if not self.closest_prey.in_group:
                print("Eating prey: " + str(self.closest_prey.id) + "own id: " + str(self.id))
                self.health_now += self.attack_power_now
                self.closest_prey.health_now -= self.attack_power_now
                self.hunger -= 50
                self.energy_now += 25
            else:
                self.closest_prey.health_now -= self.defence_power_now
                self.energy_now -= 1000 / self.closest_prey.attack_power_now
                self.health_now -= 1000 / self.defence_power_now

        # If a partner object was found, move towards it and reproduce if close enough
        if self.reproduced_cooldown == 0 and not self.closest_enemy and self.closest_partner and self.hunger < 500 and self.age > self.maturity:
            print("going to partner " + str(self.id) + " " + str(self.closest_partner.id))
            x_diff = self.closest_partner.x - self.x
            y_diff = self.closest_partner.y - self.y
            if len(lifeforms) < max_lifeforms and self.distance_to(self.closest_partner) < 3:
                self.reproduce(self.closest_partner)
                self.reproduced += 1
                self.reproduced_cooldown = reproducing_cooldown_value
                self.energy_now -= 50
                self.health_now -= 50
                self.hunger += 50
                print("reproduced " + str(self.id))

            if x_diff == 0 and y_diff == 0:
                self.x_direction = 0
                self.y_direction = 0
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance

        # If a plant object was found, move towards it and eat if close enough
        if self.closest_plant and self.hunger > 250 and not self.closest_enemy and not self.closest_partner and self.closest_plant.resource > 10:
            x_diff = self.closest_plant.x - self.x
            y_diff = self.closest_plant.y - self.y
            if self.distance_to(self.closest_plant) < 3:
                print("eating plant")
                self.health_now += 50
                self.closest_plant.decrement_resource(10)
                self.hunger -= 50
                self.energy_now += 25
            if x_diff == 0 and y_diff == 0:
                self.x_direction = 0
                self.y_direction = 0
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance


        # If there is no target nearby, start searching
        if not self.search and not self.closest_enemy and not self.closest_prey and not self.closest_partner and not self.closest_plant:
                print("searching.... " + str(self.id))
                self.x_direction = random.uniform(-1, 1)
                self.y_direction = random.uniform(-1, 1)
                self.search = True

        if self.search:
            if self.closest_follower and not self.is_leader and self.closest_follower.closest_follower != self and self.hunger < 500:
                x_diff = self.closest_follower.x - self.x
                y_diff = self.closest_follower.y - self.y
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                if total_distance > 0:
                    if total_distance > self.follow_range:  # Check if the distance is outside of the follow range
                        self.x_direction = x_diff / total_distance
                        self.y_direction = y_diff / total_distance
                    else:  # If the distance is within the follow range, adjust the direction to move away from the leader
                        self.x_direction = -x_diff / total_distance
                        self.y_direction = -y_diff / total_distance
                else:
                    self.x_direction = random.uniform(-1, 1)
                    self.y_direction = random.uniform(-1, 1)



            elif random.randint(0, 100) < 25:
                self.x_direction = random.uniform(-1, 1)
                self.y_direction = random.uniform(-1, 1)
                # self.x_direction = (self.x_direction + random.uniform(-0.1, 0.1))
                # self.y_direction = (self.y_direction + random.uniform(-0.1, 0.1))

            print("self.search = " + str(self.search) + str(self.id))

    def add_tail(self):
        # add a pheromone trail
        pheromone = Pheromone(self.x, self.y, self.width, self.height, self.color, 100)
        pheromones.append(pheromone)


    def distance_to(self, other):
        # Calculate the distance between two Lifeform objects
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx ** 2 + dy ** 2)


    def set_size(self):
        self.size = self.width * self.height
        if self.width < 1:
            self.width = 1
        if self.height < 1:
            self.height = 1

    def check_group(self):
        group_count = 0
        for lifeform in lifeforms:
            if lifeform.dna_id == self.dna_id and self.distance_to(lifeform) < self.vision:
                group_count += 1
        if group_count >= 5:
            self.in_group = True
        else:
            self.in_group = False

    def set_speed(self):
        global average_maturity
        # Calculate the speed based on the size of the Lifeform object
        self.speed = 6 - (self.hunger / 500) - (self.age / 1000) - (self.size / 250) - (self.wounded / 20)
        self.speed += (self.health_now / 200)
        self.speed += (self.energy / 100)


        if self.age < self.maturity:
            average_maturity = total_maturity / len(lifeforms)
            if average_maturity != 0:
                factor = self.maturity / average_maturity
                self.speed *= (factor / 10)

        # Constrain the speed value to a certain range
        if self.speed < 1:
            self.speed = 1

        if self.speed > 10:
            self.speed = 10

    def draw(self, surface):
        if self.health_now > 0:
            if show_vision:
                pygame.draw.circle(surface, green, (self.x, self.y), self.vision, 1)

            # pygame.draw.rect(surface, self.color, (self.x, self.y, self.width, self.height))
            # Create a copy of the rect surface to rotate
            rect = pygame.Surface((self.width, self.height))
            rect.set_colorkey(black)
            rect.fill(self.color)
            rect_rotated = pygame.transform.rotate(rect, self.angle)
            rect.get_rect()
            surface.blit(rect_rotated, (self.x, self.y))

            # Create a separate surface for the outline
            outline_copy = pygame.Surface((self.width + 4, self.height + 4))
            outline_copy.set_colorkey(black)
            red_value = int(self.attack_power_now * 2.55)
            blue_value = int(self.defence_power_now * 2.55)
            color = pygame.Color(red_value, 0, blue_value)
            pygame.draw.rect(outline_copy, color, (0, 0, self.width + 2, self.height + 2), 1)
            outline_copy = pygame.transform.rotate(outline_copy, self.angle)
            surface.blit(outline_copy, (self.x, self.y))


            # pygame.draw.rect(surface, color, (self.x, self.y, self.width + 2, self.height + 2), 2)


        else:
            lifeforms.remove(self)
            death_ages.append(self.age)

    def update_angle(self):
        self.angle = math.degrees(math.atan2(self.y_direction, self.x_direction))

    def calculate_age_factor(self):
        age_factor = 1
        if self.age > self.longevity:
            age_factor = age_factor * 0.9 ** (self.age - self.longevity)
        return age_factor

    def calculate_attack_power(self):
        self.attack_power_now = self.attack_power * (self.energy_now / 100)
        self.attack_power_now -= self.attack_power * (self.wounded / 100)
        self.attack_power_now += (self.size - 50) * 0.8
        self.attack_power_now -= (self.hunger * 0.1)
        self.attack_power_now *= self.calculate_age_factor()

        if self.attack_power_now < 1:
            self.attack_power_now = 1
        if self.attack_power_now > 100:
            self.attack_power_now = 100

    def calculate_defence_power(self):
        self.defence_power_now = self.defence_power * (self.energy_now / 100)
        self.defence_power_now -= self.defence_power * (self.wounded /100)
        self.defence_power_now += (self.size - 50) * 0.8
        self.defence_power_now -= (self.hunger * 0.1)
        self.defence_power_now *= self.calculate_age_factor()

        if self.defence_power_now < 1:
            self.defence_power_now = 1
        if self.defence_power_now > 100:
            self.defence_power_now = 100

    def grow(self):
        if self.age < self.maturity:
            factor = self.age / self.maturity
            self.height = self.initial_height * factor
            self.width = self.initial_width * factor

    def reproduce(self, partner):
        # Create a new DNA profile by mixing the attributes of the two parent Lifeform objects
        child_dna_profile = {
                'dna_id': self.dna_id,  # Assign a new ID to the child Lifeform object
                'width': (self.width + partner.width) // 2,  # Average the width of the two parent Lifeform objects
                'height': (self.height + partner.height) // 2,  # Average the height of the two parent Lifeform objects
                'color': ((self.color[0] + partner.color[0]) // 2, (self.color[1] + partner.color[1]) // 2, (self.color[2] + partner.color[2]) // 2),
                # Mix the colors of the two parent Lifeform objects
                'health': (self.health + partner.health) // 2,  # Average the health of the two parent Lifeform objects
                'maturity': (self.maturity + partner.maturity) // 2,
                    # Average the maturity of the two parent Lifeform objects
                'vision': (self.vision + partner.vision) // 2,  # Average the vision of the two parent Lifeform objects
                'defence_power': (self.defence_power + partner.defence_power) // 2,
                'attack_power': (self.attack_power + partner.attack_power) // 2,
                'energy': (self.energy + partner.energy) // 2,
                'longevity': (self.longevity + partner.longevity) // 2
                }

        # Check if a mutation should occur for each attribute

        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['width'] += random.randint(-10, 10)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['height'] += random.randint(-10, 10)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['color'] = (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['health'] += random.randint(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['maturity'] += random.randint(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['vision'] += random.randint(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['defence_power'] += random.randint(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['attack_power'] += random.randint(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['energy'] += random.uniform(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['longevity'] += random.randint(-250, 250)

        # check if values wont go to 0:

        if child_dna_profile['health'] < 1:
            child_dna_profile['health'] = 1
        if child_dna_profile['maturity'] < 1:
            child_dna_profile['maturity'] = 1
        if child_dna_profile['vision'] < 1:
            child_dna_profile['vision'] = 1
        if child_dna_profile['defence_power'] < 1:
            child_dna_profile['defence_power'] = 1
        if child_dna_profile['defence_power'] > 100:
            child_dna_profile['defence_power'] = 100
        if child_dna_profile['attack_power'] < 1:
            child_dna_profile['attack_power'] = 1
        if child_dna_profile['attack_power'] > 100:
            child_dna_profile['attack_power'] = 100
        if child_dna_profile['energy'] < 1:
            child_dna_profile['energy'] = 1
        if child_dna_profile['energy'] > 100:
            child_dna_profile['energy'] = 100
        if child_dna_profile['longevity'] < 1:
            child_dna_profile['longevity'] = 1

        # Calculate the percentage of DNA change from the original initialization
        dna_change = 0
        color_change = 0

        for attribute, value in child_dna_profile.items():
            print("2 self.dna_id: " + str(self.dna_id))
            original_value = 0
            dna_id_check = next((profile for profile in dna_profiles if profile["dna_id"] == self.dna_id), None)
            if dna_id_check is not None:
                print("found dna_id: " + str(dna_id_check))
                original_value = dna_id_check[attribute]
            print("original values from parent dna_id: " + str(original_value))
            if isinstance(value, tuple):  # Check if the attribute is a color tuple
                color_change = sum([abs(v - ov) for v, ov in zip(value, original_value)]) / sum(original_value)
                dna_change += sum([abs(v - ov) for v, ov in zip(value, original_value)]) / sum(original_value)
                if color_change > color_change_threshold:
                    child_dna_profile["dna_id"] = create_dna_id(parent_dna_id=self.dna_id)
                else:
                    pass
            else:
                if original_value != 0:
                    dna_change += abs(original_value - value) / original_value
                else:
                    # Handle the case where the original value is zero
                    # For example, you could skip the calculation for this attribute
                    pass
        print("dna_change: " + str(dna_change))
        dna_change /= len(child_dna_profile)  # Calculate the average DNA change
        print("dna_change after divide: " + str(dna_change))

        # Create a new Lifeform object with the mixed DNA profile

        # Change the DNA ID of the child Lifeform object if the DNA has changed more than a certain amount

        # if dna_change > dna_change_threshold:
        #
        #     child_lifeform.dna_id = len(dna_profiles)  # Assign a new DNA ID to the child Lifeform object
        #     dna_profiles.append(child_dna_profile)  # Add the new DNA profile to the dna_profiles list
        #     print("New dna_id: " + str(child_lifeform.dna_id))

        # Compare the child's DNA profile to the initial DNA profile
        if dna_change > dna_change_threshold or color_change > color_change_threshold:
            found = False
            for profile in dna_profiles:
                dna_change_between = 0
                color_change_between = 0
                for attribute, value in child_dna_profile.items():
                    original_value = profile[attribute]
                    if isinstance(value, tuple):  # Check if the attribute is a color tuple
                        dna_change_between += sum([abs(v - ov) for v, ov in zip(value, original_value)]) / sum(
                            original_value)
                        color_change_between += sum([abs(v - ov) for v, ov in zip(value, original_value)]) / sum(
                            original_value)
                    else:
                        if original_value != 0:
                            dna_change_between += abs(original_value - value) / original_value
                        else:
                            # Handle the case where the original value is zero
                            # For example, you could skip the calculation for this attribute
                            pass
                dna_change_between /= len(child_dna_profile)
                print("profile dna_id: " + str(profile["dna_id"]) + " change between value: " + str(dna_change_between) + " own child_dna_profile: " + str(child_dna_profile["dna_id"]))
                # Check if the dna_change_between is less than the threshold and the dna_id is not the parent's dna_id
                if dna_change_between < dna_change_threshold or color_change_between < color_change_threshold and profile["dna_id"] != self.dna_id:
                    print("Own dna_id " + str(self.dna_id) + "Change is within already existing dna_id: " + str(profile["dna_id"]))
                    child_dna_profile = profile
                    found = True
                    print('full profile list: ' + str([profile["dna_id"] for profile in dna_profiles]))
            if not found:
                parent_dna_id = self.dna_id
                if parent_dna_id in dna_id_counts:
                    dna_id_counts[parent_dna_id] += 1
                else:
                    dna_id_counts[parent_dna_id] = 1
                child_dna_id = create_dna_id(parent_dna_id)
                child_dna_profile["dna_id"] = child_dna_id
                dna_profiles.append(child_dna_profile)

        child_lifeform = Lifeform(self.x, self.y, child_dna_profile, (self.generation + 1))
        if random.randint(0, 100) < 10:
            child_lifeform.is_leader = True
        lifeforms.append(child_lifeform)

            # if not found:
            #     child_lifeform.dna_id = len(dna_profiles)  # Assign a new DNA ID to the child Lifeform object
            #     dna_profiles.append(child_dna_profile)  # Add the new DNA profile to the dna_profiles list
            #     print("New dna_id: " + str(child_lifeform.dna_id))

    def progression(self):
        self.hunger += 1
        self.age += 1
        self.energy_now += 0.5
        self.wounded -= 1

        if self.age > self.longevity:
            self.health_now -= 1
        if self.age > 10000:
            self.health_now -= 100

        if self.hunger > 500:
            self.health_now -= 0.1
        if self.hunger > 1000:
            self.health_now -= 1
        if self.wounded < 0:
            self.wounded = 0
        if self.energy_now < 1:
            self.energy_now = 1
        if self.energy_now > self.energy:
            self.energy_now = self.energy



########################################################################################################################


class Pheromone:
    def __init__(self, x, y, width, height, color, strength):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.strength = strength

    def draw(self):
        # Calculate the new color values based on the strength value
        r = int(self.color[0] + (255 - self.color[0]) * (255 - self.strength) / 255)
        g = int(self.color[1] + (255 - self.color[1]) * (255 - self.strength) / 255)
        b = int(self.color[2] + (255 - self.color[2]) * (255 - self.strength) / 255)
        color = (r, g, b)
        pygame.draw.rect(screen, color, (self.x, self.y, self.width, self.height))

class Vegetation:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y

        self.width = width
        self.height = height
        self.size = self.width * self.height
        self.resource = 100

    def draw(self):
        pygame.draw.rect(screen, green, (self.x, self.y, self.width, self.height))

    def set_size(self):
        # Calculate the new width and height based on the resource value
        self.width = int(self.resource / 1000 * self.size)
        self.height = int(self.resource / 1000 * self.size)

    def decrement_resource(self, amount):
        self.resource -= amount
        if self.resource < 0:
            self.resource = 0

    def regrow(self):
        self.resource += 0.1
        if self.resource > 100:
            self.resource = 100


########################################################################################################################

class Graph:
    def __init__(self):
        self.figure, self.axes = plt.subplots()
        self.dna_ids = []
        self.avg_ages = []

    def update_data(self, death_ages):
        self.axes.clear()
        self.dna_ids = []
        self.avg_ages = []
        for dna_id in death_ages:
            self.dna_ids.append(dna_id)
            self.avg_ages.append(sum(death_ages[dna_id]) / len(death_ages[dna_id]))
        self.axes.bar(self.dna_ids, self.avg_ages)
        self.axes.set_xlabel("DNA ID")
        self.axes.set_ylabel("Average Age at Death")
        self.axes.set_title("Average Age at Death by DNA ID")
        self.figure.canvas.draw()

    def draw(self, screen):
        plt.draw()
        # convert the figure to a surface
        graph_surface = pygame.surfarray.make_surface(self.figure)
        screen.blit(graph_surface, (x, y))

########################################################################################################################

def reset_list_values():
    global lifeforms
    global dna_profiles
    global pheromones
    global plants
    global death_ages

    lifeforms = []
    dna_profiles = []
    pheromones = []
    plants = []
    death_ages = []



def reset_dna_profiles():
    for i in range(n_dna_profiles):
        dna_profile = {
            'dna_id': i,
            'width': random.randint(min_width, max_width),
            'height': random.randint(min_height, max_height),
            'color': (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
            'health': random.randint(1, 200),
            'maturity': random.randint(min_maturity, max_maturity),
            'vision': random.randint(vision_min, vision_max),
            'defence_power': random.randint(1, 70),
            'attack_power': random.randint(1, 70),
            'energy': random.randint(80, 100),
            'longevity': random.randint(1000, 5000)
        }
        dna_profiles.append(dna_profile)

# # Levensvorm-objecten maken met behulp van een for-lus
# for i in range(n_lifeforms):
#     x = (random.randint(0, screen.get_width()))
#     y = (random.randint(0, screen.get_height()))
#
#     generation = 1
#
#     dna_profile = random.choice(dna_profiles)
#     id = len(lifeforms)
#
#
#     lifeform = Lifeform(x, y, id, dna_profile, generation)
#     lifeforms.append(lifeform)
#     for lifeform in lifeforms:
#         if random.randint(0, 100) < 10:
#             lifeform.leader = True
def create_dna_id(parent_dna_id):
    if parent_dna_id in dna_id_counts:
        dna_id_counts[parent_dna_id] += 1
    else:
        dna_id_counts[parent_dna_id] = 1
    return int(f"{parent_dna_id}{dna_id_counts[parent_dna_id]}")


def init_lifeforms():

    for i in range(n_lifeforms):

        dna_profile = random.choice(dna_profiles)
        generation = 1

        # Find the center point of all life forms with the same DNA profile
        center_x, center_y = 0, 0
        same_dna_count = 0
        for lifeform in lifeforms:
            if lifeform.dna_id == dna_profile['dna_id']:
                center_x += lifeform.x
                center_y += lifeform.y
                same_dna_count += 1
        if same_dna_count > 0:
            center_x /= same_dna_count
            center_y /= same_dna_count
        else:
            center_x = random.randint(0, screen.get_width())
            center_y = random.randint(0, screen.get_height())

        # Generate random x and y coordinates within a certain distance of the center point
        x = random.uniform(center_x - spawn_range, center_x + spawn_range)
        y = random.uniform(center_y - spawn_range, center_y + spawn_range)

        lifeform = Lifeform(x, y, dna_profile, generation)
        lifeforms.append(lifeform)

def init_vegetation():
    for i in range(n_vegetation):
        x = (random.randint(0, screen.get_width()))
        y = (random.randint(0, screen.get_height()))

        width = 20
        height = 20

        plant = Vegetation(x, y, width, height)
        plants.append(plant)

def count_dna_ids(lifeforms):
    dna_counts = {}
    for lifeform in lifeforms:
        dna_id = lifeform.dna_id
        if dna_id in dna_counts:
            dna_counts[dna_id] += 1
        else:
            dna_counts[dna_id] = 1
    return dna_counts


def get_attribute_value(lifeforms, dna_id, attribute):
    total_attribute_value = 0
    count = 0
    for lifeform in lifeforms:
        if lifeform.dna_id == dna_id:
            total_attribute_value += getattr(lifeform, attribute)
            count += 1
    if count:
        return total_attribute_value / count
    else:
        return None


def get_average_rect(lifeforms, dna_id):
    total_width = 0
    total_height = 0
    total_red = 0
    total_green = 0
    total_blue = 0
    count = 0
    for lifeform in lifeforms:
        if lifeform.dna_id == dna_id:
            rect = lifeform.rect
            total_width += rect.width
            total_height += rect.height
            color = rect.color
            total_red += color[0]
            total_green += color[1]
            total_blue += color[2]
            count += 1
    if count > 0:
        average_width = total_width / count
        average_height = total_height / count
        average_red = total_red / count
        average_green = total_green / count
        average_blue = total_blue / count
        average_color = (average_red, average_green, average_blue)
        return (average_width, average_height, average_color)
    else:
        return None

######################################################################################################################


reset_dna_profiles()
init_lifeforms()
init_vegetation()
graph = Graph()

running = True
starting_screen = True

########################################Start Screen###################################################################
while running:
    start_button = pygame.Rect(900, 400, 150, 50)  # Create the button rectangle
    reset_button = pygame.Rect(50, 900, 150, 50)
    show_dna_button = pygame.Rect(50, 800, 20, 20)
    show_dna_info_button = pygame.Rect(50, 780, 20, 20)

    if starting_screen:
        screen.fill(background)

        pygame.draw.rect(screen, green, start_button)  # Draw the button
        pygame.draw.rect(screen, black, start_button, 3)

        # Create the text for the button
        start_text = "Start"
        font = pygame.font.Font(None, 30)
        text_surface = font.render(start_text, True, black)
        text_rect = text_surface.get_rect()
        text_rect.center = start_button.center  # Center the text inside the button

        screen.blit(text_surface, text_rect)  # Draw the text on the screen

        pygame.display.flip()

##############################################Game running#############################################################

    if not paused:
        screen.fill(background)

        # Set fonts
        font1_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus8-Regular.ttf"
        expanded_path1 = os.path.expanduser(font1_path)
        font2_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus-Bold.ttf"
        expanded_path2 = os.path.expanduser(font2_path)

        font = pygame.font.Font(expanded_path1, 12)
        font2 = pygame.font.Font(expanded_path1, 18)
        font3 = pygame.font.Font(expanded_path2, 22)

        # Limit the loop to the specified frame rate
        clock.tick(fps)

        current_time = datetime.datetime.now()
        time_passed = current_time - start_time
        formatted_time_passed = datetime.timedelta(seconds=int(time_passed.total_seconds()))
        formatted_time_passed = str(formatted_time_passed).split(".")[0]

        if death_ages:
            death_age_avg = sum(death_ages) / len(death_ages)

        dna_count = count_dna_ids(lifeforms)


        # # update graph data
        # graph.update_data(death_ages)
        # graph.draw(screen)
        # pygame.display.flip()
        for plant in plants:
            plant.set_size()
            plant.regrow()
            plant.draw()

        for pheromone in pheromones:
            pheromone.strength -= 10
            if pheromone.strength == 0:
                pheromones.remove(pheromone)
            pheromone.draw()

        # Levensvorm-objecten tekenen met behulp van een for-lus

        for lifeform in lifeforms:

            lifeform.set_speed()
            lifeform.calculate_attack_power()
            lifeform.calculate_defence_power()
            lifeform.check_group()
            lifeform.progression()
            lifeform.movement()
            lifeform.update_angle()
            lifeform.grow()
            lifeform.set_size()
            lifeform.add_tail()
            lifeform.draw(screen)

            if len(lifeforms) > 1:
                total_health += lifeform.health_now
                average_health = total_health / len(lifeforms)
                total_vision += lifeform.vision
                average_vision = total_vision / len(lifeforms)
                total_gen += lifeform.generation
                average_gen = total_gen / len(lifeforms)
                total_hunger += lifeform.hunger
                average_hunger = total_hunger / len(lifeforms)
                total_size += lifeform.size
                average_size = total_size / len(lifeforms)
                total_age += lifeform.age
                average_age = total_age / len(lifeforms)
                total_maturity += lifeform.maturity
                average_maturity = total_maturity / len(lifeforms)
                total_speed += lifeform.speed
                average_speed = total_speed / len(lifeforms)
                total_cooldown += lifeform.reproduced_cooldown
                average_cooldown = total_cooldown / len(lifeforms)


            if show_debug:
                text = font.render(f"Health: {lifeform.health_now} ID: {lifeform.id} "
                                    f"cooldown {lifeform.reproduced_cooldown} "
                                    f"gen: {lifeform.generation} "
                                    f"dna_id {lifeform.dna_id} "
                                    # f"speed: {lifeform.speed} "
                                    f"hunger: {lifeform.hunger} "
                                    f"age: {lifeform.age} ",
                                    True,
                                    (0, 0, 0))
                screen.blit(text, (lifeform.x, lifeform.y - 30))
            if show_dna_id:
                text = font2.render(f"{lifeform.dna_id}", True, (0, 0, 0))
                screen.blit(text, (lifeform.x, lifeform.y - 10))
            if show_leader:
                if lifeform.is_leader:
                    text = font.render(f"L", True, (0, 0, 0))
                    screen.blit(text, (lifeform.x, lifeform.y - 30))
            if show_action:
                text = font.render(
                    f"Current target, enemy: {lifeform.closest_enemy.id if lifeform.closest_enemy is not None else None}"
                    f", prey: {lifeform.closest_prey.id if lifeform.closest_prey is not None else None}, partner: "
                    f"{lifeform.closest_partner.id if lifeform.closest_partner is not None else None}, is following: "
                    f"{lifeform.closest_follower.id if lifeform.closest_follower is not None else None} ", True, black)
                screen.blit(text, (lifeform.x, lifeform.y - 20))
            if lifeform.reproduced_cooldown > 0:
                lifeform.reproduced_cooldown -= 1
            if barrier_rect.colliderect(lifeform.rect):
                # If the lifeform's position intersects with the barrier rectangle, prevent it from moving any further in that direction
                lifeform.x_direction = -lifeform.x_direction
                lifeform.y_direction = -lifeform.y_direction


        # dna_ids = [dna_profile["dna_id"] for dna_profile in dna_profiles]
        # alive_dna_ids = {}
        # for lifeform in lifeforms:
        #     dna_id = lifeform.dna_id
        #     if dna_id in alive_dna_ids:
        #         alive_dna_ids[dna_id] += 1
        #     else:
        #         alive_dna_ids[dna_id] = 1


        text1 = "Number of Lifeforms: " + str(len(lifeforms))
        text2 = "Total time passed: " + formatted_time_passed
        text3 = "Average health: " + str(int(average_health))
        text4 = "Average vision: " + str(int(average_vision))
        text5 = "Average generation: " + str(int(average_gen))
        text6 = "Average hunger: " + str(int(average_hunger))
        text7 = "Average size: " + str(int(average_size))
        text8 = "Average age: " + str(int(average_age))
        text9 = "Average age of dying: " + str(int(death_age_avg))
        text10 = "Average maturity age: " + str(int(average_maturity))
        text11 = "Average speed: " + str(round(average_speed, 2))
        text12 = "Average reproduction cooldown: " + str(round(average_cooldown))
        text13 = "Total of DNA id's: " + str(len(dna_profiles))
        text14 = "Alive lifeforms: "


        # Render the text
        text_surface = font2.render(text1, True, black)
        text2_surface = font2.render(text2, True, black)
        text3_surface = font2.render(text3, True, black)
        text4_surface = font2.render(text4, True, black)
        text5_surface = font2.render(text5, True, black)
        text6_surface = font2.render(text6, True, black)
        text7_surface = font2.render(text7, True, black)
        text8_surface = font2.render(text8, True, black)
        text9_surface = font2.render(text9, True, black)
        text10_surface = font2.render(text10, True, black)
        text11_surface = font2.render(text11, True, black)
        text12_surface = font2.render(text12, True, black)
        text13_surface = font2.render(text13, True, black)
        text14_surface = font2.render(text14, True, black)



        # Get the rect of the text surface
        text_rect = text_surface.get_rect()
        text2_rect = text2_surface.get_rect()
        text3_rect = text3_surface.get_rect()
        text4_rect = text4_surface.get_rect()
        text5_rect = text5_surface.get_rect()
        text6_rect = text6_surface.get_rect()
        text7_rect = text7_surface.get_rect()
        text8_rect = text8_surface.get_rect()
        text9_rect = text9_surface.get_rect()
        text10_rect = text10_surface.get_rect()
        text11_rect = text11_surface.get_rect()
        text12_rect = text12_surface.get_rect()
        text13_rect = text13_surface.get_rect()
        text14_rect = text14_surface.get_rect()


        # Set the position of the text
        text_rect.topleft = (50, 20)
        text2_rect.topleft = (50, 40)
        text3_rect.topleft = (50, 60)
        text4_rect.topleft = (50, 80)
        text5_rect.topleft = (50, 100)
        text6_rect.topleft = (50, 120)
        text7_rect.topleft = (50, 140)
        text8_rect.topleft = (50, 160)
        text9_rect.topleft = (50, 180)
        text10_rect.topleft = (50, 200)
        text11_rect.topleft = (50, 220)
        text12_rect.topleft = (50, 240)
        text13_rect.topleft = (50, 260)
        text14_rect.topleft = (50, 280)

        # Draw the text
        screen.blit(text_surface, text_rect)
        screen.blit(text2_surface, text2_rect)
        screen.blit(text3_surface, text3_rect)
        screen.blit(text4_surface, text4_rect)
        screen.blit(text5_surface, text5_rect)
        screen.blit(text6_surface, text6_rect)
        screen.blit(text7_surface, text7_rect)
        screen.blit(text8_surface, text8_rect)
        screen.blit(text9_surface, text9_rect)
        screen.blit(text10_surface, text10_rect)
        screen.blit(text11_surface, text11_rect)
        screen.blit(text12_surface, text12_rect)
        screen.blit(text13_surface, text13_rect)
        screen.blit(text14_surface, text14_rect)

        y_offset = 300

        dna_count_sorted = sorted(dna_count.items(), key=lambda item: item[1], reverse=True)
        for dna_id, count in dna_count_sorted:
            text = font3.render("Nr. per dna_" + str(dna_id) + ": " + str(count), True, black)
            screen.blit(text, (50, y_offset))
            y_offset += 35

            if show_dna_info:
                # Get the average attribute value for the lifeforms with the current dna_id
                for attribute in ["health", "vision", "attack_power_now", "defence_power_now", "speed", "maturity", "size", "longevity", "energy"]:
                    attribute_value = get_attribute_value(lifeforms, dna_id, attribute)
                    if attribute_value is not None:
                        text = font2.render(attribute + ": " + str(round(attribute_value, 2)), True, black)
                        screen.blit(text, (50, y_offset))
                        y_offset += 20

        # Draw the barrier rectangle on the screen
        # pygame.draw.rect(screen, black, barrier_rect)

        # Draw reset button on screen
        pygame.draw.rect(screen, green, reset_button)  # Draw the button
        pygame.draw.rect(screen, black, reset_button, 3)
        pygame.draw.rect(screen, green, show_dna_button)
        pygame.draw.rect(screen, black, show_dna_button, 2)
        pygame.draw.rect(screen, green, show_dna_info_button)
        pygame.draw.rect(screen, black, show_dna_info_button, 2)


        pygame.display.flip()

        if len(lifeforms) > 1:
            total_health = 0
            health_avg = 0
            total_vision = 0
            average_vision = 0
            total_gen = 0
            average_gen = 0
            total_hunger = 0
            average_hunger = 0
            total_size = 0
            average_size = 0
            total_age = 0
            average_age = 0
            total_maturity = 0
            average_maturity = 0
            total_speed = 0
            average_speed = 0
            total_cooldown = 0
            average_cooldown = 0


    elif paused:
        # Display the pause message
        pause_text = "sim paused"
        font = pygame.font.Font(None, 20)
        text_surface = font.render(pause_text, True, black)
        text_rect = text_surface.get_rect()
        text_rect.center = (250, 250)

        screen.blit(text_surface, text_rect)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_p:
                # Toggle the paused state when the 'p' key is pressed
                if paused:
                    paused = False
                else:
                    paused = True
            elif event.key == pygame.K_n:
                x = (random.randint(0, screen.get_width()))
                y = (random.randint(0, screen.get_height()))

                generation = 1

                dna_profile = random.choice(dna_profiles)

                lifeform = Lifeform(x, y, dna_profile, generation)
                if random.randint(0, 100) < 10:
                    lifeform.is_leader = True
                lifeforms.append(lifeform)

            elif event.key == pygame.K_b:
                if not show_debug:
                    show_debug = True
                else:
                    show_debug = False
            elif event.key == pygame.K_l:
                if not show_leader:
                    show_leader = True
                else:
                    show_leader = False
            elif event.key == pygame.K_s:
                if not show_action:
                    show_action = True
                else:
                    show_action = False
            elif event.key == pygame.K_v:
                if not show_vision:
                    show_vision = True
                else:
                    show_vision = False
            elif event.key == pygame.K_d:
                if not show_dna_button:
                    show_dna_id = True
                else:
                    show_dna_id = False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if start_button.collidepoint(event.pos):
                print("start clicked")
                starting_screen = False  # Set the starting screen flag to False to start the simulation
                paused = False
            if reset_button.collidepoint(event.pos):
                reset_list_values()
                reset_dna_profiles()
                init_lifeforms()
                init_vegetation()
                starting_screen = True
                paused = True
            if show_dna_button.collidepoint(event.pos):
                print('dna_button clicked')
                if not show_dna_id:
                    show_dna_id = True
                else:
                    show_dna_id = False
            if show_dna_info_button.collidepoint(event.pos):
                if not show_dna_info:
                    show_dna_info = True
                else:
                    show_dna_info = False


pygame.quit()
