"""Procedural moss clusters that act as food sources in the world."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import ClassVar, List, Optional, Sequence, Set, Tuple

import pygame


GridCell = Tuple[int, int]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@dataclass(slots=True)
class MossCluster:
    """A slowly growing moss cluster composed of 2x2 cells."""

    cells: Set[GridCell]
    color: Tuple[int, int, int] = (68, 132, 88)
    CELL_SIZE: ClassVar[int] = 2
    CELL_NUTRITION: ClassVar[float] = 12.0
    BASE_GROWTH_DELAY: ClassVar[int] = 240

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

    def __post_init__(self) -> None:
        self.cells = set(self.cells)
        self.surface = pygame.Surface((0, 0), pygame.SRCALPHA)
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.width = 0
        self.height = 0
        self.x = 0.0
        self.y = 0.0
        self.resource: float = float(len(self.cells) * self.CELL_NUTRITION)
        self._dirty = True
        self._environment_multiplier = 1.0
        self._growth_timer = random.randint(self.BASE_GROWTH_DELAY // 2, self.BASE_GROWTH_DELAY)
        self.set_size()

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
        color_variation = random.randint(-10, 10)
        tint = tuple(
            int(_clamp(channel + color_variation, 32, 200))
            for channel in self.color
        )

        for gx, gy in self.cells:
            px = gx * self.CELL_SIZE - self.rect.left
            py = gy * self.CELL_SIZE - self.rect.top
            pygame.draw.rect(
                self.surface,
                tint,
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

    def decrement_resource(self, amount: float, *, eater: Optional["Lifeform"] = None) -> None:
        if not self.cells or amount <= 0:
            return

        cells_to_remove = max(1, int(math.ceil(amount / self.CELL_NUTRITION)))
        removal_order = list(self.cells)

        if eater is not None:
            center = eater.rect.center
            removal_order.sort(key=lambda cell: _distance_sq_to_point(cell, center, self.CELL_SIZE))
        else:
            random.shuffle(removal_order)

        removed = 0
        for cell in removal_order:
            self.cells.remove(cell)
            removed += 1
            if removed >= cells_to_remove:
                break

        self.resource = float(len(self.cells) * self.CELL_NUTRITION)
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
        total_multiplier = max(0.05, self._environment_multiplier * biome_multiplier)
        self._growth_timer = max(12, int(self.BASE_GROWTH_DELAY / total_multiplier))

        candidates = self._gather_growth_candidates(world, others)
        if not candidates:
            return

        new_cell = random.choice(candidates)
        self.cells.add(new_cell)
        self.resource = float(len(self.cells) * self.CELL_NUTRITION)
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

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------
    def movement_modifier_for(self, _lifeform: "Lifeform") -> float:
        # Clusters are impassable. Movement resolution handles blocking; this
        # method simply exists for backwards compatibility.
        return 0.0

    def apply_effect(self, lifeform: "Lifeform") -> None:
        lifeform.health_now = min(lifeform.health, lifeform.health_now + 10)
        lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + 15)


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
        clusters.append(MossCluster(cells))

    return clusters


__all__ = ["MossCluster", "create_initial_clusters"]
