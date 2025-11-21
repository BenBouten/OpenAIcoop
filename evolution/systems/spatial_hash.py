"""Spatial hash grid for efficient proximity queries.

This module provides a spatial partitioning data structure to optimize
entity lookups and proximity queries, reducing O(n²) to approximately O(n).
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Dict, Iterable, List, Set, Tuple

if TYPE_CHECKING:
    from ..entities.lifeform import Lifeform
    from ..world.vegetation import Plant


class SpatialHashGrid:
    """Spatial hash grid for fast proximity queries.
    
    Divides the world into a grid of cells. Each entity is stored in the cell(s)
    it overlaps with, allowing fast queries for nearby entities without checking
    all entities in the world.
    
    Args:
        cell_size: Size of each grid cell. Larger cells = fewer cells but more
                   entities per cell. Optimal size is typically 2-3x the average
                   query radius.
    """

    def __init__(self, cell_size: float = 200.0) -> None:
        self.cell_size = max(1.0, cell_size)
        self._lifeforms: Dict[Tuple[int, int], List[Lifeform]] = defaultdict(list)
        self._plants: Dict[Tuple[int, int], List[Plant]] = defaultdict(list)
        
    def clear(self) -> None:
        """Clear all entities from the grid."""
        self._lifeforms.clear()
        self._plants.clear()
        
    def _get_cell(self, x: float, y: float) -> Tuple[int, int]:
        """Get the grid cell coordinates for a world position."""
        return (int(x // self.cell_size), int(y // self.cell_size))
    
    def _get_cells_in_radius(self, x: float, y: float, radius: float) -> Set[Tuple[int, int]]:
        """Get all grid cells that overlap with a circle.
        
        Returns the set of cells that could contain entities within
        the given radius of the point (x, y).
        """
        # Calculate the bounding box in cells
        min_x = int((x - radius) // self.cell_size)
        max_x = int((x + radius) // self.cell_size)
        min_y = int((y - radius) // self.cell_size)
        max_y = int((y + radius) // self.cell_size)
        
        cells = set()
        for cell_x in range(min_x, max_x + 1):
            for cell_y in range(min_y, max_y + 1):
                cells.add((cell_x, cell_y))
        return cells
    
    def add_lifeform(self, lifeform: Lifeform) -> None:
        """Add a lifeform to the grid based on its position."""
        cell = self._get_cell(lifeform.x, lifeform.y)
        self._lifeforms[cell].append(lifeform)
        
    def add_plant(self, plant: Plant) -> None:
        """Add a plant to the grid based on its position."""
        # Use center of plant
        center_x = plant.x + plant.width / 2
        center_y = plant.y + plant.height / 2
        cell = self._get_cell(center_x, center_y)
        self._plants[cell].append(plant)
        
    def query_lifeforms(self, x: float, y: float, radius: float) -> List[Lifeform]:
        """Query all lifeforms within radius of the given point.
        
        Args:
            x, y: Center point for the query
            radius: Maximum distance from center
            
        Returns:
            List of lifeforms within the radius. Note: this may include some
            entities slightly outside the radius (false positives from grid cells).
            Caller should verify exact distance if needed.
        """
        cells = self._get_cells_in_radius(x, y, radius)
        
        # Collect unique lifeforms from all relevant cells
        seen = set()
        results = []
        radius_sq = radius * radius
        
        for cell in cells:
            for lifeform in self._lifeforms.get(cell, []):
                # Skip duplicates (entity might be in multiple cells)
                if id(lifeform) in seen:
                    continue
                seen.add(id(lifeform))
                
                # Check actual distance (optional but recommended for accuracy)
                dx = lifeform.x - x
                dy = lifeform.y - y
                if dx * dx + dy * dy <= radius_sq:
                    results.append(lifeform)
                    
        return results
    
    def query_plants(self, x: float, y: float, radius: float) -> List[Plant]:
        """Query all plants within radius of the given point.
        
        Args:
            x, y: Center point for the query
            radius: Maximum distance from center
            
        Returns:
            List of plants within the radius.
        """
        cells = self._get_cells_in_radius(x, y, radius)
        
        # Collect unique plants from all relevant cells
        seen = set()
        results = []
        radius_sq = radius * radius
        
        for cell in cells:
            for plant in self._plants.get(cell, []):
                # Skip duplicates
                if id(plant) in seen:
                    continue
                seen.add(id(plant))
                
                # Check actual distance using plant center
                center_x = plant.x + plant.width / 2
                center_y = plant.y + plant.height / 2
                dx = center_x - x
                dy = center_y - y
                if dx * dx + dy * dy <= radius_sq:
                    results.append(plant)
                    
        return results
    
    def query_lifeforms_rect(
        self, 
        min_x: float, 
        min_y: float, 
        max_x: float, 
        max_y: float
    ) -> List[Lifeform]:
        """Query all lifeforms within a rectangular region.
        
        Useful for camera frustum culling and area-based queries.
        """
        # Get all cells that overlap the rectangle
        min_cell_x = int(min_x // self.cell_size)
        max_cell_x = int(max_x // self.cell_size)
        min_cell_y = int(min_y // self.cell_size)
        max_cell_y = int(max_y // self.cell_size)
        
        seen = set()
        results = []
        
        for cell_x in range(min_cell_x, max_cell_x + 1):
            for cell_y in range(min_cell_y, max_cell_y + 1):
                for lifeform in self._lifeforms.get((cell_x, cell_y), []):
                    if id(lifeform) in seen:
                        continue
                    seen.add(id(lifeform))
                    
                    # Check if actually in bounds
                    if min_x <= lifeform.x <= max_x and min_y <= lifeform.y <= max_y:
                        results.append(lifeform)
                        
        return results


def build_spatial_grid(
    lifeforms: Iterable[Lifeform],
    plants: Iterable[Plant],
    cell_size: float = 200.0
) -> SpatialHashGrid:
    """Build a spatial hash grid from collections of entities.
    
    Args:
        lifeforms: Iterable of lifeforms to add to the grid
        plants: Iterable of plants to add to the grid
        cell_size: Size of each grid cell (default: 200.0)
        
    Returns:
        Populated SpatialHashGrid ready for queries
        
    Example:
        >>> grid = build_spatial_grid(state.lifeforms, state.plants)
        >>> nearby = grid.query_lifeforms(x=100, y=100, radius=50)
    """
    grid = SpatialHashGrid(cell_size)
    
    for lifeform in lifeforms:
        grid.add_lifeform(lifeform)
        
    for plant in plants:
        grid.add_plant(plant)
        
    return grid


__all__ = ["SpatialHashGrid", "build_spatial_grid"]
