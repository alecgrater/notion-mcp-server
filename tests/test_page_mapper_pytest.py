"""
Pytest integration tests for the Notion page mapper functionality.
This script tests the page mapping with real Notion data.
"""

import os
import sys
import pytest
import pytest_asyncio
from dotenv import load_dotenv

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notion_mcp_server.page_mapper import NotionPageMapper
from notion_client import Client


@pytest.fixture(scope="session")
def notion_client():
    """Create a Notion client for testing."""
    load_dotenv()
    
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        pytest.skip("NOTION_TOKEN environment variable is required for integration tests")
    
    return Client(auth=notion_token)


@pytest.fixture(scope="session")
def page_mapper(notion_client):
    """Create a page mapper for testing."""
    return NotionPageMapper(notion_client, cache_duration_hours=1)


@pytest.mark.asyncio
async def test_get_all_pages(page_mapper):
    """Test fetching all pages from Notion workspace."""
    all_pages = await page_mapper.get_all_pages()
    
    assert isinstance(all_pages, dict)
    assert len(all_pages) > 0
    
    # Check that pages have the expected structure
    for page_id, page in all_pages.items():
        assert page.id == page_id
        assert isinstance(page.title, str)
        assert isinstance(page.path, list)
        assert isinstance(page.depth, int)
        assert isinstance(page.archived, bool)


@pytest.mark.asyncio
async def test_hierarchy_info(page_mapper):
    """Test getting hierarchy information."""
    hierarchy_info = await page_mapper.get_page_hierarchy_info()
    
    assert "total_pages" in hierarchy_info
    assert "top_level_pages" in hierarchy_info
    assert "max_depth" in hierarchy_info
    assert "archived_pages" in hierarchy_info
    assert "pages_by_depth" in hierarchy_info
    assert "sample_paths" in hierarchy_info
    
    assert hierarchy_info["total_pages"] > 0
    assert hierarchy_info["max_depth"] >= 0


@pytest.mark.asyncio
async def test_top_level_pages(page_mapper):
    """Test getting top-level pages."""
    top_level_pages = await page_mapper.get_top_level_pages()
    
    assert isinstance(top_level_pages, list)
    
    for page in top_level_pages:
        assert page.parent_type == "workspace"
        assert not page.archived
        assert page.depth == 0


@pytest.mark.asyncio
async def test_page_search(page_mapper):
    """Test page search functionality."""
    # Ensure we have pages loaded
    await page_mapper.get_all_pages()
    
    # Test search with a common term
    found_pages = page_mapper.search_pages_by_title("test", limit=5)
    assert isinstance(found_pages, list)
    
    # Test that all found pages contain the search term (case insensitive)
    for page in found_pages:
        assert "test" in page.title.lower()


@pytest.mark.asyncio
async def test_cache_functionality(page_mapper):
    """Test cache refresh functionality."""
    # This should work without errors
    await page_mapper.refresh_cache()
    
    # Verify we still have pages after refresh
    all_pages = await page_mapper.get_all_pages()
    assert len(all_pages) > 0


@pytest.mark.asyncio
async def test_find_page_by_title(page_mapper):
    """Test finding a page by exact title."""
    # Get all pages first
    all_pages = await page_mapper.get_all_pages()
    
    if all_pages:
        # Take the first page and try to find it by exact title
        sample_page = next(iter(all_pages.values()))
        found_page = await page_mapper.find_page_by_title(sample_page.title, exact_match=True)
        
        if found_page:  # Only assert if we found something
            assert found_page.id == sample_page.id
            assert found_page.title == sample_page.title


@pytest.mark.asyncio
async def test_page_children(page_mapper):
    """Test getting page children."""
    all_pages = await page_mapper.get_all_pages()
    
    # Find a page that has children
    parent_page = None
    for page in all_pages.values():
        if page.children:
            parent_page = page
            break
    
    if parent_page:
        children = await page_mapper.get_page_children(parent_page.id)
        assert isinstance(children, list)
        assert len(children) == len(parent_page.children)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])