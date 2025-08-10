"""
Enhanced search functionality for the Notion MCP server.
Provides multiple search strategies and improved relevance ranking.
"""

import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple, cast
from dataclasses import dataclass
from notion_client import Client
from notion_client.errors import APIResponseError
from .page_mapper import NotionPageMapper, NotionPage


@dataclass
class SearchResult:
    """Represents a search result with relevance scoring."""
    page: NotionPage
    relevance_score: float
    match_reasons: List[str]
    content_preview: str


class EnhancedNotionSearch:
    """Enhanced search functionality with multiple strategies and relevance ranking."""
    
    def __init__(self, notion_client: Client, page_mapper: NotionPageMapper):
        self.notion = notion_client
        self.page_mapper = page_mapper
    
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        Perform enhanced search using multiple strategies.
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            
        Returns:
            List of SearchResult objects ranked by relevance
        """
        # Strategy 1: Direct Notion API search
        api_results = await self._notion_api_search(query)
        
        # Strategy 2: Cached title/path search
        cached_results = await self._cached_search(query)
        
        # Strategy 3: Content-based search (for highly specific queries)
        content_results = await self._content_search(query)
        
        # Combine and rank all results
        all_results = self._combine_and_rank_results(
            query, api_results, cached_results, content_results
        )
        
        # Return top results
        return all_results[:max_results]
    
    async def _notion_api_search(self, query: str) -> List[Dict[str, Any]]:
        """Use Notion's built-in search API."""
        try:
            all_results = []
            has_more = True
            start_cursor = None
            
            while has_more and len(all_results) < 50:  # Limit to avoid excessive API calls
                search_params = {
                    "query": query,
                    "page_size": 100
                }
                if start_cursor:
                    search_params["start_cursor"] = start_cursor
                
                response = cast(Dict[str, Any], self.notion.search(**search_params))
                all_results.extend(response.get("results", []))
                
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
                
                # Add small delay to avoid rate limiting
                await asyncio.sleep(0.1)
            
            return all_results
            
        except APIResponseError as e:
            print(f"Error in Notion API search: {e}")
            return []
    
    async def _cached_search(self, query: str) -> List[NotionPage]:
        """Search through cached page titles and paths."""
        await self.page_mapper.get_all_pages()
        
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))
        
        matches = []
        
        for page in self.page_mapper._page_map.values():
            if page.archived:
                continue
                
            # Check title match
            title_words = set(re.findall(r'\w+', page.title.lower()))
            title_overlap = len(query_words.intersection(title_words))
            
            # Check path match
            path_text = " ".join(page.path).lower()
            path_words = set(re.findall(r'\w+', path_text))
            path_overlap = len(query_words.intersection(path_words))
            
            if title_overlap > 0 or path_overlap > 0:
                matches.append(page)
        
        return matches
    
    async def _content_search(self, query: str) -> List[Tuple[NotionPage, str]]:
        """
        Search through page content for highly specific queries.
        Only used for queries that seem very specific.
        """
        if not self._is_specific_query(query):
            return []
        
        await self.page_mapper.get_all_pages()
        
        # Limit content search to a reasonable number of pages
        candidate_pages = []
        for page in self.page_mapper._page_map.values():
            if not page.archived and len(candidate_pages) < 20:
                candidate_pages.append(page)
        
        content_matches = []
        
        for page in candidate_pages:
            try:
                # Get page content
                blocks = cast(Dict[str, Any], self.notion.blocks.children.list(block_id=page.id))
                
                content_text = self._extract_text_from_blocks(blocks.get("results", []))
                
                if self._content_matches_query(query, content_text):
                    content_matches.append((page, content_text))
                    
            except Exception as e:
                print(f"Error reading content for page {page.id}: {e}")
                continue
        
        return content_matches
    
    def _is_specific_query(self, query: str) -> bool:
        """Determine if a query is specific enough to warrant content search."""
        # Look for specific indicators
        specific_indicators = [
            len(query.split()) >= 3,  # Multi-word queries
            any(char in query for char in ['"', "'", ':', '=']),  # Quoted or structured queries
            re.search(r'\b(password|credential|config|setup|template)\b', query.lower()),  # Specific terms
            re.search(r'\b\w+@\w+\.\w+\b', query),  # Email addresses
            re.search(r'\b\d{4}-\d{2}-\d{2}\b', query),  # Dates
        ]
        
        return any(specific_indicators)
    
    def _content_matches_query(self, query: str, content: str) -> bool:
        """Check if content matches the query."""
        query_lower = query.lower()
        content_lower = content.lower()
        
        # Direct substring match
        if query_lower in content_lower:
            return True
        
        # Word-based matching
        query_words = set(re.findall(r'\w+', query_lower))
        content_words = set(re.findall(r'\w+', content_lower))
        
        # Require at least 70% of query words to be present
        overlap = len(query_words.intersection(content_words))
        return overlap >= len(query_words) * 0.7
    
    def _extract_text_from_blocks(self, blocks: List[Dict[str, Any]]) -> str:
        """Extract text content from Notion blocks."""
        text_parts = []
        
        for block in blocks:
            block_type = block.get("type", "")
            block_data = block.get(block_type, {})
            
            if "rich_text" in block_data:
                text = "".join([rt.get("plain_text", "") for rt in block_data["rich_text"]])
                if text.strip():
                    text_parts.append(text.strip())
        
        return " ".join(text_parts)
    
    def _combine_and_rank_results(
        self, 
        query: str, 
        api_results: List[Dict[str, Any]], 
        cached_results: List[NotionPage],
        content_results: List[Tuple[NotionPage, str]]
    ) -> List[SearchResult]:
        """Combine results from different strategies and rank by relevance."""
        
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))
        
        scored_results = {}
        
        # Process API results
        for i, result in enumerate(api_results):
            page_id = result["id"]
            
            # Convert to NotionPage if we have it cached
            cached_page = self.page_mapper.get_page_by_id(page_id)
            if cached_page:
                page = cached_page
            else:
                # Create minimal page object
                title = self._extract_title_from_result(result)
                page = NotionPage(
                    id=page_id,
                    title=title,
                    url=f"https://www.notion.so/{page_id.replace('-', '')}",
                    parent_type="unknown",
                    parent_id=None,
                    object_type=result.get("object", "page"),
                    created_time=result.get("created_time", ""),
                    last_edited_time=result.get("last_edited_time", ""),
                    archived=result.get("archived", False),
                    children=[],
                    path=[title],
                    depth=0
                )
            
            # Score based on API ranking (earlier results are more relevant)
            api_score = max(0.5, 1.0 - (i * 0.1))
            
            # Title relevance score
            title_score = self._calculate_title_relevance(query_words, page.title)
            
            total_score = api_score * 0.6 + title_score * 0.4
            
            if page_id not in scored_results or scored_results[page_id].relevance_score < total_score:
                # Try to get a content preview for API results
                content_preview = ""
                try:
                    blocks = cast(Dict[str, Any], self.notion.blocks.children.list(block_id=page_id))
                    content_text = self._extract_text_from_blocks(blocks.get("results", []))
                    if content_text:
                        content_preview = content_text[:300] + "..." if len(content_text) > 300 else content_text
                except Exception as e:
                    print(f"Error getting content preview for {page_id}: {e}")
                
                scored_results[page_id] = SearchResult(
                    page=page,
                    relevance_score=total_score,
                    match_reasons=["API search match"],
                    content_preview=content_preview
                )
        
        # Process cached results
        for page in cached_results:
            title_score = self._calculate_title_relevance(query_words, page.title)
            path_score = self._calculate_path_relevance(query_words, page.path)
            
            total_score = title_score * 0.7 + path_score * 0.3
            
            reasons = []
            if title_score > 0.3:
                reasons.append("Title match")
            if path_score > 0.3:
                reasons.append("Path match")
            
            if page.id not in scored_results or scored_results[page.id].relevance_score < total_score:
                # Try to get a content preview for cached results
                content_preview = ""
                try:
                    blocks = cast(Dict[str, Any], self.notion.blocks.children.list(block_id=page.id))
                    content_text = self._extract_text_from_blocks(blocks.get("results", []))
                    if content_text:
                        content_preview = content_text[:300] + "..." if len(content_text) > 300 else content_text
                except Exception as e:
                    print(f"Error getting content preview for {page.id}: {e}")
                
                scored_results[page.id] = SearchResult(
                    page=page,
                    relevance_score=total_score,
                    match_reasons=reasons,
                    content_preview=content_preview
                )
        
        # Process content results (highest priority)
        for page, content in content_results:
            content_score = self._calculate_content_relevance(query, content)
            
            # Content matches get a significant boost
            total_score = min(1.0, content_score + 0.3)
            
            preview = self._generate_content_preview(query, content)
            
            scored_results[page.id] = SearchResult(
                page=page,
                relevance_score=total_score,
                match_reasons=["Content match"],
                content_preview=preview
            )
        
        # Sort by relevance score
        return sorted(scored_results.values(), key=lambda x: x.relevance_score, reverse=True)
    
    def _extract_title_from_result(self, result: Dict[str, Any]) -> str:
        """Extract title from a Notion API result."""
        if result.get("properties"):
            for prop_name, prop_data in result["properties"].items():
                if prop_data.get("type") == "title" and prop_data.get("title"):
                    title_parts = [t.get("plain_text", "") for t in prop_data["title"]]
                    return "".join(title_parts).strip() or "Untitled"
        return "Untitled"
    
    def _calculate_title_relevance(self, query_words: set, title: str) -> float:
        """Calculate relevance score based on title matching."""
        title_words = set(re.findall(r'\w+', title.lower()))
        
        if not query_words or not title_words:
            return 0.0
        
        # Exact phrase match gets highest score
        if " ".join(query_words) in title.lower():
            return 1.0
        
        # Word overlap score
        overlap = len(query_words.intersection(title_words))
        return overlap / len(query_words)
    
    def _calculate_path_relevance(self, query_words: set, path: List[str]) -> float:
        """Calculate relevance score based on path matching."""
        path_text = " ".join(path).lower()
        path_words = set(re.findall(r'\w+', path_text))
        
        if not query_words or not path_words:
            return 0.0
        
        overlap = len(query_words.intersection(path_words))
        return overlap / len(query_words) * 0.8  # Slightly lower weight than title
    
    def _calculate_content_relevance(self, query: str, content: str) -> float:
        """Calculate relevance score based on content matching."""
        query_lower = query.lower()
        content_lower = content.lower()
        
        # Exact phrase match
        if query_lower in content_lower:
            return 0.9
        
        # Word-based scoring
        query_words = set(re.findall(r'\w+', query_lower))
        content_words = set(re.findall(r'\w+', content_lower))
        
        if not query_words:
            return 0.0
        
        overlap = len(query_words.intersection(content_words))
        return (overlap / len(query_words)) * 0.8
    
    def _generate_content_preview(self, query: str, content: str, max_length: int = 200) -> str:
        """Generate a preview of content around the matching text."""
        query_lower = query.lower()
        content_lower = content.lower()
        
        # Find the position of the query in content
        pos = content_lower.find(query_lower)
        if pos == -1:
            # If exact query not found, find first matching word
            query_words = re.findall(r'\w+', query_lower)
            for word in query_words:
                pos = content_lower.find(word)
                if pos != -1:
                    break
        
        if pos == -1:
            return content[:max_length] + "..." if len(content) > max_length else content
        
        # Extract context around the match
        start = max(0, pos - max_length // 2)
        end = min(len(content), pos + max_length // 2)
        
        preview = content[start:end]
        
        if start > 0:
            preview = "..." + preview
        if end < len(content):
            preview = preview + "..."
        
        return preview