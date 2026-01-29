import pytest
import logging
from unittest.mock import MagicMock
from src.providers.lark_project.managers.metadata_manager import MetadataManager

class TestMetadataManagerSafety:
    """Tests for safety features in MetadataManager._flatten_options"""

    @pytest.fixture
    def manager(self):
        # We don't need real APIs for testing _flatten_options
        return MetadataManager()

    def test_flatten_options_recursion_limit(self, manager, caplog):
        """Test that recursion stops at max_depth"""
        # Create a deeply nested structure (depth 25)
        def create_nested_options(depth):
            if depth == 0:
                return [{"label": "Leaf", "value": "leaf"}]
            return [{"label": f"Level_{depth}", "value": f"val_{depth}", "children": create_nested_options(depth - 1)}]

        deep_options = create_nested_options(25)
        target_map = {}

        # Capture logs
        with caplog.at_level(logging.WARNING):
            manager._flatten_options(deep_options, target_map, max_depth=20)
        
        # Verify warning was logged
        assert "Recursion depth limit reached" in caplog.text
        
        # Verify that we captured up to level 20 but not deeper
        # Level_25 is depth 0. Level_5 is depth 20.
        assert "Level_25" in target_map
        assert "Level_5" in target_map
        assert "Level_4" not in target_map # Should be skipped

    def test_flatten_options_collision_detection(self, manager, caplog):
        """Test that label collisions are detected and logged"""
        options = [
            {
                "label": "Duplicate", 
                "value": "val_1",
                "children": [
                    {"label": "Duplicate", "value": "val_2"} # Collision!
                ]
            }
        ]
        target_map = {}

        with caplog.at_level(logging.WARNING):
            manager._flatten_options(options, target_map)

        # Verify warning
        assert "Option label collision detected" in caplog.text
        assert "Duplicate" in caplog.text
        assert "val_1" in caplog.text
        assert "val_2" in caplog.text
        
        # Verify last value wins (standard dict behavior)
        assert target_map["Duplicate"] == "val_2"

    def test_flatten_options_invalid_type(self, manager, caplog):
        """Test handling of invalid option types"""
        options = [
            {"label": "Valid", "value": "val_1"},
            "Invalid String", # Should be skipped
            None,             # Should be skipped
            {"label": "Valid2", "value": "val_2"}
        ]
        target_map = {}

        with caplog.at_level(logging.WARNING):
            manager._flatten_options(options, target_map) # type: ignore

        # Verify warnings
        assert "Invalid option format" in caplog.text
        
        # Verify valid items were processed
        assert target_map["Valid"] == "val_1"
        assert target_map["Valid2"] == "val_2"
