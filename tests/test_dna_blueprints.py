import random

from evolution.dna.blueprints import generate_modular_blueprint
from evolution.dna.factory import build_body_graph


def test_generate_modular_blueprint_produces_valid_graph() -> None:
    rng = random.Random(1234)
    blueprint = generate_modular_blueprint("omnivore", rng=rng)
    graph = build_body_graph(blueprint)

    assert graph.root_id == "core"
    assert len(graph) >= 5
    assert any(node.module.module_type == "sensor" for node in graph.iter_depth_first())


def test_generate_modular_blueprint_varies_with_diet() -> None:
    herbivore = generate_modular_blueprint("herbivore", rng=random.Random(99))
    carnivore = generate_modular_blueprint("carnivore", rng=random.Random(99))

    herb_graph = build_body_graph(herbivore)
    carn_graph = build_body_graph(carnivore)

    assert herb_graph.summary()  # sanity
    assert carn_graph.summary()
    herb_spectrum = tuple(herbivore["modules"]["head_sensor"]["parameters"]["spectrum"])
    carn_spectrum = tuple(carnivore["modules"]["head_sensor"]["parameters"]["spectrum"])
    assert herb_spectrum != carn_spectrum
