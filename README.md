# Notion MCP Server

A Model Context Protocol (MCP) server that provides access to your Notion workspace. This server allows you to ask natural language questions and get comprehensive answers by searching through your entire Notion workspace, making your Notion data accessible to MCP-compatible applications like Roo Code and other LLM clients.

## Features

- **Natural Language Queries**: Ask questions in plain English about any content in your Notion workspace
- **Comprehensive Search**: Searches through your entire Notion workspace, not just a subset
- **Page Hierarchy Mapping**: Automatically discovers and maps all pages with their hierarchical relationships
- **Intelligent Caching**: Caches page mappings to reduce API calls and improve performance
- **Rich Content Retrieval**: Gets full content from the most relevant pages with proper formatting
- **Source Citations**: Always includes links back to the original Notion pages
- **Rich Text Support**: Handles various Notion block types including headings, lists, code blocks, and more
- **Advanced Page Discovery**: Find pages by title, path, or hierarchical structure

## How It Works

### Page Hierarchy Mapping

The server automatically builds a comprehensive map of your entire Notion workspace:

1. **Discovery**: Fetches all pages and databases from your workspace
2. **Hierarchy Building**: Constructs parent-child relationships between pages
3. **Path Mapping**: Creates full paths from root to each page (e.g., "Projects > Q4 Planning > Meeting Notes")
4. **Intelligent Caching**: Stores mappings in `src/notion_mcp_server/resources/page_cache.json` with configurable expiration
5. **Runtime Updates**: Automatically refreshes cache when pages are created or updated

### Query Processing

The server provides multiple tools for interacting with your Notion content:

**ask-notion**: Natural language queries
1. Takes your natural language question
2. Searches through your entire Notion workspace for relevant content
3. Retrieves full content from the most relevant pages
4. Combines the information into a comprehensive answer
5. Provides source links to all pages used in the response

**Additional Tools**: Page management and discovery
- `list-notion-pages`: Browse all pages with hierarchical structure
- `find-notion-page`: Find specific pages by title or path
- `write-to-notion`: Create or update pages (with automatic cache refresh)
- `refresh-notion-cache`: Manually refresh the page mapping cache

## Components

### Resources

The server exposes Notion pages as resources with a custom `notion://` URI scheme:
- Each page is accessible via `notion://page/{page_id}`
- Resources include page titles and descriptions
- Content is returned as formatted markdown text

### Tools

The server implements several tools for comprehensive Notion interaction:

**ask-notion**: Ask any question about your Notion content
- Takes a natural language question as input
- Searches your entire Notion workspace for relevant information
- Returns a comprehensive answer with source citations
- Optionally limits the number of pages to include full content from (default: 5 most relevant)

**write-to-notion**: Create or update Notion pages
- Create new pages at the workspace level or under specific parent pages
- Update existing pages by ID
- Supports markdown formatting for content
- Automatically refreshes page mapping cache after changes

**list-notion-pages**: Browse your workspace structure
- Lists all pages with hierarchical indentation
- Filter by depth, archived status, and other criteria
- Shows page IDs, paths, and URLs for easy reference

**find-notion-page**: Locate specific pages
- Search by exact or fuzzy title matching
- Find pages by hierarchical path (e.g., ["Projects", "Q4 Planning"])
- Returns detailed page information including full path and metadata

**refresh-notion-cache**: Update page mappings
- Forces a refresh of the cached page hierarchy
- Useful when pages have been added/modified outside the server
- Provides summary statistics about your workspace structure

## Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- A Notion account with pages you want to access
- A Notion integration token

### Installation

1. Clone this repository:
```bash
git clone https://github.com/alecgrater/notion-mcp-server.git
cd notion-mcp-server
```

2. Install dependencies using uv:
```bash
uv sync --dev --all-extras
```

3. Create a Notion integration:
   - Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Give it a name (e.g., "MCP Server")
   - Select the workspace you want to access
   - Copy the "Internal Integration Token"

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your Notion token
```

5. Share pages with your integration:
   - In Notion, go to the pages you want the MCP server to access
   - Click "Share" in the top right
   - Click "Invite" and select your integration
   - Grant appropriate permissions

### Configuration

#### For Roo Code

Add the server to your Roo Code MCP configuration:

```json
{
  "mcpServers": {
    "notion": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/notion-mcp-server",
        "run",
        "notion-mcp-server"
      ],
      "env": {
        "NOTION_TOKEN": "your_notion_integration_token_here"
      }
    }
  }
}
```

#### For Other LLM Clients

For other MCP-compatible clients, configure the server with:
- **Command**: `uv`
- **Args**: `["--directory", "/path/to/notion-mcp-server", "run", "notion-mcp-server"]`
- **Environment**: Set `NOTION_TOKEN` to your integration token

Alternatively, if you have a `.env` file in the project directory, you can omit the environment configuration:

```json
{
  "mcpServers": {
    "notion": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/notion-mcp-server",
        "run",
        "notion-mcp-server"
      ]
    }
  }
}
```

## Usage

Once configured, you can use the Notion MCP server in your preferred LLM client by asking questions about your Notion content:

- "What are my current project priorities?"
- "Find information about the Q4 planning meeting"
- "What feedback did we get from the customer interviews?"
- "Show me my notes about the new product features"
- "What are the action items from last week's meetings?"

The server will automatically:
1. Search through your entire Notion workspace
2. Find the most relevant pages
3. Extract and combine the relevant information
4. Provide a comprehensive answer with links to source pages

## Development

### Running the Server

For development, you can run the server directly:

```bash
uv run notion-mcp-server
```

### Testing

#### Basic Tests

Run basic functionality tests to verify the page mapping system is properly set up:

```bash
uv run pytest tests/test_basic_pytest.py -v
```

This will test:
- Module imports and dependencies
- Page data structure creation
- Resources folder and cache file existence

#### Integration Tests

Test with your actual Notion workspace (requires `NOTION_TOKEN` environment variable):

```bash
uv run pytest tests/test_page_mapper_pytest.py -v
```

This will:
- Connect to your Notion workspace
- Fetch and map all pages with hierarchy
- Test caching functionality
- Verify search and discovery features

#### Run All Tests

To run all tests at once:
```bash
uv run pytest tests/ -v
```

#### VSCode Integration

The tests are now pytest-compatible and should work directly in VSCode's testing interface. Make sure VSCode is using the correct Python interpreter (`.venv/bin/python`) for the project.

#### MCP Inspector

You can also test the server using the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv --directory . run notion-mcp-server
```

This will open a web interface where you can test the server's tools and resources interactively.

### Building and Publishing

To prepare the package for distribution:

1. Sync dependencies and update lockfile:
```bash
uv sync
```

2. Build package distributions:
```bash
uv build
```

3. Publish to PyPI:
```bash
uv publish
```

## Troubleshooting

### Common Issues

1. **"NOTION_TOKEN environment variable is required"**
   - Make sure you've set the `NOTION_TOKEN` environment variable
   - Check that your `.env` file is in the correct location
   - Verify the token is valid and hasn't expired

2. **"No relevant information found"**
   - Ensure your integration has been shared with the pages you want to search
   - Check that the pages contain the content you're looking for
   - Try rephrasing your question or using broader terms

3. **"Error searching Notion"**
   - Verify your integration token is correct and hasn't expired
   - Check that your integration has the necessary permissions
   - Ensure you have an active internet connection

### Debugging

Since MCP servers run over stdio, debugging can be challenging. For the best debugging experience, use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector uv --directory . run notion-mcp-server
```

## Security

- Keep your Notion integration token secure and never commit it to version control
- Only share your integration with pages that you want the MCP server to access
- Regularly review and rotate your integration tokens
