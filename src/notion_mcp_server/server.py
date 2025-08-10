import asyncio
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio
from notion_client import Client
from notion_client.errors import APIResponseError
from dotenv import load_dotenv

from .page_mapper import NotionPageMapper
from .enhanced_search import EnhancedNotionSearch

# Load environment variables
load_dotenv()

# Initialize Notion client
notion_token = os.getenv("NOTION_TOKEN")
if not notion_token:
    raise ValueError("NOTION_TOKEN environment variable is required")

notion = Client(auth=notion_token)

# Initialize page mapper and enhanced search
page_mapper = NotionPageMapper(notion)
enhanced_search = EnhancedNotionSearch(notion, page_mapper)

server = Server("notion-mcp-server")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available Notion resources using the page mapper.
    """
    try:
        # Get all pages from the page mapper
        all_pages = await page_mapper.get_all_pages()
        
        resources = []
        for page in all_pages.values():
            if not page.archived:  # Only show non-archived pages
                resources.append(
                    types.Resource(
                        uri=AnyUrl(f"notion://page/{page.id}"),
                        name=f"Notion Page: {page.title}",
                        description=f"Notion page: {page.title}",
                        mimeType="text/plain",
                    )
                )
        
        return resources
    except Exception as e:
        print(f"Error listing Notion resources: {e}")
        return []

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific Notion page's content by its URI.
    """
    if uri.scheme != "notion":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")
    
    # Extract page ID from URI
    path_parts = (uri.path or "").strip("/").split("/")
    if len(path_parts) != 2 or path_parts[0] != "page":
        raise ValueError(f"Invalid Notion URI format: {uri}")
    
    page_id = path_parts[1]
    
    # Ensure page_id has proper UUID format with dashes
    if len(page_id) == 32 and "-" not in page_id:
        # Convert from 32-char string to UUID format
        page_id = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"
    
    try:
        # Get page content
        page = notion.pages.retrieve(page_id)
        
        # Get page title
        title = "Untitled"
        if page.get("properties"):
            for prop_name, prop_data in page["properties"].items():
                if prop_data.get("type") == "title" and prop_data.get("title"):
                    title_parts = [t.get("plain_text", "") for t in prop_data["title"]]
                    title = "".join(title_parts) or "Untitled"
                    break
        
        # Get page blocks (content)
        blocks = notion.blocks.children.list(block_id=page_id)
        content_parts = [f"# {title}\n"]
        
        for block in blocks.get("results", []):
            content_parts.append(_format_block(block))
        
        page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
        content_parts.append(f"\n\n**Source:** {page_url}")
        
        return "\n".join(content_parts)
    
    except APIResponseError as e:
        raise ValueError(f"Error reading Notion page: {e}")

def _format_block(block: Dict[str, Any]) -> str:
    """
    Format a Notion block into readable text.
    """
    block_type = block.get("type", "")
    block_data = block.get(block_type, {})
    
    if block_type == "paragraph":
        return _extract_rich_text(block_data.get("rich_text", []))
    elif block_type == "heading_1":
        text = _extract_rich_text(block_data.get("rich_text", []))
        return f"# {text}"
    elif block_type == "heading_2":
        text = _extract_rich_text(block_data.get("rich_text", []))
        return f"## {text}"
    elif block_type == "heading_3":
        text = _extract_rich_text(block_data.get("rich_text", []))
        return f"### {text}"
    elif block_type == "bulleted_list_item":
        text = _extract_rich_text(block_data.get("rich_text", []))
        return f"• {text}"
    elif block_type == "numbered_list_item":
        text = _extract_rich_text(block_data.get("rich_text", []))
        return f"1. {text}"
    elif block_type == "to_do":
        text = _extract_rich_text(block_data.get("rich_text", []))
        checked = "✓" if block_data.get("checked", False) else "☐"
        return f"{checked} {text}"
    elif block_type == "code":
        text = _extract_rich_text(block_data.get("rich_text", []))
        language = block_data.get("language", "")
        return f"```{language}\n{text}\n```"
    elif block_type == "quote":
        text = _extract_rich_text(block_data.get("rich_text", []))
        return f"> {text}"
    else:
        # For other block types, try to extract any rich text
        if "rich_text" in block_data:
            return _extract_rich_text(block_data["rich_text"])
        return ""

def _extract_rich_text(rich_text_array: List[Dict[str, Any]]) -> str:
    """
    Extract plain text from Notion rich text array.
    """
    return "".join([rt.get("plain_text", "") for rt in rich_text_array])

def _markdown_to_notion_blocks(content: str) -> List[Dict[str, Any]]:
    """
    Convert markdown content to Notion blocks.
    This is a simplified converter that handles basic markdown elements.
    """
    blocks = []
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            # Skip empty lines
            i += 1
            continue
        
        # Headers
        if line.startswith('### '):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": line[4:]}}]
                }
            })
        elif line.startswith('## '):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                }
            })
        elif line.startswith('# '):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                }
            })
        # Bulleted list
        elif line.startswith('- ') or line.startswith('* '):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                }
            })
        # Numbered list
        elif line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. ')):
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                }
            })
        # Code block
        elif line.startswith('```'):
            # Find the end of the code block
            language = line[3:].strip() if len(line) > 3 else ""
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            
            code_content = '\n'.join(code_lines)
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": code_content}}],
                    "language": language if language else "plain text"
                }
            })
        # Quote
        elif line.startswith('> '):
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                }
            })
        # Regular paragraph
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line}}]
                }
            })
        
        i += 1
    
    return blocks

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools for interacting with Notion.
    """
    return [
        types.Tool(
            name="ask-notion",
            description="Ask a question, fetch any relevant information from your entire Notion workspace, and have the question answered using those contents (and natural language processing by the LLM)",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question to search for in your Notion workspace"
                    },
                    "max_content_pages": {
                        "type": "integer",
                        "description": "Maximum number of most relevant pages to include full content from (default: 5, to keep response manageable)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    },
                    "use_enhanced_search": {
                        "type": "boolean",
                        "description": "Use enhanced search with multiple strategies and relevance ranking (default: true)",
                        "default": True
                    }
                },
                "required": ["question"],
            },
        ),
        types.Tool(
            name="write-to-notion",
            description="Create a new page or update an existing page in your Notion workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the page to create or update"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the page (supports markdown formatting)"
                    },
                    "parent_page_id": {
                        "type": "string",
                        "description": "Optional: ID of parent page to create the new page under. If not provided, creates a top-level page"
                    },
                    "page_id": {
                        "type": "string",
                        "description": "Optional: ID of existing page to update. If provided, updates this page instead of creating a new one"
                    }
                },
                "required": ["title", "content"],
            },
        ),
        types.Tool(
            name="list-notion-pages",
            description="List all pages in your Notion workspace with hierarchical structure",
            inputSchema={
                "type": "object",
                "properties": {
                    "show_hierarchy": {
                        "type": "boolean",
                        "description": "Show hierarchical structure with indentation (default: true)",
                        "default": True
                    },
                    "include_archived": {
                        "type": "boolean",
                        "description": "Include archived pages (default: false)",
                        "default": False
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to show (default: unlimited)",
                        "minimum": 0
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="find-notion-page",
            description="Find a specific Notion page by title or path",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the page to find"
                    },
                    "path": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Path hierarchy to the page (e.g., ['Parent Page', 'Child Page'])"
                    },
                    "exact_match": {
                        "type": "boolean",
                        "description": "Whether to require exact title match (default: false for fuzzy search)",
                        "default": False
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="refresh-notion-cache",
            description="Force refresh the Notion page mapping cache",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests for Notion operations.
    """
    if not arguments:
        raise ValueError("Missing arguments")
    
    if name == "ask-notion":
        question = arguments.get("question")
        max_content_pages = arguments.get("max_content_pages", 5)
        use_enhanced_search = arguments.get("use_enhanced_search", True)
        
        if not question:
            raise ValueError("Missing question")
        
        try:
            if use_enhanced_search:
                # Use enhanced search with multiple strategies
                search_results = await enhanced_search.search(question, max_content_pages)
                
                if not search_results:
                    return [types.TextContent(type="text", text=f"No relevant information found in your Notion workspace for: '{question}'")]
                
                # Format enhanced search results
                relevant_content = []
                sources = []
                
                for result in search_results:
                    page = result.page
                    
                    # Get full page content if not already in preview
                    page_content = result.content_preview
                    if not page_content or not page_content.strip():
                        try:
                            blocks = notion.blocks.children.list(block_id=page.id)
                            content_parts = []
                            
                            for block in blocks.get("results", []):
                                block_text = _format_block(block)
                                if block_text.strip():
                                    content_parts.append(block_text.strip())
                            
                            page_content = "\n".join(content_parts)
                            if not page_content.strip():
                                page_content = "No readable content found in this page"
                        except Exception as e:
                            print(f"Error reading page {page.id}: {e}")
                            page_content = f"Content unavailable (Error: {str(e)})"
                    
                    if page_content.strip():
                        match_info = f" ({', '.join(result.match_reasons)})" if result.match_reasons else ""
                        relevance_info = f" [Relevance: {result.relevance_score:.2f}]" if result.relevance_score > 0 else ""
                        
                        relevant_content.append(f"## From: {page.title}{match_info}{relevance_info}\n\n{page_content}")
                        sources.append(f"- [{page.title}]({page.url})")
                
                # Combine all relevant content
                combined_content = "\n\n---\n\n".join(relevant_content)
                
                # Add sources at the end
                sources_section = "\n\n## Sources\n\n" + "\n".join(sources)
                
                response_text = f"Based on your Notion workspace, here's what I found regarding: **{question}**\n\n{combined_content}{sources_section}"
                
                return [types.TextContent(type="text", text=response_text)]
            
            else:
                # Use original search method as fallback
                all_results = []
                has_more = True
                start_cursor = None
                
                while has_more:
                    search_params = {
                        "query": question,
                        "page_size": 100  # Max allowed by Notion API
                    }
                    if start_cursor:
                        search_params["start_cursor"] = start_cursor
                    
                    search_response = notion.search(**search_params)
                    all_results.extend(search_response.get("results", []))
                    
                    has_more = search_response.get("has_more", False)
                    start_cursor = search_response.get("next_cursor")
                
                if not all_results:
                    return [types.TextContent(type="text", text=f"No relevant information found in your Notion workspace for: '{question}'")]
                
                # Get full content from the most relevant pages (limited by max_content_pages)
                relevant_content = []
                sources = []
                
                for i, result in enumerate(all_results[:max_content_pages]):
                    page_id = result["id"]
                    
                    # Get page title
                    title = "Untitled"
                    if result.get("properties"):
                        for prop_name, prop_data in result["properties"].items():
                            if prop_data.get("type") == "title" and prop_data.get("title"):
                                title_parts = [t.get("plain_text", "") for t in prop_data["title"]]
                                title = "".join(title_parts) or "Untitled"
                                break
                    
                    # Get page URL
                    page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
                    
                    # Get full page content
                    try:
                        blocks = notion.blocks.children.list(block_id=page_id)
                        content_parts = []
                        
                        for block in blocks.get("results", []):
                            block_text = _format_block(block)
                            if block_text.strip():
                                content_parts.append(block_text.strip())
                        
                        page_content = "\n".join(content_parts)
                        
                        if page_content.strip():
                            relevant_content.append(f"## From: {title}\n\n{page_content}")
                            sources.append(f"- [{title}]({page_url})")
                    
                    except Exception as e:
                        print(f"Error reading page {page_id}: {e}")
                        continue
                
                # Add information about additional results if there are more
                additional_results_info = ""
                if len(all_results) > max_content_pages:
                    additional_count = len(all_results) - max_content_pages
                    additional_results_info = f"\n\n*Note: Found {len(all_results)} total matching pages. Showing detailed content from the top {max_content_pages} most relevant pages. {additional_count} additional pages also matched your query.*"
                
                if not relevant_content:
                    return [types.TextContent(type="text", text=f"Found {len(all_results)} matching pages, but couldn't retrieve readable content from them for: '{question}'")]
                
                # Combine all relevant content
                combined_content = "\n\n---\n\n".join(relevant_content)
                
                # Add sources at the end
                sources_section = "\n\n## Sources\n\n" + "\n".join(sources)
                
                response_text = f"Based on your Notion workspace, here's what I found regarding: **{question}**\n\n{combined_content}{sources_section}{additional_results_info}"
                
                return [types.TextContent(type="text", text=response_text)]
            
        except APIResponseError as e:
            return [types.TextContent(type="text", text=f"Error searching Notion: {e}")]
    
    elif name == "write-to-notion":
        title = arguments.get("title")
        content = arguments.get("content")
        parent_page_id = arguments.get("parent_page_id")
        page_id = arguments.get("page_id")
        
        if not title:
            raise ValueError("Missing title")
        if not content:
            raise ValueError("Missing content")
        
        try:
            # Convert markdown content to Notion blocks
            blocks = _markdown_to_notion_blocks(content)
            
            if page_id:
                # Update existing page
                # Ensure page_id has proper UUID format with dashes
                if len(page_id) == 32 and "-" not in page_id:
                    page_id = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"
                
                # Update page title
                notion.pages.update(
                    page_id=page_id,
                    properties={
                        "title": {
                            "title": [{"type": "text", "text": {"content": title}}]
                        }
                    }
                )
                
                # Clear existing content and add new blocks
                existing_blocks = notion.blocks.children.list(block_id=page_id)
                for block in existing_blocks.get("results", []):
                    notion.blocks.delete(block_id=block["id"])
                
                # Add new blocks
                if blocks:
                    notion.blocks.children.append(block_id=page_id, children=blocks)
                
                # Refresh cache after update
                await page_mapper.refresh_cache()
                
                page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
                return [types.TextContent(type="text", text=f"Successfully updated page '{title}' at {page_url}")]
            
            else:
                # Create new page
                parent = {"workspace": True}
                if parent_page_id:
                    # Ensure parent_page_id has proper UUID format with dashes
                    if len(parent_page_id) == 32 and "-" not in parent_page_id:
                        parent_page_id = f"{parent_page_id[:8]}-{parent_page_id[8:12]}-{parent_page_id[12:16]}-{parent_page_id[16:20]}-{parent_page_id[20:]}"
                    parent = {"page_id": parent_page_id}
                
                # Create the page
                new_page = notion.pages.create(
                    parent=parent,
                    properties={
                        "title": {
                            "title": [{"type": "text", "text": {"content": title}}]
                        }
                    },
                    children=blocks
                )
                
                # Refresh cache after creation
                await page_mapper.refresh_cache()
                
                new_page_id = new_page["id"]
                page_url = f"https://www.notion.so/{new_page_id.replace('-', '')}"
                return [types.TextContent(type="text", text=f"Successfully created new page '{title}' at {page_url}")]
        
        except APIResponseError as e:
            return [types.TextContent(type="text", text=f"Error writing to Notion: {e}")]
    
    elif name == "list-notion-pages":
        show_hierarchy = arguments.get("show_hierarchy", True)
        include_archived = arguments.get("include_archived", False)
        max_depth = arguments.get("max_depth")
        
        try:
            all_pages = await page_mapper.get_all_pages()
            
            # Filter pages
            filtered_pages = []
            for page in all_pages.values():
                if not include_archived and page.archived:
                    continue
                if max_depth is not None and page.depth > max_depth:
                    continue
                filtered_pages.append(page)
            
            # Sort by path for hierarchical display
            filtered_pages.sort(key=lambda p: (p.depth, p.path))
            
            if show_hierarchy:
                # Display with hierarchical indentation
                lines = []
                for page in filtered_pages:
                    indent = "  " * page.depth
                    status = " (archived)" if page.archived else ""
                    path_str = " > ".join(page.path) if len(page.path) > 1 else page.title
                    lines.append(f"{indent}• {page.title}{status}")
                    lines.append(f"{indent}  ID: {page.id}")
                    lines.append(f"{indent}  Path: {path_str}")
                    lines.append(f"{indent}  URL: {page.url}")
                    lines.append("")
                
                result_text = f"Found {len(filtered_pages)} pages in your Notion workspace:\n\n" + "\n".join(lines)
            else:
                # Simple list format
                lines = []
                for page in filtered_pages:
                    status = " (archived)" if page.archived else ""
                    lines.append(f"• {page.title}{status} - {page.id}")
                
                result_text = f"Found {len(filtered_pages)} pages:\n\n" + "\n".join(lines)
            
            return [types.TextContent(type="text", text=result_text)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error listing pages: {e}")]
    
    elif name == "find-notion-page":
        title = arguments.get("title")
        path = arguments.get("path")
        exact_match = arguments.get("exact_match", False)
        
        if not title and not path:
            raise ValueError("Either title or path must be provided")
        
        try:
            found_pages = []
            
            if path:
                # Search by path
                found_pages = await page_mapper.find_pages_by_path(path)
            elif title:
                # Search by title
                if exact_match:
                    page = await page_mapper.find_page_by_title(title, exact_match=True)
                    if page:
                        found_pages = [page]
                else:
                    # Use the synchronous search for fuzzy matching
                    await page_mapper.get_all_pages()  # Ensure cache is loaded
                    found_pages = page_mapper.search_pages_by_title(title, limit=10)
            
            if not found_pages:
                search_term = f"path {path}" if path else f"title '{title}'"
                return [types.TextContent(type="text", text=f"No pages found matching {search_term}")]
            
            # Format results
            lines = []
            for page in found_pages:
                status = " (archived)" if page.archived else ""
                path_str = " > ".join(page.path)
                lines.append(f"• {page.title}{status}")
                lines.append(f"  ID: {page.id}")
                lines.append(f"  Path: {path_str}")
                lines.append(f"  URL: {page.url}")
                lines.append(f"  Depth: {page.depth}")
                lines.append("")
            
            result_text = f"Found {len(found_pages)} matching page(s):\n\n" + "\n".join(lines)
            return [types.TextContent(type="text", text=result_text)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error finding page: {e}")]
    
    elif name == "refresh-notion-cache":
        try:
            await page_mapper.refresh_cache()
            hierarchy_info = await page_mapper.get_page_hierarchy_info()
            
            result_text = f"""Cache refreshed successfully!

Workspace Summary:
• Total pages: {hierarchy_info['total_pages']}
• Top-level pages: {hierarchy_info['top_level_pages']}
• Maximum depth: {hierarchy_info['max_depth']}
• Archived pages: {hierarchy_info['archived_pages']}

Pages by depth:"""
            
            for depth, count in hierarchy_info['pages_by_depth'].items():
                result_text += f"\n• Depth {depth}: {count} pages"
            
            if hierarchy_info['sample_paths']:
                result_text += "\n\nSample page paths:"
                for sample in hierarchy_info['sample_paths']:
                    result_text += f"\n• {sample['path']} (depth {sample['depth']})"
            
            return [types.TextContent(type="text", text=result_text)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error refreshing cache: {e}")]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Main entry point for the Notion MCP server."""
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="notion-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())