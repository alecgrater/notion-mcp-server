#!/usr/bin/env python3
"""
Test script for the Notion page mapper functionality.
This script tests the page mapping without running the full MCP server.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from notion_client import Client

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notion_mcp_server.page_mapper import NotionPageMapper

async def test_page_mapper():
    """Test the page mapper functionality."""
    
    # Load environment variables
    load_dotenv()
    
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        print("Error: NOTION_TOKEN environment variable is required")
        return
    
    # Initialize Notion client and page mapper
    notion = Client(auth=notion_token)
    page_mapper = NotionPageMapper(notion, cache_duration_hours=1)
    
    print("🔍 Testing Notion Page Mapper...")
    print("=" * 50)
    
    try:
        # Test 1: Get all pages
        print("\n1. Fetching all pages...")
        all_pages = await page_mapper.get_all_pages()
        print(f"   ✅ Found {len(all_pages)} total pages")
        
        # Test 2: Get hierarchy info
        print("\n2. Getting hierarchy information...")
        hierarchy_info = await page_mapper.get_page_hierarchy_info()
        print(f"   ✅ Total pages: {hierarchy_info['total_pages']}")
        print(f"   ✅ Top-level pages: {hierarchy_info['top_level_pages']}")
        print(f"   ✅ Maximum depth: {hierarchy_info['max_depth']}")
        print(f"   ✅ Archived pages: {hierarchy_info['archived_pages']}")
        
        # Test 3: Show top-level pages
        print("\n3. Top-level pages:")
        top_level_pages = await page_mapper.get_top_level_pages()
        for page in top_level_pages[:5]:  # Show first 5
            print(f"   • {page.title} (ID: {page.id})")
        if len(top_level_pages) > 5:
            print(f"   ... and {len(top_level_pages) - 5} more")
        
        # Test 4: Sample page search
        if top_level_pages:
            sample_page = top_level_pages[0]
            print(f"\n4. Testing page search with '{sample_page.title}'...")
            found_pages = page_mapper.search_pages_by_title(sample_page.title[:10], limit=3)
            print(f"   ✅ Found {len(found_pages)} pages matching partial title")
            for page in found_pages:
                print(f"   • {page.title}")
        
        # Test 5: Show sample hierarchy
        print("\n5. Sample page hierarchy:")
        sample_pages = [p for p in all_pages.values() if not p.archived][:10]
        for page in sample_pages:
            indent = "  " * page.depth
            path_str = " > ".join(page.path)
            print(f"   {indent}• {page.title} (depth: {page.depth})")
            print(f"   {indent}  Path: {path_str}")
        
        # Test 6: Cache functionality
        print("\n6. Testing cache functionality...")
        print("   Refreshing cache...")
        await page_mapper.refresh_cache()
        print("   ✅ Cache refreshed successfully")
        
        print("\n" + "=" * 50)
        print("🎉 All tests completed successfully!")
        print("\nYour Notion MCP server is ready to use with the following new tools:")
        print("• list-notion-pages - List all pages with hierarchy")
        print("• find-notion-page - Find pages by title or path")
        print("• refresh-notion-cache - Refresh the page mapping cache")
        print("• Enhanced write-to-notion - Now refreshes cache after changes")
        print("• Enhanced resources - Now uses cached page mapping")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_page_mapper())