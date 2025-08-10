# Notion MCP Server - Enhanced Search Improvements

## Overview

The Notion MCP server has been significantly enhanced with improved search functionality to address precision issues and provide more relevant results. The original implementation relied solely on Notion's basic keyword search, which often returned less relevant results.

## Key Improvements

### 1. Multi-Strategy Search Architecture

The new `EnhancedNotionSearch` class implements three complementary search strategies:

- **Strategy 1: Notion API Search** - Uses Notion's built-in search (existing functionality)
- **Strategy 2: Cached Title/Path Search** - Searches through cached page titles and hierarchical paths
- **Strategy 3: Content-Based Search** - Searches through actual page content for specific queries

### 2. Smart Query Detection

The system automatically detects when queries warrant deeper content search based on:
- Multi-word queries (3+ words)
- Specific terms like "password", "credential", "config", "setup", "template"
- Structured queries with quotes, colons, or equals signs
- Email addresses or date patterns

### 3. Advanced Relevance Scoring

Results are ranked using multiple factors:
- **Title Relevance**: Exact phrase matches score highest, word overlap scores proportionally
- **Path Relevance**: Matches in the page hierarchy path
- **Content Relevance**: Matches within page content with contextual scoring
- **API Ranking**: Earlier results from Notion's API get higher base scores

### 4. Enhanced Result Presentation

Search results now include:
- Relevance scores for transparency
- Match reasons (title match, path match, content match)
- Content previews showing context around matches
- Better source attribution with hierarchical paths

## Usage

### Basic Usage (Enhanced Search Enabled by Default)

```json
{
  "question": "acappella database password credentials",
  "max_content_pages": 5
}
```

### Advanced Usage with Options

```json
{
  "question": "how to update weekly keynote spreadsheet",
  "max_content_pages": 3,
  "use_enhanced_search": true
}
```

### Fallback to Original Search

```json
{
  "question": "your query here",
  "use_enhanced_search": false
}
```

## Example Improvements

### Before (Original Search)
Query: "acappella database password"
- Returned pages based only on basic keyword matching
- No relevance ranking beyond Notion's API order
- Often missed pages with relevant content but different titles

### After (Enhanced Search)
Query: "acappella database password"
- **Strategy 1**: Finds pages via Notion API
- **Strategy 2**: Searches cached titles/paths for "acappella", "database", "password"
- **Strategy 3**: Searches page content for credential information
- **Result**: Combines all matches, ranks by relevance, shows why each page matched

## Performance Considerations

- Content search is limited to 20 pages to avoid excessive API calls
- Caching reduces repeated API requests
- Smart query detection prevents unnecessary content searches
- Rate limiting with small delays between API calls

## Testing

Comprehensive test suite covers:
- Basic search functionality
- Query type detection
- Relevance scoring algorithms
- Content matching logic
- Preview generation

Run tests with:
```bash
uv run pytest tests/test_enhanced_search.py -v
```

## Configuration

The enhanced search is enabled by default but can be controlled:

- `use_enhanced_search: true` (default) - Uses multi-strategy search
- `use_enhanced_search: false` - Falls back to original search method
- `max_content_pages` - Controls how many pages to include full content from

## Future Enhancements

Potential improvements for future versions:
1. **Semantic Search**: Add embedding-based similarity search
2. **Learning**: Track which results users find most helpful
3. **Caching**: Cache search results for frequently asked questions
4. **Filters**: Add date, author, or tag-based filtering
5. **Fuzzy Matching**: Handle typos and variations in queries

## Files Modified

- `src/notion_mcp_server/enhanced_search.py` - New enhanced search implementation
- `src/notion_mcp_server/server.py` - Updated ask-notion tool integration
- `tests/test_enhanced_search.py` - Comprehensive test suite

## Backward Compatibility

The enhanced search is fully backward compatible:
- Existing queries work without modification
- Original search method available as fallback
- Same response format with additional metadata