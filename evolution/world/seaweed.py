"""Neutral-buoyant seaweed strands that replace grid-based moss clusters."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import ClassVar, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import pygame
from pygame.math import Vector2

from ..config import settings
from .moss_dna import MossDNA, ensure_dna_for_cells, random_moss_dna

GridCell = Tuple[int, int]

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

STRAND_MIN_LENGTH = 12
STRAND_MAX_LENGTH = 58
STRAND_BRANCH_ODDS = 0.2
STRAND_SWAY_SPEED = 0.25
STRAND_SWAY_RANGE = 9.0


@dataclass(slots=True)
class SeaweedCellState:
    dna: MossDNA
    alive: bool = True
    oxygen_deprivation_frames: int = 0
    _stored_nutrition: float = field(init=False, repr=False)

    DEAD_COLOR: ClassVar[Tuple[int, int, int]] = (90, 90, 90)

    def __post_init__(self) -> None:
        self._stored_nutrition = float(self.dna.nutrition)

    def apply_oxygen_state(self, has_oxygen: bool) -> bool:
        previous_alive = self.alive
        if has_oxygen:
            self.oxygen_deprivation_frames = 0
            self.alive = True
            self._stored_nutrition = max(self._stored_nutrition, self.dna.nutrition)
        else:
            self.oxygen_deprivation_frames += 1
            if self.oxygen_deprivation_frames >= int(settings.FPS * 60):
                self.alive = False
        if not self.alive:
            self._stored_nutrition = min(self._stored_nutrition, self.dna.nutrition * 0.25)
        return previous_alive != self.alive

    @property
    def nutrition(self) -> float:
        return self._stored_nutrition

    @property
    def color(self) -> Tuple[int, int, int]:
        return self.dna.color if self.alive else self.DEAD_COLOR


@dataclass(slots=True)
class SeaweedStrand:
    cells: Mapping[GridCell, MossDNA | SeaweedCellState] | Iterable[GridCell]
    color: Tuple[int, int, int] = (58, 150, 118)
    CELL_SIZE: ClassVar[int] = 8
    BASE_GROWTH_DELAY: ClassVar[int] = 220

    surface: pygame.Surface = field(init=False, repr=False)
    rect: pygame.Rect = field(init=False)
    width: int = field(init=False)
    height: int = field(init=False)
    x: float = field(init=False)
    y: float = field(init=False)
    resource: float = field(init=False)
    _rng: random.Random = field(init=False, repr=False)
    _dirty: bool = field(init=False, repr=False)
    _growth_timer: int = field(init=False, repr=False)
    _env_multiplier: float = field(init=False, repr=False)
    _growth_modifier: float = field(init=False, repr=False)
    _offset: Vector2 = field(init=False, repr=False)
    _base_rect: pygame.Rect = field(init=False, repr=False)
    _sway_phase: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        raw_cells = self.cells
        self._rng = random.Random()
        if isinstance(raw_cells, Mapping):
            cell_map: Dict[GridCell, SeaweedCellState] = {}
            for cell, dna in raw_cells.items():
                gx, gy = int(cell[0]), int(cell[1])
                if isinstance(dna, SeaweedCellState):
                    cell_state = dna
                else:
                    dna = dna if isinstance(dna, MossDNA) else random_moss_dna(self._rng)
                    cell_state = SeaweedCellState(dna)
                cell_map[(gx, gy)] = cell_state
        else:
            dna_map = ensure_dna_for_cells(tuple(raw_cells), self._rng)
            cell_map = {cell: SeaweedCellState(dna) for cell, dna in dna_map.items()}
        self.cells = cell_map
        self.surface = pygame.Surface((0, 0), pygame.SRCALPHA)
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.width = 0
        self.height = 0
        self.x = 0.0
        self.y = 0.0
        self._base_rect = self.rect
        self.resource = 0.0
        self._dirty = True
        self._env_multiplier = 1.0
        self._growth_modifier = 1.0
        self._growth_timer = self._rng.randint(self.BASE_GROWTH_DELAY // 2, self.BASE_GROWTH_DELAY)
        self._offset = Vector2()
        self._sway_phase = self._rng.uniform(0.0, math.tau)
        self._recalculate()
        self._update_rect()

    # ------------------------------------------------------------------
    def _recalculate(self) -> None:
        if not self.cells:
            self.resource = 0.0
            self.color = (58, 150, 118)
            return
        total = sum(cell.nutrition for cell in self.cells.values())
        self.resource = float(total)
        count = len(self.cells)
        avg_color = (
            sum(cell.color[0] for cell in self.cells.values()) / count,
            sum(cell.color[1] for cell in self.cells.values()) / count,
            sum(cell.color[2] for cell in self.cells.values()) / count,
        )
        self.color = tuple(int(max(32, min(220, ch))) for ch in avg_color)
        self._dirty = True

    def _update_rect(self) -> None:
        if not self.cells:
            self.rect = pygame.Rect(0, 0, 0, 0)
            self.width = 0
            self.height = 0
            self.x = 0.0
            self.y = 0.0
            self._base_rect = self.rect
            return
        min_x = min(cell[0] for cell in self.cells)
        max_x = max(cell[0] for cell in self.cells)
        min_y = min(cell[1] for cell in self.cells)
        max_y = max(cell[1] for cell in self.cells)
        base = pygame.Rect(
            min_x * self.CELL_SIZE,
            min_y * self.CELL_SIZE,
            (max_x - min_x + 1) * self.CELL_SIZE,
            (max_y - min_y + 1) * self.CELL_SIZE,
        )
        self._base_rect = base
        self.rect = base.move(int(self._offset.x), int(self._offset.y))
        self.width = self.rect.width
        self.height = self.rect.height
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

    def set_size(self) -> None:
        """Compatibility helper used by the simulation bootstrap."""
        if not self.cells:
            self.rect = pygame.Rect(0, 0, 0, 0)
            self.width = 0
            self.height = 0
            self.x = 0.0
            self.y = 0.0
            self._base_rect = self.rect
            self.surface = pygame.Surface((0, 0), pygame.SRCALPHA)
            self._dirty = False
            return

        self._update_rect()
        # Surface will be resized lazily on the next draw call.
        self._dirty = True

    def update_current(self, world: "World", dt: float) -> None:
        ocean = getattr(world, "ocean", None)
        if ocean is None or not self.cells:
            return
        props = ocean.properties_at(self.rect.centery)
        sway = math.sin(self._sway_phase) * STRAND_SWAY_RANGE
        self._sway_phase += STRAND_SWAY_SPEED * dt
        self._offset = Vector2(props.current.x * 0.1 + sway, props.current.y * 0.05)
        self.rect = self._base_rect.move(int(self._offset.x), int(self._offset.y))
        self.width = self.rect.width
        self.height = self.rect.height
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.cells:
            return
        if self._dirty:
            self._rebuild_surface()
        surface.blit(self.surface, self.rect.topleft)

    def _rebuild_surface(self) -> None:
        if not self.cells:
            self.surface = pygame.Surface((0, 0), pygame.SRCALPHA)
            self._dirty = False
            return
        self.surface = pygame.Surface(self._base_rect.size, pygame.SRCALPHA)
        for (gx, gy), cell in self.cells.items():
            px = gx * self.CELL_SIZE - self._base_rect.left
            py = gy * self.CELL_SIZE - self._base_rect.top
            color = tuple(int(max(24, min(235, channel))) for channel in cell.color)
            pygame.draw.rect(
                self.surface,
                (*color, 220),
                pygame.Rect(px, py, self.CELL_SIZE, self.CELL_SIZE),
            )
        self._dirty = False

    def set_capacity_multiplier(self, multiplier: float) -> None:
        self._env_multiplier = max(0.1, multiplier)
        for cell in self.cells.values():
            cell._stored_nutrition = max(0.1, cell.dna.nutrition * self._env_multiplier)
        self.resource = sum(cell.nutrition for cell in self.cells.values())

    def set_growth_speed_modifier(self, modifier: float) -> None:
        self._growth_modifier = max(0.1, modifier)

    def regrow(self, world: "World", others: Sequence["SeaweedStrand"]) -> None:
        if not self.cells:
            return
        _ = world  # strand growth not yet simulated; placeholder hook
        _ = others

    def blocks_rect(self, rect: pygame.Rect) -> bool:
        if not self.cells:
            return False
        shifted = rect.move(-int(self._offset.x), -int(self._offset.y))
        if not self._base_rect.colliderect(shifted):
            return False
        cell_left = shifted.left // self.CELL_SIZE
        cell_right = (shifted.right - 1) // self.CELL_SIZE
        cell_top = shifted.top // self.CELL_SIZE
        cell_bottom = (shifted.bottom - 1) // self.CELL_SIZE
        for gx in range(cell_left, cell_right + 1):
            for gy in range(cell_top, cell_bottom + 1):
                if (gx, gy) in self.cells:
                    return True
        return False

    def contains_point(self, x: float, y: float) -> bool:
        if not self.cells:
            return False
        local = Vector2(x, y) - self._offset
        if not self._base_rect.collidepoint(int(local.x), int(local.y)):
            return False
        gx = int(local.x) // self.CELL_SIZE
        gy = int(local.y) // self.CELL_SIZE
        return (gx, gy) in self.cells

    def occupies_cell(self, cell: GridCell) -> bool:
        """Compatibility helper so moss oxygen checks see seaweed occupancy."""
        return cell in self.cells

    def decrement_resource(
        self, amount: float, *, eater: Optional["Lifeform"] = None
    ) -> List["ConsumptionSample"]:
        from .vegetation import ConsumptionSample  # lazy import to avoid cycle

        if not self.cells or amount <= 0:
            return []
        order = list(self.cells.keys())
        if eater is not None:
            center = eater.rect.center
            order.sort(key=lambda cell: _distance_sq_to_point(cell, center, self.CELL_SIZE))
        else:
            self._rng.shuffle(order)
        consumed = 0.0
        removed = 0
        samples: List[ConsumptionSample] = []
        while order and (consumed < amount or removed == 0):
            cell = order.pop(0)
            state = self.cells.pop(cell, None)
            if state is None:
                continue
            consumed += state.nutrition
            removed += 1
            samples.append(ConsumptionSample(state.dna, state.nutrition, state.alive))
        if removed:
            self._recalculate()
            self._update_rect()
        return samples

    def apply_effect(
        self, lifeform: "Lifeform", consumption: Sequence["ConsumptionSample"]
    ) -> "ConsumptionOutcome":
        from .vegetation import ConsumptionOutcome

        if not consumption:
            return ConsumptionOutcome()
        energy = 0.0
        toxins = 0.0
        satiety = 0.0
        soothing = 0.0
        for sample in consumption:
            nutrition = sample.nutrition
            dna = sample.dna
            energy += nutrition * (1.2 + dna.hydration * 0.4)
            toxins += nutrition * dna.toxicity * 0.2
            satiety += dna.fiber_density * 5.0
            soothing += dna.hydration * 3.0
        net = energy - toxins
        lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + net)
        lifeform.hunger = max(
            settings.HUNGER_MINIMUM,
            lifeform.hunger - net * settings.PLANT_HUNGER_SATIATION_PER_NUTRITION - satiety,
        )
        lifeform.wounded = max(0.0, lifeform.wounded - soothing)
        return ConsumptionOutcome(
            satiety_bonus=satiety,
            health_delta=0.0,
            energy_delta=net,
            toxin_damage=max(0.0, toxins),
        )

    def movement_modifier_for(self, _lifeform: "Lifeform") -> float:
        return 0.0

    def core_radius(self) -> float:
        return max(6.0, max(self.rect.width, self.rect.height) * 0.3)


def _distance_sq_to_point(cell: GridCell, point: Tuple[int, int], cell_size: int) -> float:
    cx = cell[0] * cell_size + cell_size / 2
    cy = cell[1] * cell_size + cell_size / 2
    dx = cx - point[0]
    dy = cy - point[1]
    return dx * dx + dy * dy


def create_initial_strands(
    world: "World",
    *,
    count: int = 32,
    min_cells: int = STRAND_MIN_LENGTH,
    max_cells: int = STRAND_MAX_LENGTH,
    rng: Optional[random.Random] = None,
) -> List[SeaweedStrand]:
    rng = rng or random.Random()
    strands: List[SeaweedStrand] = []
    occupied: Set[GridCell] = set()
    for _ in range(count):
        cells = _generate_seed_cells(
            world,
            existing_cells=occupied,
            min_cells=min_cells,
            max_cells=max_cells,
            rng=rng,
            allowed_biomes={"Sunlit", "Twilight"},
        )
        if not cells:
            break
        occupied.update(cells)
        dna_map = ensure_dna_for_cells(cells, rng)
        strands.append(SeaweedStrand(dna_map))
    return strands


def create_strand_from_brush(
    world: "World",
    center: Tuple[float, float],
    radius_px: int,
    *,
    density: float = 0.85,
    rng: Optional[random.Random] = None,
) -> Optional[SeaweedStrand]:
    rng = rng or random.Random()
    radius_px = max(SeaweedStrand.CELL_SIZE, int(radius_px))
    cx = max(0, min(int(center[0]), world.width - 1))
    cy = max(0, min(int(center[1]), world.height - 1))
    cell_size = SeaweedStrand.CELL_SIZE
    cells: Set[GridCell] = set()
    brush_sq = radius_px * radius_px
    for gx in range((cx - radius_px) // cell_size, (cx + radius_px) // cell_size + 1):
        for gy in range((cy - radius_px) // cell_size, (cy + radius_px) // cell_size + 1):
            if gx < 0 or gy < 0:
                continue
            px = gx * cell_size
            py = gy * cell_size
            rect = pygame.Rect(px, py, cell_size, cell_size)
            if rect.right > world.width or rect.bottom > world.height:
                continue
            if world.is_blocked(rect):
                continue
            dx = px + cell_size / 2 - cx
            dy = py + cell_size / 2 - cy
            if dx * dx + dy * dy > brush_sq:
                continue
            if density < 1.0 and rng.random() > density:
                continue
            cells.add((gx, gy))
    if not cells:
        return None
    dna_map = ensure_dna_for_cells(tuple(cells), rng)
    return SeaweedStrand(dna_map)


def _generate_seed_cells(
    world: "World",
    *,
    existing_cells: Set[GridCell],
    min_cells: int,
    max_cells: int,
    rng: Optional[random.Random] = None,
    allowed_biomes: Optional[Set[str]] = None,
) -> Optional[Set[GridCell]]:
    rng = rng or random.Random()
    cell_size = SeaweedStrand.CELL_SIZE
    attempts = 0
    seed_mask: Optional[pygame.Rect] = None
    while attempts < 200:
        attempts += 1
        origin = _select_seed_origin(world, rng, cell_size, allowed_biomes)
        if origin is not None:
            gx, gy, seed_mask = origin
        else:
            gx = rng.randrange(0, world.width // cell_size)
            gy = rng.randrange(0, world.height // cell_size)
        if (gx, gy) in existing_cells:
            continue
        rect = pygame.Rect(gx * cell_size, gy * cell_size, cell_size, cell_size)
        if world.is_blocked(rect):
            continue
        if seed_mask and not seed_mask.contains(rect):
            continue
        cells: Set[GridCell] = {(gx, gy)}
        target = rng.randint(min_cells, max_cells)
        direction = Vector2(rng.uniform(-0.4, 0.4), rng.uniform(0.7, 1.3))
        if direction.length_squared() == 0:
            direction = Vector2(0, 1)
        direction = direction.normalize()
        while len(cells) < target:
            head = max(cells, key=lambda cell: cell[1])
            choices = _directional_neighbors(head, direction)
            placed = False
            for nx, ny in choices:
                if (nx, ny) in cells or (nx, ny) in existing_cells:
                    continue
                px = nx * cell_size
                py = ny * cell_size
                candidate = pygame.Rect(px, py, cell_size, cell_size)
                if (
                    candidate.left < 0
                    or candidate.top < 0
                    or candidate.right > world.width
                    or candidate.bottom > world.height
                    or world.is_blocked(candidate)
                ):
                    continue
                if seed_mask and not seed_mask.contains(candidate):
                    continue
                cells.add((nx, ny))
                direction = Vector2(nx - head[0], ny - head[1]).normalize()
                placed = True
                if rng.random() < STRAND_BRANCH_ODDS:
                    side = Vector2(direction.y, -direction.x)
                    branch = (nx + int(side.x), ny + int(side.y))
                    if branch not in cells and branch not in existing_cells:
                        bx = branch[0] * cell_size
                        by = branch[1] * cell_size
                        branch_rect = pygame.Rect(bx, by, cell_size, cell_size)
                        if (
                            branch_rect.left >= 0
                            and branch_rect.top >= 0
                            and branch_rect.right <= world.width
                            and branch_rect.bottom <= world.height
                            and not world.is_blocked(branch_rect)
                        ):
                            cells.add(branch)
                break
            if not placed:
                break
        if len(cells) >= min_cells:
            return cells
    return None


def _directional_neighbors(cell: GridCell, direction: Vector2) -> List[GridCell]:
    neighbors: List[Tuple[float, GridCell]] = []
    for dx, dy in NEIGHBOR_OFFSETS:
        vec = Vector2(dx, dy)
        score = vec.normalize().dot(direction) if vec.length_squared() else -1.0
        neighbors.append((score, (cell[0] + dx, cell[1] + dy)))
    neighbors.sort(key=lambda item: item[0], reverse=True)
    return [cell for _, cell in neighbors]


def _select_seed_origin(
    world: "World",
    rng: random.Random,
    cell_size: int,
    allowed_biomes: Optional[Set[str]] = None,
) -> Optional[Tuple[int, int, pygame.Rect]]:
    if not getattr(world, "vegetation_masks", None):
        return None
    masks = list(world.vegetation_masks)
    if allowed_biomes:
        filtered: List[pygame.Rect] = []
        for mask in masks:
            biome = world.get_biome_at(mask.centerx, mask.centery)
            if biome and biome.name in allowed_biomes:
                filtered.append(mask)
        if filtered:
            masks = filtered
    if not masks:
        return None
    mask = rng.choice(masks)
    px = rng.randint(mask.left, max(mask.left, mask.right - cell_size))
    py = rng.randint(mask.top, max(mask.top, mask.bottom - cell_size))
    return px // cell_size, py // cell_size, mask


__all__ = [
    "SeaweedCellState",
    "SeaweedStrand",
    "create_initial_strands",
    "create_strand_from_brush",
]

