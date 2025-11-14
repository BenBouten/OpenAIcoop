"""Procedural moss clusters that act as food sources in the world."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import ClassVar, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import pygame


GridCell = Tuple[int, int]

from .moss_dna import MossDNA, average_dna, ensure_dna_for_cells, random_moss_dna


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@dataclass(slots=True)
class MossCluster:
    """A slowly growing moss cluster composed of 2x2 cells."""

    cells: Mapping[GridCell, MossDNA] | Iterable[GridCell]
    color: Tuple[int, int, int] = (68, 132, 88)
    CELL_SIZE: ClassVar[int] = 2
    BASE_GROWTH_DELAY: ClassVar[int] = 180

    surface: pygame.Surface = field(init=False, repr=False)
    rect: pygame.Rect = field(init=False)
    width: int = field(init=False)
    height: int = field(init=False)
    x: float = field(init=False)
    y: float = field(init=False)
    resource: float = field(init=False)
    _dirty: bool = field(init=False, repr=False)
    _environment_multiplier: float = field(init=False, repr=False)
    _growth_timer: int = field(init=False, repr=False)
    _global_growth_modifier: float = field(init=False, repr=False)
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        raw_cells = self.cells
        self._rng = random.Random()
        if isinstance(raw_cells, Mapping):
            cell_map: Dict[GridCell, MossDNA] = {}
            for cell, dna in raw_cells.items():
                gx, gy = int(cell[0]), int(cell[1])
                if not isinstance(dna, MossDNA):
                    dna = random_moss_dna(self._rng)
                cell_map[(gx, gy)] = dna
        else:
            cell_map = ensure_dna_for_cells(tuple(raw_cells), self._rng)

        self.cells = cell_map
        self.surface = pygame.Surface((0, 0), pygame.SRCALPHA)
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.width = 0
        self.height = 0
        self.x = 0.0
        self.y = 0.0
        self.resource = 0.0
        self._dirty = True
        self._environment_multiplier = 1.0
        self._global_growth_modifier = 1.0
        self._growth_timer = self._rng.randint(self.BASE_GROWTH_DELAY // 3, self.BASE_GROWTH_DELAY)
        self._recalculate_aggregates()
        self.set_size()

    def _recalculate_aggregates(self) -> None:
        if not self.cells:
            self.resource = 0.0
            self.color = (68, 132, 88)
            return

        total_nutrition = sum(dna.nutrition for dna in self.cells.values())
        self.resource = float(total_nutrition)
        count = len(self.cells)
        avg_color = (
            sum(dna.color[0] for dna in self.cells.values()) / count,
            sum(dna.color[1] for dna in self.cells.values()) / count,
            sum(dna.color[2] for dna in self.cells.values()) / count,
        )
        self.color = (
            int(_clamp(avg_color[0], 32, 220)),
            int(_clamp(avg_color[1], 32, 220)),
            int(_clamp(avg_color[2], 32, 220)),
        )

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    def set_size(self) -> None:
        if not self.cells:
            self.rect = pygame.Rect(0, 0, 0, 0)
            self.width = 0
            self.height = 0
            self.x = 0.0
            self.y = 0.0
            self.surface = pygame.Surface((0, 0), pygame.SRCALPHA)
            self._dirty = False
            return

        min_x = min(cell[0] for cell in self.cells)
        max_x = max(cell[0] for cell in self.cells)
        min_y = min(cell[1] for cell in self.cells)
        max_y = max(cell[1] for cell in self.cells)

        width = (max_x - min_x + 1) * self.CELL_SIZE
        height = (max_y - min_y + 1) * self.CELL_SIZE
        topleft = (min_x * self.CELL_SIZE, min_y * self.CELL_SIZE)

        self.rect = pygame.Rect(topleft, (width, height))
        self.width = width
        self.height = height
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self._dirty = True

    def contains_point(self, x: float, y: float) -> bool:
        if not self.cells:
            return False
        if not self.rect.collidepoint(int(x), int(y)):
            return False
        gx = int(x) // self.CELL_SIZE
        gy = int(y) // self.CELL_SIZE
        return (gx, gy) in self.cells

    def blocks_rect(self, rect: pygame.Rect) -> bool:
        if not self.cells or not self.rect.colliderect(rect):
            return False

        cell_left = rect.left // self.CELL_SIZE
        cell_right = (rect.right - 1) // self.CELL_SIZE
        cell_top = rect.top // self.CELL_SIZE
        cell_bottom = (rect.bottom - 1) // self.CELL_SIZE

        for gx in range(cell_left, cell_right + 1):
            for gy in range(cell_top, cell_bottom + 1):
                if (gx, gy) in self.cells:
                    return True
        return False

    def occupies_cell(self, cell: GridCell) -> bool:
        return cell in self.cells

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _rebuild_surface(self) -> None:
        if not self.cells:
            self.surface = pygame.Surface((0, 0), pygame.SRCALPHA)
            self._dirty = False
            return

        self.surface = pygame.Surface(self.rect.size, pygame.SRCALPHA)

        for (gx, gy), dna in self.cells.items():
            px = gx * self.CELL_SIZE - self.rect.left
            py = gy * self.CELL_SIZE - self.rect.top
            color = tuple(int(_clamp(channel, 24, 220)) for channel in dna.color)
            pygame.draw.rect(
                self.surface,
                color,
                pygame.Rect(px, py, self.CELL_SIZE, self.CELL_SIZE),
            )

        self._dirty = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.cells:
            return
        if self._dirty:
            self._rebuild_surface()
        surface.blit(self.surface, self.rect.topleft)

    # ------------------------------------------------------------------
    # Resource & regrowth
    # ------------------------------------------------------------------
    def set_capacity_multiplier(self, multiplier: float) -> None:
        self._environment_multiplier = max(0.1, multiplier)

    def set_growth_speed_modifier(self, modifier: float) -> None:
        self._global_growth_modifier = max(0.1, modifier)

    def decrement_resource(self, amount: float, *, eater: Optional["Lifeform"] = None) -> None:
        if not self.cells:
            return

        removal_order = list(self.cells.keys())

        if eater is not None:
            center = eater.rect.center
            removal_order.sort(key=lambda cell: _distance_sq_to_point(cell, center, self.CELL_SIZE))
        else:
            self._rng.shuffle(removal_order)

        min_nutrition = min(dna.nutrition for dna in self.cells.values()) if self.cells else 0.0
        target_nutrition = max(min_nutrition, float(amount))

        consumed = 0.0
        removed = 0
        while removal_order and (consumed < target_nutrition or removed == 0):
            cell = removal_order.pop(0)
            dna = self.cells.pop(cell, None)
            if dna is None:
                continue
            consumed += dna.nutrition
            removed += 1

        self._recalculate_aggregates()
        self.set_size()

    def regrow(self, world: "World", others: Sequence["MossCluster"]) -> None:
        if not self.cells:
            return

        if self._growth_timer > 0:
            self._growth_timer -= 1
            return

        center_x = self.rect.centerx
        center_y = self.rect.centery
        biome_multiplier = world.get_regrowth_modifier(center_x, center_y)
        total_multiplier = max(
            0.05,
            self._environment_multiplier
            * biome_multiplier
            * self._global_growth_modifier
            * self._average_growth_rate(),
        )
        self._growth_timer = max(6, int(self.BASE_GROWTH_DELAY / total_multiplier))

        candidates = self._gather_growth_candidates(world, others)
        if not candidates:
            return

        new_cell = self._rng.choice(candidates)
        self.cells[new_cell] = self._create_offspring_dna(new_cell)
        self._recalculate_aggregates()
        self.set_size()

    def _gather_growth_candidates(self, world: "World", others: Sequence["MossCluster"]) -> List[GridCell]:
        candidates: Set[GridCell] = set()
        for gx, gy in self.cells:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = gx + dx, gy + dy
                if (nx, ny) in self.cells:
                    continue
                cell_rect = pygame.Rect(
                    nx * self.CELL_SIZE,
                    ny * self.CELL_SIZE,
                    self.CELL_SIZE,
                    self.CELL_SIZE,
                )
                if (
                    cell_rect.left < 0
                    or cell_rect.top < 0
                    or cell_rect.right > world.width
                    or cell_rect.bottom > world.height
                ):
                    continue
                if world.is_blocked(cell_rect):
                    continue
                if any(other is not self and other.occupies_cell((nx, ny)) for other in others):
                    continue
                candidates.add((nx, ny))
        return list(candidates)

    def _average_growth_rate(self) -> float:
        if not self.cells:
            return 1.0
        return sum(dna.growth_rate for dna in self.cells.values()) / len(self.cells)

    def _create_offspring_dna(self, cell: GridCell) -> MossDNA:
        neighbors = list(self._neighbor_dnas(cell))
        return average_dna(neighbors, self._rng)

    def _neighbor_dnas(self, cell: GridCell) -> Iterable[MossDNA]:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (cell[0] + dx, cell[1] + dy)
            dna = self.cells.get(neighbor)
            if dna is not None:
                yield dna

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------
    def movement_modifier_for(self, _lifeform: "Lifeform") -> float:
        # Clusters are impassable. Movement resolution handles blocking; this
        # method simply exists for backwards compatibility.
        return 0.0

    def apply_effect(self, lifeform: "Lifeform") -> None:
        dna = self._nearest_cell_dna(lifeform)
        if dna is None:
            return

        base_energy = dna.nutrition * (1.0 + dna.hydration * 0.4)
        toxin_energy = dna.toxicity * 8.0
        net_energy = base_energy - toxin_energy
        if net_energy >= 0:
            lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + net_energy)
        else:
            lifeform.energy_now = max(0.0, lifeform.energy_now + net_energy)

        heal_amount = dna.vitality * 12.0
        toxin_damage = dna.toxicity * 16.0
        health_delta = heal_amount - toxin_damage
        if health_delta >= 0:
            lifeform.health_now = min(lifeform.health, lifeform.health_now + health_delta)
        else:
            lifeform.health_now = max(0.0, lifeform.health_now + health_delta)

        soothing = dna.hydration * 4.0
        lifeform.wounded = max(0.0, lifeform.wounded - soothing)
        if toxin_damage > 0:
            lifeform.wounded += toxin_damage * 0.1

        satiety_bonus = dna.fiber_density * 8.0
        lifeform.hunger = max(0.0, lifeform.hunger - satiety_bonus)

    def _nearest_cell_dna(self, lifeform: "Lifeform") -> Optional[MossDNA]:
        if not self.cells:
            return None
        center = lifeform.rect.center
        closest_cell = min(
            self.cells.keys(),
            key=lambda cell: _distance_sq_to_point(cell, center, self.CELL_SIZE),
        )
        return self.cells.get(closest_cell)


def _distance_sq_to_point(cell: GridCell, point: Tuple[int, int], cell_size: int) -> float:
    cell_center = (
        cell[0] * cell_size + cell_size / 2,
        cell[1] * cell_size + cell_size / 2,
    )
    dx = cell_center[0] - point[0]
    dy = cell_center[1] - point[1]
    return dx * dx + dy * dy


def _generate_seed_cells(
    world: "World",
    *,
    existing_cells: Set[GridCell],
    min_cells: int,
    max_cells: int,
    rng: Optional[random.Random] = None,
) -> Optional[Set[GridCell]]:
    rng = rng or random.Random()
    cell_size = MossCluster.CELL_SIZE
    max_attempts = 240
    attempts = 0

    while attempts < max_attempts:
        attempts += 1
        gx = rng.randrange(0, world.width // cell_size)
        gy = rng.randrange(0, world.height // cell_size)
        if (gx, gy) in existing_cells:
            continue
        rect = pygame.Rect(gx * cell_size, gy * cell_size, cell_size, cell_size)
        if world.is_blocked(rect):
            continue

        cells: Set[GridCell] = {(gx, gy)}
        target_size = rng.randint(min_cells, max_cells)
        stagnation = 0

        while len(cells) < target_size and stagnation < target_size * 10:
            stagnation += 1
            base_cell = rng.choice(tuple(cells))
            dx, dy = rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
            candidate = (base_cell[0] + dx, base_cell[1] + dy)
            if candidate in cells or candidate in existing_cells:
                continue
            px = candidate[0] * cell_size
            py = candidate[1] * cell_size
            candidate_rect = pygame.Rect(px, py, cell_size, cell_size)
            if (
                candidate_rect.left < 0
                or candidate_rect.top < 0
                or candidate_rect.right > world.width
                or candidate_rect.bottom > world.height
            ):
                continue
            if world.is_blocked(candidate_rect):
                continue
            cells.add(candidate)
            stagnation = 0

        if len(cells) >= min_cells:
            return cells

    return None


def create_initial_clusters(
    world: "World",
    *,
    count: int = 4,
    min_cells: int = 18,
    max_cells: int = 48,
    rng: Optional[random.Random] = None,
) -> List[MossCluster]:
    rng = rng or random.Random()
    clusters: List[MossCluster] = []
    occupied: Set[GridCell] = set()

    for _ in range(count):
        cells = _generate_seed_cells(
            world,
            existing_cells=occupied,
            min_cells=min_cells,
            max_cells=max_cells,
            rng=rng,
        )
        if not cells:
            break
        occupied.update(cells)
        dna_cells = ensure_dna_for_cells(cells, rng)
        clusters.append(MossCluster(dna_cells))

    return clusters


__all__ = ["MossCluster", "create_initial_clusters"]
