"""Procedural development traits for generated DNA profiles."""
from __future__ import annotations

import random
from typing import Iterable, Mapping, MutableMapping, Optional

__all__ = [
    "generate_development_plan",
    "mix_development_plans",
    "mutate_profile_development",
    "describe_feature",
    "describe_skin_stage",
    "ensure_development_plan",
]

_SKIN_STAGES = [
    {
        "id": "bare",
        "label": "Kaal",
        "description": "Nog nauwelijks bepantsering of pigment; zachte huid.",
    },
    {
        "id": "patterned",
        "label": "Vlekkerig",
        "description": "Eerste patronen en lichte bepantsering worden zichtbaar.",
    },
    {
        "id": "plated",
        "label": "Platen",
        "description": "Dikkere huidplaten bieden bescherming en textuur.",
    },
    {
        "id": "ornate",
        "label": "Volgroeid",
        "description": "Volledig ontwikkelde huid met patronen, uitsteeksels en pigmentlagen.",
    },
]

_FEATURE_LIBRARY = {
    "saber_fangs": {
        "label": "Sabeltanden",
        "description": "Langere tanden voor diepe beten en het vasthouden van prooi.",
    },
    "crushing_jaw": {
        "label": "Versterkte kaak",
        "description": "Brede kaakspieren voor krachtige beten.",
    },
    "hooked_claws": {
        "label": "Haakklauwen",
        "description": "Grip om prooi vast te klemmen tijdens de aanval.",
    },
    "long_neck": {
        "label": "Lange nek",
        "description": "Bereikt hogere vegetatie zonder te verplaatsen.",
    },
    "wide_muzzle": {
        "label": "Brede snuit",
        "description": "Maakt gelijktijdig grazen over een groter oppervlak mogelijk.",
    },
    "digestive_sacks": {
        "label": "Fermentatiezakken",
        "description": "Extra verteringskamers voor vezelrijk voedsel.",
    },
    "flexible_jaw": {
        "label": "Flexibele kaken",
        "description": "Kan zowel scheuren als kauwen, handig voor omnivoren.",
    },
    "gripping_digits": {
        "label": "Grijpvingers",
        "description": "Handige klauwen/vingers om voedsel te manipuleren.",
    },
    "cheek_pouches": {
        "label": "Wangzakken",
        "description": "Opslagruimte om voedsel tijdelijk te bewaren.",
    },
}

_DIET_FEATURE_ORDER = {
    "carnivore": ["saber_fangs", "crushing_jaw", "hooked_claws"],
    "herbivore": ["long_neck", "wide_muzzle", "digestive_sacks"],
    "omnivore": ["flexible_jaw", "gripping_digits", "cheek_pouches"],
}


def _empty_plan() -> dict:
    return {"skin_stage": 0, "features": []}


def describe_skin_stage(stage_index: int) -> dict[str, str]:
    stage = max(0, min(stage_index, len(_SKIN_STAGES) - 1))
    return dict(_SKIN_STAGES[stage])


def describe_feature(feature_id: str) -> dict[str, str]:
    data = _FEATURE_LIBRARY.get(feature_id)
    if not data:
        return {"id": feature_id, "label": feature_id.title(), "description": ""}
    return {"id": feature_id, **data}


def ensure_development_plan(data: Optional[Mapping[str, object]]) -> dict:
    plan = _empty_plan()
    if not data:
        return plan
    stage = int(data.get("skin_stage", 0))
    plan["skin_stage"] = max(0, min(stage, len(_SKIN_STAGES) - 1))
    raw_features = data.get("features")
    features: list[str] = []
    if isinstance(raw_features, Iterable):
        for feature in raw_features:
            feature_id = str(feature)
            if feature_id in _FEATURE_LIBRARY and feature_id not in features:
                features.append(feature_id)
    plan["features"] = features
    return plan


def _feature_order_for(diet: str) -> list[str]:
    return list(_DIET_FEATURE_ORDER.get(diet, _DIET_FEATURE_ORDER["omnivore"]))


def _target_feature_count(stage: int) -> int:
    if stage <= 0:
        return 0
    if stage == 1:
        return 1
    if stage == 2:
        return 2
    return 3


def _fill_features(plan: dict, diet: str) -> None:
    order = _feature_order_for(diet)
    target = min(len(order), _target_feature_count(plan["skin_stage"]))
    current = [fid for fid in plan["features"] if fid in order]
    current = current[:target]
    while len(current) < target:
        next_feature = order[len(current)]
        current.append(next_feature)
    plan["features"] = current


def generate_development_plan(diet: str, *, rng: Optional[random.Random] = None) -> dict:
    rng = rng or random
    plan = _empty_plan()
    # Een klein deel start met een minimale huidtextuur.
    if rng.random() < 0.15:
        plan["skin_stage"] = 1
    _fill_features(plan, diet)
    return plan


def mix_development_plans(
    diet: str,
    parent_a: Optional[Mapping[str, object]],
    parent_b: Optional[Mapping[str, object]],
) -> dict:
    plan_a = ensure_development_plan(parent_a)
    plan_b = ensure_development_plan(parent_b)
    stage = max(plan_a["skin_stage"], plan_b["skin_stage"])
    combined = _empty_plan()
    combined["skin_stage"] = stage
    order = _feature_order_for(diet)
    inherited = [fid for fid in order if fid in plan_a["features"] or fid in plan_b["features"]]
    combined["features"] = inherited
    _fill_features(combined, diet)
    return combined


def mutate_profile_development(
    profile: MutableMapping[str, object], *, rng: Optional[random.Random] = None
) -> None:
    rng = rng or random
    diet = str(profile.get("diet", "omnivore"))
    plan = ensure_development_plan(profile.get("development"))
    if rng.random() < 0.35 and plan["skin_stage"] < len(_SKIN_STAGES) - 1:
        plan["skin_stage"] += 1
    _fill_features(plan, diet)
    profile["development"] = plan
