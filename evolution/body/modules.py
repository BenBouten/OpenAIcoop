"""Body module definitions used to construct procedural organisms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Dict, Iterable, Mapping, Sequence, Tuple

from .attachment import AttachmentPoint, Joint, JointType


@dataclass(frozen=True)
class ModuleStats:
    """High level statistics that every module exposes."""

    mass: float
    energy_cost: float
    integrity: float
    heat_dissipation: float
    power_output: float = 0.0
    buoyancy_bias: float = 0.0


@dataclass
class BodyModule:
    """Base class for every module that can appear in a ``BodyGraph``."""

    key: str
    name: str
    description: str
    size: Tuple[float, float, float]
    stats: ModuleStats
    material: str = "biomass"
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
    lift_coefficient: float = 0.0

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


# Concrete module implementations -------------------------------------------


def _clone_attachment_points(points: Iterable[AttachmentPoint]) -> Iterable[AttachmentPoint]:
    """Return fresh ``AttachmentPoint`` instances for the provided template."""

    return [
        AttachmentPoint(
            name=point.name,
            joint=point.joint,
            allowed_modules=point.allowed_modules,
            description=point.description,
            max_child_mass=point.max_child_mass,
            allowed_materials=point.allowed_materials,
        )
        for point in points
    ]


@dataclass
class TrunkCore(CoreModule):
    """Stock torso that provides power, cargo slots and attachment sockets."""

    key: str = "core"
    name: str = "Core"
    description: str = "Main torso providing power distribution"
    size: Tuple[float, float, float] = (2.8, 1.8, 7.2)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=34.0,
            energy_cost=3.5,
            integrity=140.0,
            heat_dissipation=15.0,
            power_output=60.0,
            buoyancy_bias=6.0,
        )
    )
    material: str = "bio-alloy"
    energy_capacity: float = 200.0
    cargo_slots: int = 2

    ATTACHMENT_SLOTS: ClassVar[Tuple[AttachmentPoint, ...]] = (
        AttachmentPoint(
            name="head_socket",
            joint=Joint(JointType.FIXED),
            allowed_modules=(HeadModule,),
            description="Connection for the head module",
            max_child_mass=18.0,
            allowed_materials=("bio-alloy", "chitin"),
        ),
        AttachmentPoint(
            name="dorsal_mount",
            joint=Joint(JointType.BALL, swing_limits=(-35.0, 35.0)),
            allowed_modules=(SensoryModule,),
            max_child_mass=5.0,
            allowed_materials=("ceramic", "bio-alloy"),
        ),
        AttachmentPoint(
            name="ventral_core",
            joint=Joint(JointType.HINGE, swing_limits=(-20.0, 20.0)),
            allowed_modules=(PropulsionModule, LimbModule),
            max_child_mass=25.0,
            allowed_materials=("flex-polymer", "titanium"),
        ),
        AttachmentPoint(
            name="lateral_mount_left",
            joint=Joint(JointType.MUSCLE, swing_limits=(-50.0, 50.0), torque_limit=120.0),
            allowed_modules=(LimbModule,),
            max_child_mass=12.0,
            allowed_materials=("flex-polymer",),
        ),
        AttachmentPoint(
            name="lateral_mount_right",
            joint=Joint(JointType.MUSCLE, swing_limits=(-50.0, 50.0), torque_limit=120.0),
            allowed_modules=(LimbModule,),
            max_child_mass=12.0,
            allowed_materials=("flex-polymer",),
        ),
    )

    def __post_init__(self) -> None:
        if not self.attachment_points:
            self.add_attachment_points(_clone_attachment_points(self.ATTACHMENT_SLOTS))


@dataclass
class CephalonHead(HeadModule):
    """Default head packed with visual and cognitive enhancers."""

    key: str = "head"
    name: str = "Cephalon"
    description: str = "Primary sensory organ"
    size: Tuple[float, float, float] = (1.6, 1.2, 4.2)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=7.5,
            energy_cost=1.2,
            integrity=60.0,
            heat_dissipation=6.0,
            buoyancy_bias=2.0,
        )
    )
    material: str = "bio-alloy"
    vision_bonus: float = 45.0
    cognition_bonus: float = 12.0

    ATTACHMENT_SLOTS: ClassVar[Tuple[AttachmentPoint, ...]] = (
        AttachmentPoint(
            name="cranial_sensor",
            joint=Joint(JointType.FIXED),
            allowed_modules=(SensoryModule,),
            max_child_mass=4.0,
            allowed_materials=("ceramic",),
        ),
    )

    def __post_init__(self) -> None:
        if not self.attachment_points:
            self.add_attachment_points(_clone_attachment_points(self.ATTACHMENT_SLOTS))


@dataclass
class HydroFin(LimbModule):
    """Flexible fin-like limb specialised for aquatic locomotion."""

    key: str = "fin"
    name: str = "Hydro Fin"
    description: str = "Flexible fin for aquatic thrust"
    size: Tuple[float, float, float] = (2.4, 0.6, 5.2)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=4.2,
            energy_cost=0.6,
            integrity=38.0,
            heat_dissipation=4.0,
            buoyancy_bias=5.0,
        )
    )
    material: str = "flex-polymer"
    thrust: float = 45.0
    grip_strength: float = 5.0
    lift_coefficient: float = 36.0


@dataclass
class TailThruster(PropulsionModule):
    """Directional thruster that can also host lightweight sensors."""

    key: str = "thruster"
    name: str = "Tail Thruster"
    description: str = "Powerful axial thruster"
    size: Tuple[float, float, float] = (2.1, 1.2, 6.0)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=16.0,
            energy_cost=2.8,
            integrity=55.0,
            heat_dissipation=10.0,
            power_output=30.0,
            buoyancy_bias=-4.0,
        )
    )
    material: str = "titanium"
    thrust_power: float = 120.0
    fuel_efficiency: float = 0.8

    ATTACHMENT_SLOTS: ClassVar[Tuple[AttachmentPoint, ...]] = (
        AttachmentPoint(
            name="tail_sensors",
            joint=Joint(JointType.FIXED),
            allowed_modules=(SensoryModule,),
            max_child_mass=4.0,
            allowed_materials=("ceramic",),
        ),
    )

    def __post_init__(self) -> None:
        if not self.attachment_points:
            self.add_attachment_points(_clone_attachment_points(self.ATTACHMENT_SLOTS))


@dataclass
class SensorPod(SensoryModule):
    """Compact sensor pod that can be reconfigured with a spectrum."""

    key: str = "sensor"
    name: str = "Sensor Pod"
    description: str = "Specialised detection apparatus"
    size: Tuple[float, float, float] = (0.9, 0.8, 2.5)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=1.4,
            energy_cost=0.4,
            integrity=22.0,
            heat_dissipation=2.5,
            buoyancy_bias=1.0,
        )
    )
    material: str = "ceramic"
    detection_range: float = 75.0
    spectrum: Sequence[str] = field(default_factory=lambda: ("light", "colour"))

    def __post_init__(self) -> None:
        if not isinstance(self.spectrum, tuple):
            self.spectrum = tuple(self.spectrum)


# Convenience builders -----------------------------------------------------

def build_default_core(key: str = "core") -> CoreModule:
    """Return a lightweight default core with a few attachment points."""

    module = TrunkCore(key=key)
    return module


def build_default_head(key: str = "head") -> HeadModule:
    """Return a head module with sensory attachment points."""

    module = CephalonHead(key=key)
    return module


def build_default_fin(key: str) -> LimbModule:
    """Return a fin-like limb module."""

    module = HydroFin(key=key)
    return module


def build_default_thruster(key: str) -> PropulsionModule:
    """Return a tail thruster module."""

    module = TailThruster(key=key)
    return module


def build_default_sensor(key: str, spectrum: Sequence[str]) -> SensoryModule:
    """Return a sensory module that can be attached on multiple sockets."""

    return SensorPod(key=key, spectrum=tuple(spectrum))


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
