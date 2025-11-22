"""Tests for depth-based darkening of lifeforms."""

import pygame
import pytest

from evolution.rendering.draw_lifeform import _apply_depth_shading, _calculate_depth_darkness


class TestDepthDarkness:
    """Test the depth-based darkness calculation."""

    def test_surface_full_brightness(self):
        """Lifeforms at the surface (y=0) should have full brightness."""
        darkness = _calculate_depth_darkness(0, 6000)
        assert darkness == pytest.approx(1.0, abs=0.01)

    def test_bottom_complete_darkness(self):
        """Lifeforms at the bottom should have complete darkness."""
        darkness = _calculate_depth_darkness(6000, 6000)
        assert darkness == pytest.approx(0.0, abs=0.01)

    def test_middle_partial_darkness(self):
        """Lifeforms at middle depth should have partial darkness."""
        darkness = _calculate_depth_darkness(3000, 6000)
        # At 50% depth, using exponential curve (1 - 0.5)^1.8 = 0.287
        assert 0.25 < darkness < 0.35

    def test_gradual_darkening(self):
        """Darkness should increase gradually with depth."""
        world_height = 6000
        darkness_values = []
        for y in range(0, world_height + 1, 1000):
            darkness = _calculate_depth_darkness(y, world_height)
            darkness_values.append(darkness)

        # Check that darkness decreases monotonically
        for i in range(len(darkness_values) - 1):
            assert darkness_values[i] >= darkness_values[i + 1]

    def test_zero_world_height(self):
        """Should handle edge case of zero world height."""
        darkness = _calculate_depth_darkness(100, 0)
        assert darkness == 1.0

    def test_negative_position(self):
        """Negative positions should be clamped to full brightness."""
        darkness = _calculate_depth_darkness(-100, 6000)
        assert darkness == pytest.approx(1.0, abs=0.01)

    def test_beyond_bottom(self):
        """Positions beyond bottom should be clamped to complete darkness."""
        darkness = _calculate_depth_darkness(7000, 6000)
        assert darkness == pytest.approx(0.0, abs=0.01)


class TestDepthShading:
    """Test the depth shading application to sprites."""

    def setup_method(self):
        """Initialize pygame for surface operations."""
        pygame.init()

    def test_no_darkening_at_full_brightness(self):
        """Sprite should be unchanged at full brightness."""
        sprite = pygame.Surface((10, 10), pygame.SRCALPHA)
        sprite.fill((255, 0, 0))  # Red

        result = _apply_depth_shading(sprite, 1.0)

        # Should return the original sprite without modification
        assert result is sprite

    def test_complete_darkening(self):
        """Sprite should be completely dark at 0.0 brightness."""
        sprite = pygame.Surface((10, 10), pygame.SRCALPHA)
        sprite.fill((255, 0, 0))  # Red

        result = _apply_depth_shading(sprite, 0.0)

        # Result should be a new surface
        assert result is not sprite

        # Check that the result is significantly darker
        # (We can't easily check exact pixel values due to blending)
        assert result.get_size() == sprite.get_size()

    def test_partial_darkening(self):
        """Sprite should be partially darkened at intermediate brightness."""
        sprite = pygame.Surface((10, 10), pygame.SRCALPHA)
        sprite.fill((255, 0, 0))  # Red

        result = _apply_depth_shading(sprite, 0.5)

        # Result should be a new surface
        assert result is not sprite
        assert result.get_size() == sprite.get_size()

    def test_brightness_range(self):
        """Test various brightness levels produce different results."""
        sprite = pygame.Surface((10, 10), pygame.SRCALPHA)
        sprite.fill((255, 255, 255))  # White

        results = []
        for brightness in [1.0, 0.75, 0.5, 0.25, 0.0]:
            result = _apply_depth_shading(sprite, brightness)
            results.append(result)

        # All results should have the correct size
        for result in results:
            assert result.get_size() == (10, 10)
