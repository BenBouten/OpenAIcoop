# Marine Base Form Evolution Layer

This document establishes the five marine archetypes that future evolutions must
use as starting points. The definitions mirror the new `BaseForm` schema in
`evolution/dna/base_forms.py` and are intentionally system-oriented so they slot
into DNA generation, AI behaviour weighting, movement, and reproduction
compatibility rules without rewriting the simulation loop.

## 1. BaseForm Data Structure

The schema is implemented as frozen dataclasses for stability and easy
serialisation:

```python
@dataclass(frozen=True)
class BaseForm:
    key: str
    label: str
    dna: DNAProfile            # movement, speed, offence/defence balance
    behaviour: BehaviourIdentity  # state machine, depth, priorities
    evolution: EvolutionRules  # mutation pace, constraints, specialisations
    interfaces: SystemInterfaces  # integration notes for core systems
```

A registry named `BASE_FORMS` exposes the five archetypes, and `EVOLUTION_MATRIX`
encodes their specialisation notes.

## 2. Example DNA Profiles

| Base Form | movement_style | base_speed | agility | defense_bias | attack_bias | sensory_range | metabolism_rate | reproduction_style |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Drifter (Jelly / Qual) | pulse | 0.35 | 0.25 | 0.30 | 0.15 | 38.0 | 0.50 | broadcast_spawn |
| Burrower (Sea Worm) | slither | 0.25 | 0.30 | 0.45 | 0.25 | 30.0 | 0.35 | egg_cluster |
| Streamliner (Fish-like) | glide | 0.60 | 0.55 | 0.35 | 0.45 | 45.0 | 0.65 | egg_cloud |
| Tentacle Core (Octopus-like) | jet | 0.45 | 0.70 | 0.40 | 0.50 | 50.0 | 0.70 | brooded_clusters |
| Bastion (Shell / Armored) | crawl | 0.18 | 0.20 | 0.75 | 0.35 | 28.0 | 0.40 | plated_broadcast |

## 3. Evolution Rule Matrix

Each archetype lists mutation pace (fast/moderate/slow), constraints, and
specialisation routes. The matrix below summarises the specialisations and their
mechanical focus.

| Base Form | Swarm/Coordination | Predator Lean | Tank/Defense | Explorer/Utility |
| --- | --- | --- | --- | --- |
| Drifter | swarm → pulse efficiency, group cohesion | lure_predator → bioluminescent bait & venom payload | — | signal_broadcaster → extended range & comms |
| Burrower | detritivore_swarm → efficiency, low attack | ambush_predator → camo strike, higher attack | trap_layer → mucus nets, territory-first | — |
| Streamliner | pack_hunter → coordination buffs | solo_sprinter → burst speed, lower defence | — | scout_explorer → range & low drag |
| Tentacle Core | — | ink_striker → burst/ink tools | — | tool_user/reef_engineer → manipulation, grip, territory |
| Bastion | — | — | tank/living_wall → shell density, anchoring | slow_grazer → metabolism minimisation |

## 4. Spawn Selection Pseudocode

```python
def select_base_form_at_spawn(environment, rng):
    # 1. Detect biome + depth to bias archetype.
    depth = environment.depth_layer_at_spawn_point()
    temperature = environment.temperature_band()

    # 2. Build weighted options from BASE_FORMS.
    weights = {}
    for form in BASE_FORMS.values():
        weights[form.key] = depth_affinity(depth, form.behaviour.preferred_depth_layer)
        weights[form.key] *= temperature_affinity(temperature, form.key)
        weights[form.key] *= rarity_curve(form.key, rng)

    # 3. Pick a base form and hydrate DNA.
    chosen_key = weighted_choice(weights, rng)
    base_form = BASE_FORMS[chosen_key]
    dna_profile = seed_dna_from_base_form(base_form)

    # 4. Pass movement/reproduction flags into system constructors.
    locomotion_profile = map_movement_style(base_form.dna.movement_style)
    reproduction_rules = lookup_reproduction_rules(base_form.dna.reproduction_style)

    return Lifeform(state, x, y, dna_profile, generation=0,
                    locomotion_profile=locomotion_profile,
                    reproduction_rules=reproduction_rules,
                    base_form=base_form.key)
```

## 5. System Integration and Preservation Notes

- **lifeform.py (DNA initialisation):** read `base_form` metadata when seeding
  `MorphologyGenotype`, locomotion profile, and physics body defaults so the
  archetype flavour appears without altering existing per-stat calculations.
- **ai.py (behaviour bias):** map `BehaviourIdentity` to initial state-machine
  weights (e.g., Drifter prioritises flee > forage > mate) while keeping current
  decision nodes intact.
- **movement.py (locomotion style):** reuse `movement_style` to select
  locomotion curves (pulse/glide/slither/jet/crawl) without changing collision
  handling or velocity integration.
- **reproduction.py (compatibility):** couple `reproduction_style` to
  compatibility checks; existing reproduction cooldowns and energy costs remain
  unchanged.
- **Simulation stability:** all values are additive metadata. No existing tests
  or runtime entry points are removed; the layer only feeds deterministic seeds
  into the current generation and progression pipeline.
