"""Procedurally generated locomotion archetypes for ocean lifeforms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..morphology import MorphologyGenotype, MorphStats


@dataclass(frozen=True)
class LocomotionProfile:
    """Describes how a lifeform moves through the alien ocean."""

    key: str
    label: str
    thrust_efficiency: float
    speed_multiplier: float
    drag_multiplier: float
    energy_cost: float
    sensor_bonus: float
    depth_bias: float
    drift_preference: float
    grip_bonus: float
    burst_force: float
    burst_duration: int
    burst_cooldown: int
    uses_signal_cones: bool
    signal_threshold: float
    light_penalty: float
    description: str
    hover_lift_preference: float = 1.0


_PROFILES: Mapping[str, LocomotionProfile] = {
    "fin_swimmer": LocomotionProfile(
        key="fin_swimmer",
        label="Vin-oscillator",
        thrust_efficiency=1.1,
        speed_multiplier=1.05,
        drag_multiplier=0.9,
        energy_cost=1.0,
        sensor_bonus=8.0,
        depth_bias=-0.1,
        drift_preference=0.15,
        grip_bonus=1.0,
        burst_force=1.0,
        burst_duration=0,
        burst_cooldown=0,
        uses_signal_cones=False,
        signal_threshold=0.3,
        light_penalty=0.0,
        description="Oscillerende vinnen vertalen naar efficiënte thrust en hoge wendbaarheid.",
        hover_lift_preference=1.2,
    ),
    "jet_propulsion": LocomotionProfile(
        key="jet_propulsion",
        label="Jetstuwkracht",
        thrust_efficiency=1.45,
        speed_multiplier=1.2,
        drag_multiplier=0.85,
        energy_cost=1.45,
        sensor_bonus=6.0,
        depth_bias=-0.05,
        drift_preference=0.05,
        grip_bonus=0.85,
        burst_force=2.25,
        burst_duration=18,
        burst_cooldown=220,
        uses_signal_cones=False,
        signal_threshold=0.25,
        light_penalty=0.0,
        description="Schorpioen- en squidachtige mantels leveren korte, dure explosies van snelheid.",
        hover_lift_preference=0.8,
    ),
    "drift_feeder": LocomotionProfile(
        key="drift_feeder",
        label="Drift-planktonier",
        thrust_efficiency=0.65,
        speed_multiplier=0.85,
        drag_multiplier=0.95,
        energy_cost=0.6,
        sensor_bonus=22.0,
        depth_bias=-0.2,
        drift_preference=0.85,
        grip_bonus=0.95,
        burst_force=1.0,
        burst_duration=0,
        burst_cooldown=0,
        uses_signal_cones=False,
        signal_threshold=0.35,
        light_penalty=0.0,
        description="Sensor-rijke zwevers laten zich door stromingen voeren om planktonwolken te filteren.",
        hover_lift_preference=1.4,
    ),
    "benthic_crawler": LocomotionProfile(
        key="benthic_crawler",
        label="Bodemganger",
        thrust_efficiency=0.75,
        speed_multiplier=0.75,
        drag_multiplier=1.15,
        energy_cost=0.9,
        sensor_bonus=10.0,
        depth_bias=0.8,
        drift_preference=0.05,
        grip_bonus=1.35,
        burst_force=1.1,
        burst_duration=0,
        burst_cooldown=0,
        uses_signal_cones=False,
        signal_threshold=0.3,
        light_penalty=0.0,
        description="Gemuteerde pootjes kruipen veilig over de zeebodem en weerstaan stromingen.",
        hover_lift_preference=0.5,
    ),
    "tentacle_walker": LocomotionProfile(
        key="tentacle_walker",
        label="Tentakelganger",
        thrust_efficiency=0.55,
        speed_multiplier=0.6,
        drag_multiplier=0.9,
        energy_cost=0.7,
        sensor_bonus=14.0,
        depth_bias=0.55,
        drift_preference=0.1,
        grip_bonus=1.55,
        burst_force=0.9,
        burst_duration=0,
        burst_cooldown=0,
        uses_signal_cones=False,
        signal_threshold=0.25,
        light_penalty=0.0,
        description="Langzame tentakel-trekkers haken zich vast aan rotsen en mineralen voor stabiliteit.",
        hover_lift_preference=0.65,
    ),
    "electro_stalker": LocomotionProfile(
        key="electro_stalker",
        label="Electro-stalker",
        thrust_efficiency=0.95,
        speed_multiplier=0.95,
        drag_multiplier=1.0,
        energy_cost=0.95,
        sensor_bonus=18.0,
        depth_bias=1.0,
        drift_preference=0.2,
        grip_bonus=1.15,
        burst_force=1.0,
        burst_duration=0,
        burst_cooldown=0,
        uses_signal_cones=True,
        signal_threshold=-0.15,
        light_penalty=0.45,
        description="Diepzeejagers voelen elektrische geur-signalen en sluipen via signal cones.",
        hover_lift_preference=0.9,
    ),
}


def _choose_profile_key(
    dna_profile: Mapping[str, object],
    morphology: MorphologyGenotype,
    stats: MorphStats,
) -> str:
    fins = morphology.fins
    legs = morphology.legs
    whiskers = morphology.whiskers
    antennae = morphology.antennae
    eyes = morphology.eyes
    energy = int(dna_profile.get("energy", 80))

    if legs >= 3:
        return "benthic_crawler"
    if whiskers >= 6 and fins <= 1:
        return "tentacle_walker"
    if eyes <= 1 and antennae >= 2:
        return "electro_stalker"
    if fins <= 1 and energy >= 80:
        return "jet_propulsion"
    if antennae + whiskers >= 6 and fins <= 2:
        return "drift_feeder"
    if fins == 0 and stats.mass <= 1.2:
        return "drift_feeder"
    if fins >= max(2, legs):
        return "fin_swimmer"
    return "fin_swimmer"


def derive_locomotion_profile(
    dna_profile: Mapping[str, object],
    morphology: MorphologyGenotype,
    stats: MorphStats,
) -> LocomotionProfile:
    """Return the locomotion profile derived from DNA traits."""

    key = _choose_profile_key(dna_profile, morphology, stats)
    return _PROFILES[key]
