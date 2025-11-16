"""Body module definitions used to construct procedural organisms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from .attachment import AttachmentPoint, Joint, JointType


@dataclass(frozen=True)
class ModuleStats:
    """High level statistics that every module exposes."""

    mass: float
    energy_cost: float
    integrity: float
    heat_dissipation: float
    power_output: float = 0.0


@dataclass
class BodyModule:
    """Base class for every module that can appear in a ``BodyGraph``."""

    key: str
    name: str
    description: str
    size: Tuple[float, float, float]
    stats: ModuleStats
    attachment_points: Dict[str, AttachmentPoint] = field(default_factory=dict)

    module_type: str = "generic"

    def add_attachment_points(self, points: Iterable[AttachmentPoint]) -> None:
        """Register new attachment points on the module."""

        for point in points:
            if point.name in self.attachment_points:
                raise ValueError(f"Attachment point '{point.name}' already registered on {self.key}")
            self.attachment_points[point.name] = point

    def get_attachment_point(self, name: str) -> AttachmentPoint:
        """Return the attachment point with ``name``."""

        try:
            return self.attachment_points[name]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise KeyError(f"Attachment point '{name}' not defined on module '{self.key}'") from exc


@dataclass
class CoreModule(BodyModule):
    """Central torso module that anchors the rest of the body."""

    energy_capacity: float = 0.0
    cargo_slots: int = 0

    module_type: str = "core"


@dataclass
class HeadModule(BodyModule):
    """Sensory and control hub."""

    vision_bonus: float = 0.0
    cognition_bonus: float = 0.0

    module_type: str = "head"


@dataclass
class LimbModule(BodyModule):
    """Appendage used for locomotion or manipulation."""

    thrust: float = 0.0
    grip_strength: float = 0.0

    module_type: str = "limb"


@dataclass
class PropulsionModule(BodyModule):
    """Modules that provide strong directional thrust."""

    thrust_power: float = 0.0
    fuel_efficiency: float = 0.0

    module_type: str = "propulsion"


@dataclass
class SensoryModule(BodyModule):
    """Specialised sensors such as sonar or electroreceptors."""

    detection_range: float = 0.0
    spectrum: Sequence[str] = field(default_factory=tuple)

    module_type: str = "sensor"


# Convenience builders -----------------------------------------------------

def build_default_core(key: str = "core") -> CoreModule:
    """Return a lightweight default core with a few attachment points."""

    module = CoreModule(
        key=key,
        name="Core",
        description="Main torso providing power distribution",
        size=(1.2, 1.0, 1.4),
        stats=ModuleStats(mass=40.0, energy_cost=3.5, integrity=120.0, heat_dissipation=15.0, power_output=60.0),
        energy_capacity=200.0,
        cargo_slots=2,
    )
    module.add_attachment_points(
        [
            AttachmentPoint(
                name="head_socket",
                joint=Joint(JointType.FIXED),
                allowed_modules=(HeadModule,),
                description="Connection for the head module",
            ),
            AttachmentPoint(
                name="dorsal_mount",
                joint=Joint(JointType.BALL, swing_limits=(-35.0, 35.0)),
                allowed_modules=(SensoryModule,),
            ),
            AttachmentPoint(
                name="ventral_core",
                joint=Joint(JointType.HINGE, swing_limits=(-20.0, 20.0)),
                allowed_modules=(PropulsionModule, LimbModule),
            ),
            AttachmentPoint(
                name="lateral_mount_left",
                joint=Joint(JointType.MUSCLE, swing_limits=(-50.0, 50.0), torque_limit=120.0),
                allowed_modules=(LimbModule,),
            ),
            AttachmentPoint(
                name="lateral_mount_right",
                joint=Joint(JointType.MUSCLE, swing_limits=(-50.0, 50.0), torque_limit=120.0),
                allowed_modules=(LimbModule,),
            ),
        ]
    )
    return module


def build_default_head(key: str = "head") -> HeadModule:
    """Return a head module with sensory attachment points."""

    module = HeadModule(
        key=key,
        name="Cephalon",
        description="Primary sensory organ",
        size=(0.8, 0.6, 0.9),
        stats=ModuleStats(mass=10.0, energy_cost=1.2, integrity=60.0, heat_dissipation=6.0),
        vision_bonus=45.0,
        cognition_bonus=12.0,
    )
    module.add_attachment_points(
        [
            AttachmentPoint(
                name="cranial_sensor",
                joint=Joint(JointType.FIXED),
                allowed_modules=(SensoryModule,),
            )
        ]
    )
    return module


def build_default_fin(key: str) -> LimbModule:
    """Return a fin-like limb module."""

    module = LimbModule(
        key=key,
        name="Hydro Fin",
        description="Flexible fin for aquatic thrust",
        size=(1.2, 0.2, 0.6),
        stats=ModuleStats(mass=6.0, energy_cost=0.6, integrity=35.0, heat_dissipation=4.0),
        thrust=45.0,
        grip_strength=5.0,
    )
    return module


def build_default_thruster(key: str) -> PropulsionModule:
    """Return a tail thruster module."""

    module = PropulsionModule(
        key=key,
        name="Tail Thruster",
        description="Powerful axial thruster",
        size=(1.5, 0.5, 0.5),
        stats=ModuleStats(mass=12.0, energy_cost=2.5, integrity=50.0, heat_dissipation=10.0, power_output=30.0),
        thrust_power=120.0,
        fuel_efficiency=0.8,
    )
    module.add_attachment_points(
        [
            AttachmentPoint(
                name="tail_sensors",
                joint=Joint(JointType.FIXED),
                allowed_modules=(SensoryModule,),
            )
        ]
    )
    return module


def build_default_sensor(key: str, spectrum: Sequence[str]) -> SensoryModule:
    """Return a sensory module that can be attached on multiple sockets."""

    return SensoryModule(
        key=key,
        name="Sensor Pod",
        description="Specialised detection apparatus",
        size=(0.5, 0.4, 0.4),
        stats=ModuleStats(mass=2.5, energy_cost=0.4, integrity=20.0, heat_dissipation=2.5),
        detection_range=75.0,
        spectrum=tuple(spectrum),
    )


def catalogue_default_modules() -> Mapping[str, BodyModule]:
    """Return a mapping of simple module presets for prototypes/tests."""

    sensor = build_default_sensor("sensor_light", ("light", "colour"))
    sonar = build_default_sensor("sensor_sonar", ("sonar",))
    modules = {
        "core": build_default_core(),
        "head": build_default_head(),
        "fin_left": build_default_fin("fin_left"),
        "fin_right": build_default_fin("fin_right"),
        "thruster": build_default_thruster("thruster"),
        sensor.key: sensor,
        sonar.key: sonar,
    }
    return modules
