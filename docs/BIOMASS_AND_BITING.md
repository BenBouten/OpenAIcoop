# Biomass & Generic Biting System

The biomass system abstracts all consumable matter – plants, carrion, and
creature bodies – behind a common interface. Any creature can attempt to
bite nearby biomass by raising the `bite_intent` controller output
(0..1). When the intent is high and a target is within reach the engine
transfers energy and wounds are applied without relying on predator/prey
roles.

## Biomass targets

- **Plants / resource patches** use their moss cell nutrition and apply
  hydration/toxin effects. The eater's `digest_efficiency_plants` scales
  the energy and satiety gained.
- **Carrion / dead bodies** expose stored nutrition with light armor. The
  eater's `digest_efficiency_meat` controls how much of a bite turns into
  usable energy.
- **Living creatures** can be bitten directly. Effective damage is based
  on the attacker's `bite_force` (plus melee strength) versus the target's
  `tissue_hardness`, and the eater immediately recovers energy from the
  bite.

## Emergent diets

There are no role checks; differences in traits create ecological roles:

- High `digest_efficiency_plants` + modest `bite_force` → efficient
  herbivores that park near moss clusters.
- High `digest_efficiency_meat` + high `bite_force` → predators and
  scavengers that convert flesh efficiently.
- High `tissue_hardness` → prey that are costly to bite, rewarding
  creatures with bigger bite budgets.

Controllers can evolve behaviors by simply modulating `bite_intent` – from
"only bite when starving" to "bite anything within reach" – and the trait
combinations above drive whether the strategy is viable.
