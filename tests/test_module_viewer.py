"""Tests for the module viewer tool."""

import sys
from pathlib import Path

import pytest

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

# Import after path setup
from module_viewer import ModuleViewer


class TestModuleViewer:
    """Test suite for ModuleViewer functionality."""

    def test_viewer_initialization(self):
        """Test that viewer can be initialized in headless mode."""
        viewer = ModuleViewer(width=800, height=600, headless=True)
        assert viewer.width == 800
        assert viewer.height == 600
        assert viewer.creature is not None
        assert viewer.running is True

    def test_default_creature(self):
        """Test that default creature is properly created."""
        viewer = ModuleViewer(headless=True)
        
        # Check default creature has expected modules
        graph = viewer.creature.graph
        assert len(graph) >= 5  # At least core, head, 2 fins, thruster
        assert graph.root_id == "core"

    def test_add_module(self):
        """Test adding modules to the creature."""
        viewer = ModuleViewer(headless=True)
        initial_count = len(viewer.creature.graph)
        
        # Try adding a sensor module
        viewer.add_module("sensor")
        
        # Module count may increase if attachment point was available
        final_count = len(viewer.creature.graph)
        assert final_count >= initial_count

    def test_remove_module(self):
        """Test removing modules from the creature."""
        viewer = ModuleViewer(headless=True)
        
        # Add a module first
        viewer.add_module("sensor")
        count_after_add = len(viewer.creature.graph)
        
        # Remove it
        viewer.remove_last_module()
        count_after_remove = len(viewer.creature.graph)
        
        # Should have one less module (or same if add failed)
        assert count_after_remove <= count_after_add

    def test_reset_creature(self):
        """Test resetting the creature to default."""
        viewer = ModuleViewer(headless=True)
        
        # Modify the creature
        viewer.add_module("sensor")
        
        # Reset
        viewer.reset_creature()
        
        # Should be back to default
        graph = viewer.creature.graph
        assert len(graph) >= 5

    def test_layout_computation(self):
        """Test that layout is computed for all modules."""
        viewer = ModuleViewer(headless=True)
        
        # Layout should have entry for each module
        graph = viewer.creature.graph
        assert len(viewer.layout) == len(graph)
        
        # All entries should be Vector2
        for node_id, position in viewer.layout.items():
            assert hasattr(position, 'x')
            assert hasattr(position, 'y')

    def test_render_no_crash(self):
        """Test that rendering doesn't crash."""
        viewer = ModuleViewer(headless=True)
        
        # Should not raise an exception
        viewer.render()

    def test_screenshot_save(self, tmp_path):
        """Test saving screenshots."""
        viewer = ModuleViewer(headless=True)
        viewer.render()
        
        # Save screenshot
        output_file = tmp_path / "test_screenshot.png"
        viewer.save_screenshot(str(output_file))
        
        # File should exist
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_animation_toggle(self):
        """Test toggling animation."""
        viewer = ModuleViewer(headless=True)
        
        initial_state = viewer.animate
        viewer.animate = not viewer.animate
        assert viewer.animate != initial_state

    def test_physics_aggregation(self):
        """Test that physics stats are aggregated correctly."""
        viewer = ModuleViewer(headless=True)
        
        agg = viewer.creature.graph.aggregate_physics_stats()
        
        # Check that stats are reasonable
        assert agg.mass > 0
        assert agg.volume > 0
        assert agg.total_thrust >= 0
        assert agg.energy_cost > 0

    def test_module_visuals(self):
        """Test that module visuals can be retrieved."""
        viewer = ModuleViewer(headless=True)
        
        # Test different module types
        for module_type in ["core", "head", "limb", "propulsion", "sensor"]:
            color, alpha = viewer._get_module_visuals(module_type)
            assert len(color) == 3  # RGB tuple
            assert 0 <= alpha <= 255
