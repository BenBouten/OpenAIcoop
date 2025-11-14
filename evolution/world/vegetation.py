"""Procedural moss clusters that act as food sources in the world."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import ClassVar, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import pygame


GridCell = Tuple[int, int]

from .moss_dna import MossDNA, average_dna, ensure_dna_for_cells, random_moss_dna
from ..config import settings


NEIGHBOR_OFFSETS: Tuple[Tuple[int, int], ...] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)

ORTHOGONAL_OFFSETS: Tuple[Tuple[int, int], ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))

OXYGEN_DEPRIVATION_LIMIT = int(settings.FPS * 60)
DEAD_NUTRITION_MULTIPLIER = 0.2


@dataclass(slots=True)
class MossCellState:
    dna: MossDNA
    alive: bool = True
    oxygen_deprivation_frames: int = 0
    _stored_nutrition: float = field(init=False, repr=False)

    DEAD_COLOR: ClassVar[Tuple[int, int, int]] = (96, 96, 96)

    def __post_init__(self) -> None:
        base = self.dna.nutrition
        self._stored_nutrition = float(base)

    def apply_oxygen_state(self, has_oxygen: bool) -> bool:
        previous_alive = self.alive
        if has_oxygen:
            self.oxygen_deprivation_frames = 0
            self.alive = True
            self._stored_nutrition = max(self._stored_nutrition, self.dna.nutrition)
        else:
            self.oxygen_deprivation_frames += 1
            if self.oxygen_deprivation_frames >= OXYGEN_DEPRIVATION_LIMIT:
                self.alive = False
        if not self.alive:
            self._stored_nutrition = min(
                self._stored_nutrition, self.dna.nutrition * DEAD_NUTRITION_MULTIPLIER
            )
        return previous_alive != self.alive

    @property
    def nutrition(self) -> float:
        return self._stored_nutrition

    @property
    def color(self) -> Tuple[int, int, int]:
        return self.dna.color if self.alive else self.DEAD_COLOR


@dataclass(slots=True)
class ConsumptionSample:
    """Information about a single moss cell that was eaten."""

    dna: MossDNA
    nutrition: float
    alive: bool


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@dataclass(slots=True)
class MossCluster:
    """A slowly growing moss cluster composed of 2x2 cells."""

    cells: Mapping[GridCell, MossDNA | MossCellState] | Iterable[GridCell]
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
            cell_map: Dict[GridCell, MossCellState] = {}
            for cell, dna in raw_cells.items():
                gx, gy = int(cell[0]), int(cell[1])
                if isinstance(dna, MossCellState):
                    cell_state = dna
                else:
                    if not isinstance(dna, MossDNA):
                        dna = random_moss_dna(self._rng)
                    cell_state = MossCellState(dna)
                cell_map[(gx, gy)] = cell_state
        else:
            dna_map = ensure_dna_for_cells(tuple(raw_cells), self._rng)
            cell_map = {cell: MossCellState(dna) for cell, dna in dna_map.items()}

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

        total_nutrition = sum(cell.nutrition for cell in self.cells.values())
        self.resource = float(total_nutrition)
        count = len(self.cells)
        avg_color = (
            sum(cell.color[0] for cell in self.cells.values()) / count,
            sum(cell.color[1] for cell in self.cells.values()) / count,
            sum(cell.color[2] for cell in self.cells.values()) / count,
        )
        self.color = (
            int(_clamp(avg_color[0], 32, 220)),
            int(_clamp(avg_color[1], 32, 220)),
            int(_clamp(avg_color[2], 32, 220)),
        )
        self._dirty = True

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

        for (gx, gy), cell in self.cells.items():
            px = gx * self.CELL_SIZE - self.rect.left
            py = gy * self.CELL_SIZE - self.rect.top
            color = tuple(int(_clamp(channel, 24, 220)) for channel in cell.color)
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

    def decrement_resource(
        self, amount: float, *, eater: Optional["Lifeform"] = None
    ) -> List[ConsumptionSample]:
        if not self.cells or amount <= 0:
            return []

        removal_order = list(self.cells.keys())

        if eater is not None:
            center = eater.rect.center
            removal_order.sort(key=lambda cell: _distance_sq_to_point(cell, center, self.CELL_SIZE))
        else:
            self._rng.shuffle(removal_order)

        min_nutrition = (
            min(cell.nutrition for cell in self.cells.values()) if self.cells else 0.0
        )
        target_nutrition = max(min_nutrition, float(amount))

        consumed = 0.0
        removed = 0
        samples: List[ConsumptionSample] = []
        while removal_order and (consumed < target_nutrition or removed == 0):
            cell = removal_order.pop(0)
            state = self.cells.pop(cell, None)
            if state is None:
                continue
            nutrition = state.nutrition
            consumed += nutrition
            removed += 1
            samples.append(ConsumptionSample(state.dna, nutrition, state.alive))

        if removed:
            self._recalculate_aggregates()
            self.set_size()

        return samples

    def regrow(self, world: "World", others: Sequence["MossCluster"]) -> None:
        if not self.cells:
            return

        if self._update_cell_life_state(world, others):
            self._recalculate_aggregates()

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

        opportunities = self._reproduction_opportunities(world, others)
        if not opportunities:
            return

        indices = list(range(len(opportunities)))
        weights = [opportunity[2] for opportunity in opportunities]
        selected_index = self._rng.choices(indices, weights=weights, k=1)[0]
        _, empty_neighbors, _ = opportunities[selected_index]
        new_cell = self._rng.choice(empty_neighbors)
        if new_cell in self.cells:
            return
        self.cells[new_cell] = MossCellState(self._create_offspring_dna(new_cell))
        self._recalculate_aggregates()
        self.set_size()

    def _reproduction_opportunities(
        self, world: "World", others: Sequence["MossCluster"]
    ) -> List[Tuple[GridCell, List[GridCell], float]]:
        opportunities: List[Tuple[GridCell, List[GridCell], float]] = []
        for cell, state in self.cells.items():
            if not state.alive:
                continue
            empty_neighbors = self._available_neighbor_cells(cell, world, others)
            if len(empty_neighbors) < 3:
                continue
            weight = max(0.1, state.dna.growth_rate)
            opportunities.append((cell, empty_neighbors, weight))
        return opportunities

    def _available_neighbor_cells(
        self, cell: GridCell, world: "World", others: Sequence["MossCluster"]
    ) -> List[GridCell]:
        empties: List[GridCell] = []
        for dx, dy in NEIGHBOR_OFFSETS:
            nx, ny = cell[0] + dx, cell[1] + dy
            neighbor = (nx, ny)
            if self._is_occupied(neighbor, world, others):
                continue
            empties.append(neighbor)
        return empties

    def _is_occupied(
        self, cell: GridCell, world: "World", others: Sequence["MossCluster"]
    ) -> bool:
        if cell in self.cells:
            return True

        cell_rect = pygame.Rect(
            cell[0] * self.CELL_SIZE,
            cell[1] * self.CELL_SIZE,
            self.CELL_SIZE,
            self.CELL_SIZE,
        )
        if (
            cell_rect.left < 0
            or cell_rect.top < 0
            or cell_rect.right > world.width
            or cell_rect.bottom > world.height
        ):
            return True
        if world.is_blocked(cell_rect):
            return True
        return any(other is not self and other.occupies_cell(cell) for other in others)

    def _update_cell_life_state(
        self, world: "World", others: Sequence["MossCluster"]
    ) -> bool:
        changed = False
        for cell, state in self.cells.items():
            has_oxygen = self._cell_has_oxygen(cell, world, others)
            if state.apply_oxygen_state(has_oxygen):
                changed = True
        return changed

    def _cell_has_oxygen(
        self, cell: GridCell, world: "World", others: Sequence["MossCluster"]
    ) -> bool:
        for dx, dy in NEIGHBOR_OFFSETS:
            neighbor = (cell[0] + dx, cell[1] + dy)
            if not self._is_occupied(neighbor, world, others):
                return True
        return False

    def _average_growth_rate(self) -> float:
        if not self.cells:
            return 1.0
        living = [cell for cell in self.cells.values() if cell.alive]
        if not living:
            return 0.0
        return sum(cell.dna.growth_rate for cell in living) / len(living)

    def _create_offspring_dna(self, cell: GridCell) -> MossDNA:
        neighbors = list(self._neighbor_dnas(cell))
        return average_dna(neighbors, self._rng)

    def _neighbor_dnas(self, cell: GridCell) -> Iterable[MossDNA]:
        for dx, dy in ORTHOGONAL_OFFSETS:
            neighbor = (cell[0] + dx, cell[1] + dy)
            state = self.cells.get(neighbor)
            if state is not None and state.alive:
                yield state.dna

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------
    def movement_modifier_for(self, _lifeform: "Lifeform") -> float:
        # Clusters are impassable. Movement resolution handles blocking; this
        # method simply exists for backwards compatibility.
        return 0.0

    def apply_effect(
        self, lifeform: "Lifeform", consumption: Sequence[ConsumptionSample]
    ) -> float:
        if not consumption:
            return 0.0

        energy_gain = 0.0
        toxin_energy = 0.0
        heal_amount = 0.0
        toxin_damage = 0.0
        soothing = 0.0
        satiety_bonus = 0.0

        for sample in consumption:
            nutrition = sample.nutrition
            if nutrition <= 0.0:
                continue
            dna = sample.dna
            cell_capacity = max(dna.nutrition, 1e-6)
            portion = nutrition / cell_capacity

            energy_gain += nutrition * (1.0 + dna.hydration * 0.4)
            toxin_energy += portion * dna.toxicity * 8.0
            heal_amount += portion * dna.vitality * 12.0
            toxin_damage += portion * dna.toxicity * 16.0
            soothing += portion * dna.hydration * 4.0
            satiety_bonus += portion * dna.fiber_density * 8.0

        net_energy = energy_gain - toxin_energy
        if net_energy >= 0:
            lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + net_energy)
        else:
            lifeform.energy_now = max(0.0, lifeform.energy_now + net_energy)

        health_delta = heal_amount - toxin_damage
        if health_delta >= 0:
            lifeform.health_now = min(lifeform.health, lifeform.health_now + health_delta)
        else:
            lifeform.health_now = max(0.0, lifeform.health_now + health_delta)

        lifeform.wounded = max(0.0, lifeform.wounded - soothing)
        if toxin_damage > 0:
            lifeform.wounded += toxin_damage * 0.1

        return satiety_bonus

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
    count: int = 32,
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


__all__ = ["MossCellState", "MossCluster", "create_initial_clusters"]
