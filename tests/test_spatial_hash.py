"""Tests for the spatial hash grid performance optimization."""

from __future__ import annotations

import pytest
from dataclasses import dataclass

from evolution.systems.spatial_hash import SpatialHashGrid, build_spatial_grid


@dataclass
class MockLifeform:
    """Mock lifeform for testing."""
    x: float
    y: float
    id: int
    health_now: float = 100.0


@dataclass
class MockPlant:
    """Mock plant for testing."""
    x: float
    y: float
    width: float = 10.0
    height: float = 10.0
    resource: float = 100.0


class TestSpatialHashGrid:
    """Test suite for SpatialHashGrid."""

    def test_grid_initialization(self):
        """Test grid can be initialized."""
        grid = SpatialHashGrid(cell_size=100.0)
        assert grid.cell_size == 100.0

    def test_add_and_query_lifeform(self):
        """Test adding and querying a single lifeform."""
        grid = SpatialHashGrid(cell_size=100.0)
        lifeform = MockLifeform(x=50.0, y=50.0, id=1)
        
        grid.add_lifeform(lifeform)
        results = grid.query_lifeforms(50.0, 50.0, radius=10.0)
        
        assert len(results) == 1
        assert results[0] is lifeform

    def test_query_lifeforms_radius(self):
        """Test querying lifeforms within a radius."""
        grid = SpatialHashGrid(cell_size=100.0)
        
        # Add lifeforms at different positions
        lf1 = MockLifeform(x=50.0, y=50.0, id=1)
        lf2 = MockLifeform(x=60.0, y=50.0, id=2)  # 10 units away
        lf3 = MockLifeform(x=150.0, y=50.0, id=3)  # 100 units away
        
        grid.add_lifeform(lf1)
        grid.add_lifeform(lf2)
        grid.add_lifeform(lf3)
        
        # Query with radius 20 - should get lf1 and lf2
        results = grid.query_lifeforms(50.0, 50.0, radius=20.0)
        assert len(results) == 2
        assert lf1 in results
        assert lf2 in results
        assert lf3 not in results

    def test_query_plants(self):
        """Test querying plants within a radius."""
        grid = SpatialHashGrid(cell_size=100.0)
        
        # Add plants at different positions
        p1 = MockPlant(x=50.0, y=50.0)
        p2 = MockPlant(x=60.0, y=50.0)
        p3 = MockPlant(x=150.0, y=50.0)
        
        grid.add_plant(p1)
        grid.add_plant(p2)
        grid.add_plant(p3)
        
        # Query with radius 30
        results = grid.query_plants(50.0, 50.0, radius=30.0)
        assert len(results) >= 1  # Should at least find p1
        assert p1 in results

    def test_query_empty_grid(self):
        """Test querying an empty grid returns no results."""
        grid = SpatialHashGrid(cell_size=100.0)
        
        results = grid.query_lifeforms(50.0, 50.0, radius=100.0)
        assert len(results) == 0
        
        results = grid.query_plants(50.0, 50.0, radius=100.0)
        assert len(results) == 0

    def test_clear_grid(self):
        """Test clearing the grid removes all entities."""
        grid = SpatialHashGrid(cell_size=100.0)
        
        grid.add_lifeform(MockLifeform(x=50.0, y=50.0, id=1))
        grid.add_plant(MockPlant(x=50.0, y=50.0))
        
        grid.clear()
        
        assert len(grid.query_lifeforms(50.0, 50.0, radius=100.0)) == 0
        assert len(grid.query_plants(50.0, 50.0, radius=100.0)) == 0

    def test_query_rect(self):
        """Test querying lifeforms within a rectangular region."""
        grid = SpatialHashGrid(cell_size=100.0)
        
        lf1 = MockLifeform(x=50.0, y=50.0, id=1)
        lf2 = MockLifeform(x=150.0, y=50.0, id=2)
        lf3 = MockLifeform(x=50.0, y=150.0, id=3)
        
        grid.add_lifeform(lf1)
        grid.add_lifeform(lf2)
        grid.add_lifeform(lf3)
        
        # Query rectangle that should contain only lf1
        results = grid.query_lifeforms_rect(0.0, 0.0, 100.0, 100.0)
        assert len(results) == 1
        assert lf1 in results

    def test_multiple_cells(self):
        """Test entities in different grid cells are handled correctly."""
        grid = SpatialHashGrid(cell_size=100.0)
        
        # Add lifeforms in different cells
        lf1 = MockLifeform(x=50.0, y=50.0, id=1)   # Cell (0, 0)
        lf2 = MockLifeform(x=150.0, y=50.0, id=2)  # Cell (1, 0)
        lf3 = MockLifeform(x=50.0, y=150.0, id=3)  # Cell (0, 1)
        
        grid.add_lifeform(lf1)
        grid.add_lifeform(lf2)
        grid.add_lifeform(lf3)
        
        # Query from center of cell (0, 0) with small radius
        results = grid.query_lifeforms(50.0, 50.0, radius=30.0)
        assert len(results) == 1
        assert lf1 in results

    def test_cell_size_validation(self):
        """Test that cell size is validated."""
        # Should use minimum value of 1.0 if negative or zero
        grid = SpatialHashGrid(cell_size=-10.0)
        assert grid.cell_size >= 1.0
        
        grid = SpatialHashGrid(cell_size=0.0)
        assert grid.cell_size >= 1.0


class TestBuildSpatialGrid:
    """Test suite for build_spatial_grid helper function."""

    def test_build_empty_grid(self):
        """Test building a grid with no entities."""
        grid = build_spatial_grid([], [], cell_size=100.0)
        assert grid.cell_size == 100.0
        assert len(grid.query_lifeforms(0.0, 0.0, radius=1000.0)) == 0

    def test_build_grid_with_entities(self):
        """Test building a grid with lifeforms and plants."""
        lifeforms = [
            MockLifeform(x=50.0, y=50.0, id=1),
            MockLifeform(x=150.0, y=50.0, id=2),
        ]
        plants = [
            MockPlant(x=50.0, y=50.0),
            MockPlant(x=150.0, y=50.0),
        ]
        
        grid = build_spatial_grid(lifeforms, plants, cell_size=100.0)
        
        # Should be able to query both types
        lf_results = grid.query_lifeforms(50.0, 50.0, radius=30.0)
        assert len(lf_results) >= 1
        
        plant_results = grid.query_plants(50.0, 50.0, radius=30.0)
        assert len(plant_results) >= 1

    def test_build_with_custom_cell_size(self):
        """Test building a grid with custom cell size."""
        grid = build_spatial_grid([], [], cell_size=200.0)
        assert grid.cell_size == 200.0


class TestPerformance:
    """Performance-oriented tests."""

    def test_large_grid_performance(self):
        """Test that grid performs well with many entities."""
        grid = SpatialHashGrid(cell_size=200.0)
        
        # Add 1000 lifeforms in a grid pattern
        for i in range(1000):
            x = (i % 32) * 50.0
            y = (i // 32) * 50.0
            grid.add_lifeform(MockLifeform(x=x, y=y, id=i))
        
        # Query should be fast even with many entities
        import time
        start = time.time()
        results = grid.query_lifeforms(500.0, 500.0, radius=100.0)
        elapsed = time.time() - start
        
        # Should complete in less than 10ms
        assert elapsed < 0.01
        # Should find some entities
        assert len(results) > 0

    def test_spatial_locality(self):
        """Test that queries benefit from spatial locality."""
        grid = SpatialHashGrid(cell_size=100.0)
        
        # Add 100 lifeforms clustered in one area
        for i in range(100):
            grid.add_lifeform(MockLifeform(x=50.0 + i * 2, y=50.0, id=i))
        
        # Add 100 lifeforms far away
        for i in range(100, 200):
            grid.add_lifeform(MockLifeform(x=5000.0 + i * 2, y=5000.0, id=i))
        
        # Query in first cluster should only check nearby cells
        results = grid.query_lifeforms(50.0, 50.0, radius=100.0)
        
        # Should find entities from first cluster
        assert len(results) > 0
        # Should not include entities from far cluster
        assert all(r.x < 1000 for r in results)
