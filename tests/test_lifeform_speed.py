"""Regression tests for Lifeform.set_speed heuristics."""

import types

import pygame
import pytest

from evolution.entities.lifeform import Lifeform
from evolution.config import settings
from evolution.world.world import BiomeRegion


class DummyState:
    def __init__(self, movement=1.0, plant_modifier=1.0):
        self.lifeforms = []
        self.plants = [] if plant_modifier == 1.0 else [types.SimpleNamespace(resource=10, contains_point=lambda *_: True, movement_modifier_for=lambda *_: plant_modifier)]
        self.carcasses = []
        self.death_ages = []
        self.environment_modifiers = {"hunger_rate": 1.0}
        self.lifeform_id_counter = 0
        rect = pygame.Rect(0, 0, settings.WORLD_WIDTH, settings.WORLD_HEIGHT)
        weather = types.SimpleNamespace(
            name="Stabiel",
            movement_modifier=1.0,
            hunger_modifier=1.0,
            regrowth_modifier=1.0,
            energy_modifier=1.0,
            health_tick=0.0,
            temperature=20,
            precipitation="helder",
        )
        biome = BiomeRegion(
            name="Test",
            rect=rect,
            color=(20, 30, 40),
            weather_patterns=[weather],
        )
        biome.active_weather = weather
        self.world = types.SimpleNamespace(
            get_environment_context=lambda *_: (
                biome,
                {
                    "movement": movement,
                    "hunger": 1.0,
                    "regrowth": 1.0,
                    "energy": 1.0,
                    "health": 0.0,
                    "temperature": 20.0,
                    "precipitation": "helder",
                    "weather_name": "Stabiel",
                    "light": 1.0,
                    "pressure": 1.0,
                    "fluid_density": 1.0,
                    "current_speed": 0.0,
                },
            )
        )
        self.player = None


@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    yield
    try:
        pygame.display.quit()
    except pygame.error:
        pass


def build_lifeform(age, hunger, mass=2.5, speed_multiplier=1.0, movement=1.0):
    state = DummyState(movement=movement)
    dna_profile = {
        "dna_id": 1,
        "color": (120, 150, 200),
        "maturity": 100,
        "longevity": 800,
        "geometry": {"width": 10, "height": 4},
    }
    lf = Lifeform(state, 0.0, 0.0, dna_profile, generation=1)
    lf.age = age
    lf.hunger = hunger
    lf.mass = mass
    lf.speed_multiplier = speed_multiplier
    lf.health_now = lf.health
    lf.energy_now = lf.energy
    lf.state.lifeforms.append(lf)
    return lf


def test_adult_speed_above_floor():
    lf = build_lifeform(age=150, hunger=400)
    lf.set_speed()
    assert lf.speed > 0.6


def test_elder_speed_reduces_but_not_zero():
    lf = build_lifeform(age=600, hunger=100)
    lf.set_speed()
    assert 0.4 < lf.speed < 3.0


def test_hunger_penalty_stronger_when_starving():
    lf = build_lifeform(age=180, hunger=100)
    lf.set_speed()
    well_fed_speed = lf.speed
    lf2 = build_lifeform(age=180, hunger=600)
    lf2.set_speed()
    assert lf2.speed < well_fed_speed


def test_locomotion_multiplier_affects_speed():
    lf = build_lifeform(age=180, hunger=100, speed_multiplier=1.5, movement=1.2)
    lf.set_speed()
    assert lf.speed > 1.2
