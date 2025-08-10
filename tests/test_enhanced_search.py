"""
Tests for the enhanced search functionality.
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notion_mcp_server.enhanced_search import EnhancedNotionSearch, SearchResult
from notion_mcp_server.page_mapper import NotionPage, NotionPageMapper


@pytest.fixture
def mock_notion_client():
    """Create a mock Notion client."""
    client = Mock()
    client.search = Mock(return_value={
        "results": [
            {
                "id": "test-page-1",
                "object": "page",
                "properties": {
                    "title": {
                        "type": "title",
                        "title": [{"plain_text": "Test Page 1"}]
                    }
                },
                "created_time": "2023-01-01T00:00:00.000Z",
                "last_edited_time": "2023-01-01T00:00:00.000Z",
                "archived": False
            }
        ],
        "has_more": False,
        "next_cursor": None
    })
    
    client.blocks = Mock()
    client.blocks.children = Mock()
    client.blocks.children.list = Mock(return_value={
        "results": [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "This is test content about acappella database credentials."}]
                }
            }
        ]
    })
    
    return client


@pytest.fixture
def mock_page_mapper():
    """Create a mock page mapper."""
    mapper = Mock(spec=NotionPageMapper)
    
    test_page = NotionPage(
        id="test-page-1",
        title="CA Database Credentials",
        url="https://www.notion.so/testpage1",
        parent_type="workspace",
        parent_id=None,
        object_type="page",
        created_time="2023-01-01T00:00:00.000Z",
        last_edited_time="2023-01-01T00:00:00.000Z",
        archived=False,
        children=[],
        path=["CA Database Credentials"],
        depth=0
    )
    
    mapper._page_map = {"test-page-1": test_page}
    mapper.get_all_pages = AsyncMock(return_value={"test-page-1": test_page})
    mapper.get_page_by_id = Mock(return_value=test_page)
    
    return mapper


@pytest.fixture
def enhanced_search(mock_notion_client, mock_page_mapper):
    """Create an enhanced search instance."""
    return EnhancedNotionSearch(mock_notion_client, mock_page_mapper)


@pytest.mark.asyncio
async def test_basic_search(enhanced_search):
    """Test basic search functionality."""
    results = await enhanced_search.search("database credentials", max_results=5)
    
    assert len(results) > 0
    assert isinstance(results[0], SearchResult)
    assert results[0].page.title == "CA Database Credentials"
    assert results[0].relevance_score > 0


@pytest.mark.asyncio
async def test_specific_query_detection(enhanced_search):
    """Test detection of specific queries that warrant content search."""
    # Test multi-word query
    assert enhanced_search._is_specific_query("acappella database password credentials")
    
    # Test query with specific terms
    assert enhanced_search._is_specific_query("password for database")
    
    # Test simple query
    assert not enhanced_search._is_specific_query("test")


def test_title_relevance_calculation(enhanced_search):
    """Test title relevance scoring."""
    query_words = {"database", "credentials"}
    
    # Exact match should score high
    score1 = enhanced_search._calculate_title_relevance(query_words, "Database Credentials")
    assert score1 == 1.0
    
    # Partial match should score lower
    score2 = enhanced_search._calculate_title_relevance(query_words, "Database Setup")
    assert 0 < score2 < 1.0
    
    # No match should score 0
    score3 = enhanced_search._calculate_title_relevance(query_words, "Random Page")
    assert score3 == 0.0


def test_content_matching(enhanced_search):
    """Test content matching logic."""
    query = "update weekly keynote spreadsheet"
    
    # Content with exact match
    content1 = "Here's how to update the weekly keynote and spreadsheet with the latest data."
    assert enhanced_search._content_matches_query(query, content1)
    
    # Content with partial match (3 out of 4 words = 75%)
    content2 = "This document explains how to update weekly keynote presentations."
    assert enhanced_search._content_matches_query(query, content2)
    
    # Content with no match
    content3 = "This is about something completely different like database configuration."
    assert not enhanced_search._content_matches_query(query, content3)


def test_content_preview_generation(enhanced_search):
    """Test content preview generation."""
    query = "database password"
    content = "This is a long document about various topics. The database password is stored in the configuration file. There are many other details here."
    
    preview = enhanced_search._generate_content_preview(query, content, max_length=50)
    
    assert "database password" in preview.lower()
    assert len(preview) <= 60  # Accounting for ellipsis