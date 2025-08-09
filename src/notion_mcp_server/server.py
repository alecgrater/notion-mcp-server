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

# Load environment variables
load_dotenv()

# Initialize Notion client
notion_token = os.getenv("NOTION_TOKEN")
if not notion_token:
    raise ValueError("NOTION_TOKEN environment variable is required")

notion = Client(auth=notion_token)

server = Server("notion-mcp-server")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available Notion resources.
    This will search for recent pages and databases that the integration has access to.
    """
    try:
        # Search for pages and databases
        search_results = notion.search(
            filter={"property": "object", "value": "page"},
            page_size=20
        )
        
        resources = []
        for result in search_results.get("results", []):
            page_id = result["id"]
            
            # Get page title
            title = "Untitled"
            if result.get("properties"):
                # For database pages, look for title property
                for prop_name, prop_data in result["properties"].items():
                    if prop_data.get("type") == "title" and prop_data.get("title"):
                        title_parts = [t.get("plain_text", "") for t in prop_data["title"]]
                        title = "".join(title_parts) or "Untitled"
                        break
            elif result.get("object") == "page" and result.get("parent", {}).get("type") == "workspace":
                # For top-level pages, get title from properties
                if result.get("properties", {}).get("title", {}).get("title"):
                    title_parts = [t.get("plain_text", "") for t in result["properties"]["title"]["title"]]
                    title = "".join(title_parts) or "Untitled"
            
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"notion://page/{page_id}"),
                    name=f"Notion Page: {title}",
                    description=f"Notion page: {title}",
                    mimeType="text/plain",
                )
            )
        
        return resources
    except APIResponseError as e:
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

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools for interacting with Notion.
    """
    return [
        types.Tool(
            name="ask-notion",
            description="Ask a question and get relevant information from your entire Notion workspace",
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
                    }
                },
                "required": ["question"],
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
        
        if not question:
            raise ValueError("Missing question")
        
        try:
            # Search through entire Notion workspace - we'll paginate through all results
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