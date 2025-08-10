"""
Page mapping functionality for the Notion MCP server.
This module provides comprehensive page discovery and hierarchical mapping.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from notion_client import Client
from notion_client.errors import APIResponseError


@dataclass
class NotionPage:
    """Represents a Notion page with its metadata and hierarchy information."""
    id: str
    title: str
    url: str
    parent_type: str  # 'workspace', 'page', 'database'
    parent_id: Optional[str]
    object_type: str  # 'page' or 'database'
    created_time: str
    last_edited_time: str
    archived: bool
    children: List[str]  # List of child page IDs
    path: List[str]  # Full path from root to this page (titles)
    depth: int


class NotionPageMapper:
    """Handles comprehensive mapping of all Notion pages with caching."""
    
    def __init__(self, notion_client: Client, cache_duration_hours: int = 1):
        self.notion = notion_client
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.cache_file = os.path.join(os.path.dirname(__file__), 'resources', 'page_cache.json')
        self._page_map: Dict[str, NotionPage] = {}
        self._title_to_id: Dict[str, str] = {}
        self._last_update: Optional[datetime] = None
    
    async def get_all_pages(self, force_refresh: bool = False) -> Dict[str, NotionPage]:
        """
        Get all pages from Notion workspace with hierarchical structure.
        Uses caching to avoid excessive API calls.
        """
        if not force_refresh and self._is_cache_valid():
            await self._load_from_cache()
            if self._page_map:
                return self._page_map
        
        print("Fetching all pages from Notion workspace...")
        await self._fetch_all_pages()
        await self._build_hierarchy()
        await self._save_to_cache()
        
        return self._page_map
    
    async def find_page_by_title(self, title: str, exact_match: bool = True) -> Optional[NotionPage]:
        """Find a page by its title."""
        await self.get_all_pages()
        
        if exact_match:
            page_id = self._title_to_id.get(title)
            return self._page_map.get(page_id) if page_id else None
        else:
            # Fuzzy search
            title_lower = title.lower()
            for page_title, page_id in self._title_to_id.items():
                if title_lower in page_title.lower():
                    return self._page_map[page_id]
            return None
    
    async def find_pages_by_path(self, path_parts: List[str]) -> List[NotionPage]:
        """Find pages that match a specific path hierarchy."""
        await self.get_all_pages()
        
        matching_pages = []
        for page in self._page_map.values():
            if len(page.path) >= len(path_parts):
                # Check if the path matches (case-insensitive)
                path_match = True
                for i, part in enumerate(path_parts):
                    if i >= len(page.path) or part.lower() not in page.path[i].lower():
                        path_match = False
                        break
                
                if path_match:
                    matching_pages.append(page)
        
        return matching_pages
    
    async def get_top_level_pages(self) -> List[NotionPage]:
        """Get all top-level pages (direct children of workspace)."""
        await self.get_all_pages()
        return [page for page in self._page_map.values() 
                if page.parent_type == 'workspace' and not page.archived]
    
    async def get_page_children(self, page_id: str) -> List[NotionPage]:
        """Get all direct children of a specific page."""
        await self.get_all_pages()
        
        if page_id not in self._page_map:
            return []
        
        parent_page = self._page_map[page_id]
        return [self._page_map[child_id] for child_id in parent_page.children 
                if child_id in self._page_map]
    
    async def get_page_hierarchy_info(self) -> Dict[str, Any]:
        """Get comprehensive hierarchy information for debugging/display."""
        await self.get_all_pages()
        
        hierarchy_info = {
            "total_pages": len(self._page_map),
            "top_level_pages": len([p for p in self._page_map.values() if p.parent_type == 'workspace']),
            "max_depth": max((p.depth for p in self._page_map.values()), default=0),
            "archived_pages": len([p for p in self._page_map.values() if p.archived]),
            "pages_by_depth": {},
            "sample_paths": []
        }
        
        # Group by depth
        for page in self._page_map.values():
            depth = page.depth
            if depth not in hierarchy_info["pages_by_depth"]:
                hierarchy_info["pages_by_depth"][depth] = 0
            hierarchy_info["pages_by_depth"][depth] += 1
        
        # Sample paths for different depths
        for depth in range(min(4, hierarchy_info["max_depth"] + 1)):
            depth_pages = [p for p in self._page_map.values() if p.depth == depth and not p.archived]
            if depth_pages:
                sample_page = depth_pages[0]
                hierarchy_info["sample_paths"].append({
                    "depth": depth,
                    "title": sample_page.title,
                    "path": " > ".join(sample_page.path),
                    "id": sample_page.id
                })
        
        return hierarchy_info
    
    async def _fetch_all_pages(self):
        """Fetch all pages and databases from Notion workspace."""
        self._page_map.clear()
        self._title_to_id.clear()
        
        # Fetch all pages and databases
        all_results = []
        has_more = True
        start_cursor = None
        
        while has_more:
            try:
                search_params = {
                    "page_size": 100,  # Max allowed by Notion API
                    "filter": {
                        "property": "object",
                        "value": "page"
                    }
                }
                if start_cursor:
                    search_params["start_cursor"] = start_cursor
                
                response = self.notion.search(**search_params)
                all_results.extend(response.get("results", []))
                
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
                
                # Add a small delay to avoid rate limiting
                await asyncio.sleep(0.1)
                
            except APIResponseError as e:
                print(f"Error fetching pages: {e}")
                break
        
        # Also fetch databases
        has_more = True
        start_cursor = None
        
        while has_more:
            try:
                search_params = {
                    "page_size": 100,
                    "filter": {
                        "property": "object", 
                        "value": "database"
                    }
                }
                if start_cursor:
                    search_params["start_cursor"] = start_cursor
                
                response = self.notion.search(**search_params)
                all_results.extend(response.get("results", []))
                
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
                
                await asyncio.sleep(0.1)
                
            except APIResponseError as e:
                print(f"Error fetching databases: {e}")
                break
        
        # Process all results
        for result in all_results:
            page = self._process_page_result(result)
            if page:
                self._page_map[page.id] = page
                self._title_to_id[page.title] = page.id
        
        print(f"Fetched {len(self._page_map)} pages/databases from Notion")
    
    def _process_page_result(self, result: Dict[str, Any]) -> Optional[NotionPage]:
        """Process a single page/database result from Notion API."""
        try:
            page_id = result["id"]
            object_type = result.get("object", "page")
            
            # Extract title - handle both pages and databases
            title = "Untitled"
            
            # For databases, title is often at the root level
            if object_type == "database" and result.get("title"):
                title_parts = [t.get("plain_text", "") for t in result["title"]]
                title = "".join(title_parts).strip() or "Untitled"
            elif result.get("properties"):
                # For pages, look for title property in properties
                for prop_name, prop_data in result["properties"].items():
                    if prop_data.get("type") == "title" and prop_data.get("title"):
                        title_parts = [t.get("plain_text", "") for t in prop_data["title"]]
                        title = "".join(title_parts).strip() or "Untitled"
                        break
            
            # Extract parent information
            parent = result.get("parent", {})
            parent_type = parent.get("type", "workspace")
            parent_id = None
            
            if parent_type == "page_id":
                parent_id = parent.get("page_id")
                parent_type = "page"
            elif parent_type == "database_id":
                parent_id = parent.get("database_id")
                parent_type = "database"
            elif parent_type == "workspace":
                parent_type = "workspace"
            
            # Create page object
            page = NotionPage(
                id=page_id,
                title=title,
                url=f"https://www.notion.so/{page_id.replace('-', '')}",
                parent_type=parent_type,
                parent_id=parent_id,
                object_type=object_type,
                created_time=result.get("created_time", ""),
                last_edited_time=result.get("last_edited_time", ""),
                archived=result.get("archived", False),
                children=[],  # Will be populated in _build_hierarchy
                path=[],      # Will be populated in _build_hierarchy
                depth=0       # Will be populated in _build_hierarchy
            )
            
            return page
            
        except Exception as e:
            print(f"Error processing page result: {e}")
            return None
    
    async def _build_hierarchy(self):
        """Build the hierarchical structure and populate children/path/depth."""
        # First pass: populate children lists
        for page in self._page_map.values():
            if page.parent_id and page.parent_id in self._page_map:
                parent = self._page_map[page.parent_id]
                parent.children.append(page.id)
        
        # Second pass: build paths and depths using BFS
        visited: Set[str] = set()
        queue: List[str] = []
        
        # Start with top-level pages (workspace pages)
        for page in self._page_map.values():
            if page.parent_type == "workspace":
                page.path = [page.title]
                page.depth = 0
                queue.append(page.id)
                visited.add(page.id)
        
        # BFS to build hierarchy for connected pages
        while queue:
            current_id = queue.pop(0)
            current_page = self._page_map[current_id]
            
            for child_id in current_page.children:
                if child_id not in visited and child_id in self._page_map:
                    child_page = self._page_map[child_id]
                    child_page.path = current_page.path + [child_page.title]
                    child_page.depth = current_page.depth + 1
                    queue.append(child_id)
                    visited.add(child_id)
        
        # Filter out orphaned pages that don't belong in the main hierarchy
        # Only keep pages that are legitimate workspace pages or connected to the main hierarchy
        orphaned_pages = []
        for page in self._page_map.values():
            if page.id not in visited:
                # Only keep pages that are legitimate workspace pages (like "Work")
                # Filter out standalone pages that aren't connected to the main hierarchy
                if page.parent_type == "workspace" and page.parent_id is None:
                    # This could be a legitimate top-level page like "Work"
                    page.path = [page.title]
                    page.depth = 0
                    visited.add(page.id)
                else:
                    # This is an orphaned page that should be removed
                    orphaned_pages.append(page.id)
        
        # Remove orphaned pages and their descendants from the page map
        pages_to_remove = set()
        
        def collect_descendants(page_id: str):
            """Recursively collect all descendants of a page."""
            if page_id in self._page_map:
                pages_to_remove.add(page_id)
                page = self._page_map[page_id]
                for child_id in page.children:
                    collect_descendants(child_id)
        
        # Collect all orphaned pages and their descendants
        for orphaned_id in orphaned_pages:
            collect_descendants(orphaned_id)
        
        # Remove orphaned pages from the page map and title index
        for page_id in pages_to_remove:
            if page_id in self._page_map:
                page = self._page_map[page_id]
                # Remove from title index
                if page.title in self._title_to_id and self._title_to_id[page.title] == page_id:
                    del self._title_to_id[page.title]
                # Remove from page map
                del self._page_map[page_id]
    
    def _is_cache_valid(self) -> bool:
        """Check if the current cache is still valid."""
        if not self._last_update:
            return False
        return datetime.now() - self._last_update < self.cache_duration
    
    async def _load_from_cache(self):
        """Load page mapping from cache file."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Check cache timestamp
                cache_time = datetime.fromisoformat(cache_data.get("timestamp", ""))
                if datetime.now() - cache_time < self.cache_duration:
                    # Load pages from cache
                    self._page_map = {}
                    self._title_to_id = {}
                    
                    for page_data in cache_data.get("pages", []):
                        page = NotionPage(**page_data)
                        self._page_map[page.id] = page
                        self._title_to_id[page.title] = page.id
                    
                    self._last_update = cache_time
                    print(f"Loaded {len(self._page_map)} pages from cache")
                    return
        except Exception as e:
            print(f"Error loading cache: {e}")
        
        # Clear invalid cache
        self._page_map.clear()
        self._title_to_id.clear()
        self._last_update = None
    
    async def _save_to_cache(self):
        """Save current page mapping to cache file."""
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "pages": [asdict(page) for page in self._page_map.values()]
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            self._last_update = datetime.now()
            print(f"Saved {len(self._page_map)} pages to cache")
            
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    async def refresh_cache(self):
        """Force refresh the page mapping cache."""
        await self.get_all_pages(force_refresh=True)
    
    def get_page_by_id(self, page_id: str) -> Optional[NotionPage]:
        """Get a page by its ID (synchronous, uses cached data)."""
        return self._page_map.get(page_id)
    
    def search_pages_by_title(self, query: str, limit: int = 10) -> List[NotionPage]:
        """Search pages by title (synchronous, uses cached data)."""
        query_lower = query.lower()
        matches = []
        
        for page in self._page_map.values():
            if query_lower in page.title.lower() and not page.archived:
                matches.append(page)
                if len(matches) >= limit:
                    break
        
        return matches