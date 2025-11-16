"""Prototype creatures assembled from :mod:`BodyGraph` templates."""

from __future__ import annotations

from dataclasses import dataclass

from ..body.body_graph import BodyGraph
from ..body.modules import catalogue_default_modules
from .controllers import FinOscillationController
from .physics_body import PhysicsBody, build_physics_body
from .vector_math import Vector2


@dataclass
class TestCreature:
    """Bundle that groups a body graph, physics data and controller."""

    name: str
    graph: BodyGraph
    physics: PhysicsBody
    controller: FinOscillationController
    __test__ = False  # prevent pytest from collecting this helper

    def step(self, dt: float) -> Vector2:
        """Advance locomotion and return the resulting thrust vector."""

        self.controller.update(dt)
        return self.controller.thrust_vector(self.physics)


def build_fin_swimmer_prototype(name: str = "fin_swimmer_prototype") -> TestCreature:
    """Assemble a simple core/head/fin creature for physics experiments."""

    modules = catalogue_default_modules()
    graph = BodyGraph("core", modules["core"])
    graph.add_module("head", modules["head"], "core", "head_socket")
    graph.add_module("fin_left", modules["fin_left"], "core", "lateral_mount_left")
    graph.add_module("fin_right", modules["fin_right"], "core", "lateral_mount_right")
    graph.add_module("thruster", modules["thruster"], "core", "ventral_core")
    physics = build_physics_body(graph)
    controller = FinOscillationController(amplitude=0.85, frequency=0.45)
    return TestCreature(name=name, graph=graph, physics=physics, controller=controller)
