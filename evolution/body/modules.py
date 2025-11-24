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
    nutrition_value: float = 0.0  # Nutrition when eaten (auto-calculated from mass)


def calculate_module_nutrition(mass: float, module_type: str = "generic") -> float:
    """Calculate nutrition value for a module based on its mass and type.
    
    Different module types have different nutritional values:
    - Cores/organs are energy-rich (1.5x multiplier)
    - Muscles are protein-rich (1.3x)
    - Armor/teeth are less edible (0.6-0.8x)
    
    Args:
        mass: Module mass in kg
        module_type: Type of module (affects nutrition multiplier)
        
    Returns:
        Nutrition value (energy units creature gains from eating this module)
    """
    # Base nutrition: ~10 nutrition per kg of mass
    base_nutrition = mass * 10.0
    
    # Type multipliers (some modules are more nutritious than others)
    type_multipliers = {
        "core": 1.5,       # Energy-rich organs
        "muscle": 1.3,     # Protein-rich tissue
        "storage": 1.4,    # Fat/energy storage
        "mouth": 0.8,      # Teeth/beak - less edible
        "armor": 0.6,      # Hard scales - less nutritious
        "sensor": 0.9,     # Eyes, sensors - moderate
        "eye": 0.9,        # Visual organs
        "propulsion": 1.2, # Muscles for movement
        "limb": 1.1,       # Fins, legs
        "tentacle": 1.1,   # Tentacles
        "head": 1.0,       # Brain matter
        "tail": 1.0,       # Standard tissue
        "fin": 1.1,        # Fin tissue
        "generic": 1.0,    # Default
    }
    
    multiplier = type_multipliers.get(module_type, 1.0)
    return base_nutrition * multiplier


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
    natural_orientation: float = 0.0

    module_type: str = "generic"
    variant: Optional[str] = None

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


@dataclass
class Eye(SensoryModule):
    """Visual sensory organ with variable pupil and iris characteristics."""

    key: str = "eye"
    name: str = "Eye"
    description: str = "Visual receptor"
    size: Tuple[float, float, float] = (0.4, 0.4, 0.3)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=0.3,
            energy_cost=0.15,
            integrity=5.0,
            heat_dissipation=0.5,
            buoyancy_bias=0.0,
        )
    )
    material: str = "organic"
    detection_range: float = 150.0
    spectrum: Sequence[str] = ("light", "colour", "motion")
    module_type: str = "eye"

    # Visual traits
    pupil_shape: str = "circle"  # circle, slit, rect, cross
    iris_color: Tuple[int, int, int] = (200, 200, 200)
    pupil_color: Tuple[int, int, int] = (10, 10, 10)
    eye_size: float = 1.0  # Scale factor for drawing

    def __post_init__(self) -> None:
        # Scale stats based on size volume relative to default
        default_vol = 0.4 * 0.4 * 0.3
        vol = self.size[0] * self.size[1] * self.size[2]
        scale = max(0.5, vol / max(0.001, default_vol))
        
        # Adjust detection range
        self.detection_range *= (scale ** 0.5)
        
        # Adjust stats (mass, energy)
        # We need to create a new ModuleStats object because it's frozen
        self.stats = ModuleStats(
            mass=self.stats.mass * scale,
            energy_cost=self.stats.energy_cost * scale,
            integrity=self.stats.integrity * (scale ** 0.5),
            heat_dissipation=self.stats.heat_dissipation * scale,
            buoyancy_bias=self.stats.buoyancy_bias
        )


@dataclass
class Mouth(BodyModule):
    """Feeding apparatus."""

    key: str = "mouth"
    name: str = "Mouth"
    description: str = "Ingestion orifice"
    size: Tuple[float, float, float] = (0.6, 0.5, 0.4)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=0.8,
            energy_cost=0.2,
            integrity=15.0,
            heat_dissipation=1.0,
            buoyancy_bias=0.0,
        )
    )
    material: str = "chitin"
    module_type: str = "mouth"

    # Traits
    jaw_type: str = "mandibles"  # mandibles, beak, sucker, filter
    bite_damage: float = 5.0

    def __post_init__(self) -> None:
        # Scale stats based on size volume relative to default
        default_vol = 0.6 * 0.5 * 0.4
        vol = self.size[0] * self.size[1] * self.size[2]
        scale = max(0.5, vol / max(0.001, default_vol))
        
        # Adjust bite damage
        self.bite_damage *= scale
        
        # Adjust stats
        self.stats = ModuleStats(
            mass=self.stats.mass * scale,
            energy_cost=self.stats.energy_cost * scale, # Bigger mouth = more energy
            integrity=self.stats.integrity * (scale ** 0.5),
            heat_dissipation=self.stats.heat_dissipation * scale,
            buoyancy_bias=self.stats.buoyancy_bias
        )


@dataclass
class TentacleLimb(LimbModule):
    """Elongated limb specialised for grasping and pulsed swimming."""

    key: str = "tentacle"
    name: str = "Ribbon Tentacle"
    description: str = "Flexible tentacle capable of stinging and steering"
    size: Tuple[float, float, float] = (0.8, 0.6, 6.0)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=2.4,
            energy_cost=0.45,
            integrity=22.0,
            heat_dissipation=2.0,
            buoyancy_bias=0.9,
        )
    )
    material: str = "mesoglea"
    thrust: float = 18.0
    grip_strength: float = 16.0
    lift_coefficient: float = 14.0

    module_type: str = "tentacle"

    venom_intensity: float = 0.35
    pulse_resonance: float = 0.65


@dataclass
class JellyBell(CoreModule):
    """Gelatinous bell that anchors tentacles and pulse propulsion."""

    key: str = "bell_core"
    name: str = "Jelly Bell"
    description: str = "Buoyant bell with radial tentacle ring"
    size: Tuple[float, float, float] = (3.2, 3.2, 2.6)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=10.5,
            energy_cost=0.8,
            integrity=30.0,
            heat_dissipation=2.8,
            power_output=22.0,
            buoyancy_bias=1.25,
        )
    )
    material: str = "mesoglea"
    energy_capacity: float = 120.0
    cargo_slots: int = 0

    module_type: str = "bell_core"

    pulse_rate: float = 0.85
    bioluminescence: float = 0.55

    ATTACHMENT_SLOTS: ClassVar[Tuple[AttachmentPoint, ...]] = (
        AttachmentPoint(
            name="siphon_nozzle",
            joint=Joint(JointType.BALL, swing_limits=(-25.0, 25.0)),
            allowed_modules=(PropulsionModule,),
            description="Central jet for pulse propulsion",
            max_child_mass=10.0,
            allowed_materials=("mesoglea", "flex-polymer"),
        ),
        AttachmentPoint(
            name="umbrella_sensor",
            joint=Joint(JointType.FIXED),
            allowed_modules=(SensoryModule,),
            description="Dome tip sensor cluster",
            max_child_mass=3.0,
            allowed_materials=("ceramic", "mesoglea"),
        ),
        AttachmentPoint(
            name="tentacle_socket_front",
            joint=Joint(JointType.MUSCLE, swing_limits=(-85.0, 55.0), torque_limit=45.0),
            allowed_modules=(LimbModule,),
            description="Front-facing tentacle socket",
            max_child_mass=4.0,
            allowed_materials=("mesoglea", "flex-polymer"),
            offset=(-0.12, -0.8),
            angle=-115.0,
            clearance=0.8,
            relative=True,
        ),
        AttachmentPoint(
            name="tentacle_socket_left",
            joint=Joint(JointType.MUSCLE, swing_limits=(-85.0, 55.0), torque_limit=50.0),
            allowed_modules=(LimbModule,),
            description="Left rim tentacle socket",
            max_child_mass=4.2,
            allowed_materials=("mesoglea", "flex-polymer"),
            offset=(-0.52, -0.82),
            angle=-155.0,
            clearance=0.9,
            relative=True,
        ),
        AttachmentPoint(
            name="tentacle_socket_right",
            joint=Joint(JointType.MUSCLE, swing_limits=(-85.0, 55.0), torque_limit=50.0),
            allowed_modules=(LimbModule,),
            description="Right rim tentacle socket",
            max_child_mass=4.2,
            allowed_materials=("mesoglea", "flex-polymer"),
            offset=(0.52, -0.82),
            angle=-25.0,
            clearance=0.9,
            relative=True,
        ),
        AttachmentPoint(
            name="tentacle_socket_rear",
            joint=Joint(JointType.MUSCLE, swing_limits=(-65.0, 85.0), torque_limit=60.0),
            allowed_modules=(LimbModule,),
            description="Trailing tentacle socket",
            max_child_mass=4.7,
            allowed_materials=("mesoglea", "flex-polymer"),
            offset=(0.0, -0.92),
            angle=-90.0,
            clearance=1.0,
            relative=True,
        ),
    )

    def __post_init__(self) -> None:
        if not self.attachment_points:
            self.add_attachment_points(_clone_attachment_points(self.ATTACHMENT_SLOTS))


@dataclass
class RoundCore(CoreModule):
    """Compact spherical torso with radial arm slots."""

    key: str = "round_core"
    name: str = "Round Core"
    description: str = "Orb-like body with evenly spaced limb sockets"
    size: Tuple[float, float, float] = (1.9, 1.9, 1.9)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=18.0,
            energy_cost=2.0,
            integrity=95.0,
            heat_dissipation=9.0,
            power_output=50.0,
            buoyancy_bias=0.6,
        )
    )
    material: str = "bio-alloy"
    energy_capacity: float = 180.0
    cargo_slots: int = 1

    module_type: str = "core"

    ATTACHMENT_SLOTS: ClassVar[Tuple[AttachmentPoint, ...]] = (
        AttachmentPoint(
            name="head_socket",
            joint=Joint(JointType.FIXED),
            allowed_modules=(HeadModule,),
            description="Crown mount for sensory head",
            max_child_mass=14.0,
            allowed_materials=("bio-alloy", "chitin"),
            offset=(0.0, 0.6),
            angle=0.0,
            clearance=1.0,
            relative=True,
        ),
        AttachmentPoint(
            name="ventral_socket",
            joint=Joint(JointType.HINGE, swing_limits=(-30.0, 30.0)),
            allowed_modules=(PropulsionModule, LimbModule),
            description="Underslung socket for jets or trailing limbs",
            max_child_mass=18.0,
            allowed_materials=("flex-polymer", "mesoglea", "titanium"),
            offset=(-0.25, -0.6),
            angle=180.0,
            clearance=1.1,
            relative=True,
        ),
        AttachmentPoint(
            name="radial_1",
            joint=Joint(JointType.MUSCLE, swing_limits=(-110.0, 110.0), torque_limit=95.0),
            allowed_modules=(LimbModule,),
            description="Front-left radial limb mount",
            max_child_mass=10.0,
            allowed_materials=("flex-polymer", "mesoglea"),
            offset=(-0.55, 0.05),
            angle=135.0,
            clearance=0.9,
            relative=True,
        ),
        AttachmentPoint(
            name="radial_2",
            joint=Joint(JointType.MUSCLE, swing_limits=(-110.0, 110.0), torque_limit=95.0),
            allowed_modules=(LimbModule,),
            description="Front-right radial limb mount",
            max_child_mass=10.0,
            allowed_materials=("flex-polymer", "mesoglea"),
            offset=(0.55, 0.05),
            angle=45.0,
            clearance=0.9,
            relative=True,
        ),
        AttachmentPoint(
            name="radial_3",
            joint=Joint(JointType.MUSCLE, swing_limits=(-110.0, 110.0), torque_limit=95.0),
            allowed_modules=(LimbModule,),
            description="Rear-right radial limb mount",
            max_child_mass=10.0,
            allowed_materials=("flex-polymer", "mesoglea"),
            offset=(0.55, -0.05),
            angle=-45.0,
            clearance=0.9,
            relative=True,
        ),
        AttachmentPoint(
            name="radial_4",
            joint=Joint(JointType.MUSCLE, swing_limits=(-110.0, 110.0), torque_limit=95.0),
            allowed_modules=(LimbModule,),
            description="Rear-left radial limb mount",
            max_child_mass=10.0,
            allowed_materials=("flex-polymer", "mesoglea"),
            offset=(-0.55, -0.05),
            angle=-135.0,
            clearance=0.9,
            relative=True,
        ),
    )

    def __post_init__(self) -> None:
        if not self.attachment_points:
            self.add_attachment_points(_clone_attachment_points(self.ATTACHMENT_SLOTS))


@dataclass
class PulseSiphon(PropulsionModule):
    """Low-profile jet that rhythmically expands/contracts."""

    key: str = "pulse_siphon"
    name: str = "Pulse Siphon"
    description: str = "Radial jet for bell compression thrust"
    size: Tuple[float, float, float] = (1.2, 1.0, 2.4)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=6.0,
            energy_cost=1.0,
            integrity=20.0,
            heat_dissipation=2.5,
            power_output=16.0,
            buoyancy_bias=0.35,
        )
    )
    material: str = "mesoglea"
    thrust_power: float = 55.0
    fuel_efficiency: float = 1.2

    module_type: str = "propulsion"
    pulse_frequency: float = 0.95


@dataclass
class TentacleLimb(LimbModule):
    """Flexible grasping tentacle."""

    key: str = "tentacle"
    name: str = "Tentacle"
    description: str = "Prehensile limb"
    size: Tuple[float, float, float] = (0.4, 0.4, 4.0)
    stats: ModuleStats = field(
        default_factory=lambda: ModuleStats(
            mass=1.5,
            energy_cost=0.2,
            integrity=10.0,
            heat_dissipation=1.0,
            buoyancy_bias=0.0,
        )
    )
    material: str = "mesoglea"
    thrust: float = 5.0
    grip_strength: float = 15.0
    
    module_type: str = "tentacle"
    
    ATTACHMENT_SLOTS: ClassVar[Tuple[AttachmentPoint, ...]] = (
        AttachmentPoint(
            name="distal_tip",
            joint=Joint(JointType.BALL, swing_limits=(-45.0, 45.0)),
            allowed_modules=(LimbModule, SensoryModule),
            description="Tip of the tentacle",
            max_child_mass=2.0,
            allowed_materials=("mesoglea", "flex-polymer"),
            relative=True,
            offset=(0.0, 1.0),
        ),
    )

    def __post_init__(self) -> None:
        if not self.attachment_points:
            self.add_attachment_points(_clone_attachment_points(self.ATTACHMENT_SLOTS))


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
            offset=point.offset,
            angle=point.angle,
            clearance=point.clearance,
            relative=point.relative,
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
            buoyancy_bias=0.5,
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
            offset=(0.0, 0.5),
            angle=0.0,
            clearance=1.0,
            relative=True,
        ),
        AttachmentPoint(
            name="dorsal_mount",
            joint=Joint(JointType.BALL, swing_limits=(-35.0, 35.0)),
            allowed_modules=(SensoryModule, LimbModule),
            max_child_mass=15.0,
            allowed_materials=("ceramic", "bio-alloy", "flex-polymer", "mesoglea"),
            offset=(0.0, 0.5),
            angle=-90.0,
            clearance=0.6,
            relative=True,
        ),
        AttachmentPoint(
            name="ventral_core",
            joint=Joint(JointType.HINGE, swing_limits=(-20.0, 20.0)),
            allowed_modules=(PropulsionModule, LimbModule),
            max_child_mass=25.0,
            allowed_materials=("flex-polymer", "titanium", "mesoglea"),
            offset=(-0.4, -0.5),
            angle=180.0,
            clearance=1.4,
            relative=True,
        ),
        AttachmentPoint(
            name="lateral_mount_left",
            joint=Joint(JointType.MUSCLE, swing_limits=(-50.0, 50.0), torque_limit=120.0),
            allowed_modules=(LimbModule,),
            max_child_mass=12.0,
            allowed_materials=("flex-polymer", "mesoglea"),
            offset=(-0.35, 0.0),
            angle=180.0,
            clearance=0.8,
            relative=True,
        ),
        AttachmentPoint(
            name="lateral_mount_right",
            joint=Joint(JointType.MUSCLE, swing_limits=(-50.0, 50.0), torque_limit=120.0),
            allowed_modules=(LimbModule,),
            max_child_mass=12.0,
            allowed_materials=("flex-polymer", "mesoglea"),
            offset=(-0.35, 0.0),
            angle=0.0,
            clearance=0.8,
            relative=True,
        ),
        AttachmentPoint(
            name="caudal_tentacle_left",
            joint=Joint(JointType.MUSCLE, swing_limits=(-110.0, 110.0), torque_limit=90.0),
            allowed_modules=(LimbModule,),
            description="Rear-left tentacle fan mount",
            max_child_mass=10.0,
            allowed_materials=("flex-polymer", "mesoglea"),
            offset=(-0.8, -0.35),
            angle=210.0,
            clearance=1.0,
            relative=True,
        ),
        AttachmentPoint(
            name="caudal_tentacle_right",
            joint=Joint(JointType.MUSCLE, swing_limits=(-110.0, 110.0), torque_limit=90.0),
            allowed_modules=(LimbModule,),
            description="Rear-right tentacle fan mount",
            max_child_mass=10.0,
            allowed_materials=("flex-polymer", "mesoglea"),
            offset=(-0.8, -0.35),
            angle=-30.0,
            clearance=1.0,
            relative=True,
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
            buoyancy_bias=0.2,
        )
    )
    material: str = "bio-alloy"
    vision_bonus: float = 45.0
    cognition_bonus: float = 12.0

    ATTACHMENT_SLOTS: ClassVar[Tuple[AttachmentPoint, ...]] = (
        AttachmentPoint(
            name="cranial_sensor",
            joint=Joint(JointType.FIXED),
            allowed_modules=(SensoryModule, Eye),
            max_child_mass=4.0,
            allowed_materials=("ceramic", "organic"),
            offset=(0.8, 0.0),
            angle=0.0,
            clearance=0.8,
            relative=True,
        ),
        AttachmentPoint(
            name="mouth_socket",
            joint=Joint(JointType.FIXED),
            allowed_modules=(Mouth,),
            max_child_mass=5.0,
            allowed_materials=("chitin", "organic"),
            offset=(0.6, 0.5),  # Below the sensor/eye
            angle=0.0,
            clearance=0.5,
            relative=True,
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
            buoyancy_bias=0.3,
        )
    )
    material: str = "flex-polymer"
    thrust: float = 45.0
    grip_strength: float = 5.0
    lift_coefficient: float = 36.0

    ATTACHMENT_SLOTS: ClassVar[Tuple[AttachmentPoint, ...]] = (
        AttachmentPoint(
            name="proximal_joint",
            joint=Joint(JointType.MUSCLE, swing_limits=(-80.0, 80.0), torque_limit=90.0),
            allowed_modules=(LimbModule,),
            description="Allows chaining fin segments",
            max_child_mass=6.0,
            allowed_materials=("flex-polymer",),
            offset=(1.0, 0.0),
            angle=0.0,
            clearance=1.2,
            relative=True,
        ),
    )

    def __post_init__(self) -> None:
        if not self.attachment_points:
            self.add_attachment_points(_clone_attachment_points(self.ATTACHMENT_SLOTS))


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
            buoyancy_bias=-0.3,
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
        AttachmentPoint(
            name="tail_socket",
            joint=Joint(JointType.FIXED),
            allowed_modules=(PropulsionModule,),
            max_child_mass=20.0,
            allowed_materials=("titanium", "bio-alloy"),
            offset=(0.0, 1.0),
            relative=True,
        ),
        AttachmentPoint(
            name="lateral_mount_left",
            joint=Joint(JointType.MUSCLE, swing_limits=(-30.0, 30.0)),
            allowed_modules=(LimbModule,),
            max_child_mass=5.0,
            allowed_materials=("flex-polymer", "chitin"),
            offset=(-0.3, 0.0),
            angle=90.0,
            relative=True,
        ),
        AttachmentPoint(
            name="lateral_mount_right",
            joint=Joint(JointType.MUSCLE, swing_limits=(-30.0, 30.0)),
            allowed_modules=(LimbModule,),
            max_child_mass=5.0,
            allowed_materials=("flex-polymer", "chitin"),
            offset=(-0.3, 0.0),
            angle=-90.0,
            relative=True,
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
            buoyancy_bias=0.1,
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


def build_eye(key: str) -> Eye:
    """Return a default eye module."""
    return Eye(key=key)


def build_mouth(key: str) -> Mouth:
    """Return a default mouth module."""
    return Mouth(key=key)


def build_jelly_bell_core(key: str = "bell_core") -> JellyBell:
    """Return a buoyant bell core with tentacle sockets."""

    return JellyBell(key=key)


def build_tentacle(key: str) -> TentacleLimb:
    """Return a grasping ribbon tentacle."""

    return TentacleLimb(key=key)


def build_pulse_siphon(key: str = "pulse_siphon") -> PulseSiphon:
    """Return a pulsing propulsion siphon sized for a bell core."""

    return PulseSiphon(key=key)


def catalogue_default_modules() -> Mapping[str, BodyModule]:
    """Return a mapping of simple module presets for prototypes/tests."""

    modules = {
        "core": build_default_core(),
        "head": build_default_head(),
        "fin_left": build_default_fin("fin_left"),
        "fin_right": build_default_fin("fin_right"),
        "thruster": build_default_thruster("thruster"),
        "sensor": build_default_sensor("sensor", ("light", "colour")),
    }
    return modules


def catalogue_jellyfish_modules() -> Mapping[str, BodyModule]:
    """Return modules suited for gelatinous drifters and deep-sea jellies."""

    bell = build_jelly_bell_core("bell_core")
    siphon = build_pulse_siphon("bell_siphon")
    tentacle_front = build_tentacle("tentacle_front")
    tentacle_left = build_tentacle("tentacle_left")
    tentacle_right = build_tentacle("tentacle_right")
    tentacle_rear = build_tentacle("tentacle_rear")
    sensor = SensorPod(key="bell_sensor", spectrum=("light", "bioelectric"))

    return {
        bell.key: bell,
        siphon.key: siphon,
        tentacle_front.key: tentacle_front,
        tentacle_left.key: tentacle_left,
        tentacle_right.key: tentacle_right,
        tentacle_rear.key: tentacle_rear,
        sensor.key: sensor,
    }
