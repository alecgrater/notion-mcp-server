"""
Basic pytest tests to verify the page mapper module can be imported and instantiated.
"""

import os
import sys
import pytest

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notion_mcp_server.page_mapper import NotionPageMapper, NotionPage


def test_imports():
    """Test that we can import the page mapper module."""
    # If we get here without ImportError, the test passes
    assert NotionPageMapper is not None
    assert NotionPage is not None


def test_dataclass():
    """Test that the NotionPage dataclass works correctly."""
    # Create a test page
    test_page = NotionPage(
        id="test-id",
        title="Test Page",
        url="https://notion.so/test",
        parent_type="workspace",
        parent_id=None,
        object_type="page",
        created_time="2024-01-01T00:00:00Z",
        last_edited_time="2024-01-01T00:00:00Z",
        archived=False,
        children=[],
        path=["Test Page"],
        depth=0
    )
    
    assert test_page.id == "test-id"
    assert test_page.title == "Test Page"
    assert test_page.path == ["Test Page"]
    assert test_page.depth == 0
    assert test_page.archived is False


def test_resources_folder():
    """Test that the resources folder exists."""
    resources_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'notion_mcp_server', 'resources')
    assert os.path.exists(resources_path), f"Resources folder not found: {resources_path}"
    
    cache_file = os.path.join(resources_path, 'page_cache.json')
    assert os.path.exists(cache_file), f"Cache file not found: {cache_file}"


if __name__ == "__main__":
    pytest.main([__file__])