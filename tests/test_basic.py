#!/usr/bin/env python3
"""
Basic test to verify the page mapper module can be imported and instantiated.
"""

import sys
import os

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_imports():
    """Test that we can import the page mapper module."""
    try:
        from notion_mcp_server.page_mapper import NotionPageMapper, NotionPage
        print("SUCCESS: Successfully imported NotionPageMapper and NotionPage")
        return True
    except ImportError as e:
        print("ERROR: Failed to import:", str(e))
        return False

def test_dataclass():
    """Test that the NotionPage dataclass works correctly."""
    try:
        from notion_mcp_server.page_mapper import NotionPage
        
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
        
        print("SUCCESS: Created test page:", test_page.title)
        print("   ID:", test_page.id)
        print("   Path:", " > ".join(test_page.path))
        print("   Depth:", test_page.depth)
        return True
    except Exception as e:
        print("ERROR: Failed to create NotionPage:", str(e))
        return False

def test_resources_folder():
    """Test that the resources folder exists."""
    resources_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'notion_mcp_server', 'resources')
    if os.path.exists(resources_path):
        print("SUCCESS: Resources folder exists:", resources_path)
        
        cache_file = os.path.join(resources_path, 'page_cache.json')
        if os.path.exists(cache_file):
            print("SUCCESS: Cache file exists:", cache_file)
        else:
            print("WARNING: Cache file not found:", cache_file)
        return True
    else:
        print("ERROR: Resources folder not found:", resources_path)
        return False

def main():
    """Run all basic tests."""
    print("Running basic tests for Notion MCP Server...")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("DataClass Test", test_dataclass),
        ("Resources Folder Test", test_resources_folder),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print("\n" + test_name + ":")
        if test_func():
            passed += 1
        else:
            print("ERROR:", test_name, "failed")
    
    print("\n" + "=" * 50)
    print("Test Results:", str(passed) + "/" + str(total), "tests passed")
    
    if passed == total:
        print("SUCCESS: All basic tests passed! The page mapping system is properly set up.")
        print("\nTo test with real Notion data, run:")
        print("  uv run python tests/test_page_mapper.py")
    else:
        print("ERROR: Some tests failed. Please check the setup.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)