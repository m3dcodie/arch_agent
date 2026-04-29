# MCP Server

The Model Context Protocol (MCP) server lets any MCP-compatible AI assistant call ADAG as a tool mid-conversation. This document covers what MCP is, the 5 tools ADAG exposes, how to connect various clients, and how to extend the server.

---

## Table of Contents

1. [What is MCP?](#1-what-is-mcp)
2. [The Five ADAG Tools](#2-the-five-adag-tools)
3. [Connecting Claude Desktop](#3-connecting-claude-desktop)
4. [Connecting VS Code Copilot](#4-connecting-vs-code-copilot)
5. [Connecting Other MCP Clients](#5-connecting-other-mcp-clients)
6. [Offline vs RAG-Enabled Behavior](#6-offline-vs-rag-enabled-behavior)
7. [Running the Server Manually](#7-running-the-server-manually)
8. [Extending the MCP Server](#8-extending-the-mcp-server)

---

## 1. What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io) is an open standard that lets AI assistants call external tools via a standardized JSON-RPC interface. When an LLM is configured with an MCP server, it can discover the server's tools and decide to call them based on the conversation context — without the user explicitly invoking a command.

**Why ADAG uses MCP:**

Without MCP, a developer asking Claude "is my Terraform compliant?" would need to:

1. Leave the conversation
2. Run `adag scan ./infra/` in a terminal
3. Copy the output back into the conversation

With MCP, Claude calls `check_terraform_file` directly, scans the file, and returns a structured result — all inline in the conversation. The developer never leaves their editor.

ADAG's MCP server uses [FastMCP](https://github.com/jlowin/fastmcp) and runs over stdio transport (no separate server process needed for basic use).

---

## 2. The Five ADAG Tools

### `check_terraform_file`

Scan a single Terraform file for policy violations.

```
Input:  path (str) — absolute or relative path to a .tf file
Output: dict with violations list, status, total_resources, summary
```

**Example interaction in Claude:**

> User: "Check `/home/me/infra/main.tf` for compliance issues."
>
> Claude calls: `check_terraform_file(path="/home/me/infra/main.tf")`
>
> Claude responds: "I found 2 violations: ..."

**Example return value:**

```json
{
  "status": "FAILED",
  "file_path": "/home/me/infra/main.tf",
  "total_resources": 3,
  "violations": [
    {
      "id": "V-001",
      "resource_type": "aws_db_instance",
      "resource_name": "main",
      "severity": "HIGH",
      "policy_ref": "delete_protection",
      "description": "Database instance does not have deletion protection enabled.",
      "line_number": 3,
      "remediation_hint": "Add 'deletion_protection = true' to the resource block."
    }
  ],
  "summary": "1 violation found: 1 HIGH, 0 MEDIUM, 0 LOW"
}
```

**Error return value (file not found):**

```json
{
  "error": "File not found: /home/me/infra/main.tf"
}
```

---

### `scan_terraform_dir`

Recursively scan all `.tf` files in a directory.

```
Input:  path (str) — absolute or relative path to a directory
Output: list of per-file result dicts (same structure as check_terraform_file)
```

**Example:**

```json
[
  {
    "file": "infra/main.tf",
    "status": "FAILED",
    "violations": [...]
  },
  {
    "file": "infra/database.tf",
    "status": "PASSED",
    "violations": []
  }
]
```

---

### `list_policies`

List all active policies with their metadata.

```
Input:  (none)
Output: list of policy summary dicts
```

**Example return value:**

```json
[
  {
    "id": "delete_protection",
    "title": "Deletion Protection Required",
    "severity": "HIGH",
    "filename": "delete_protection.md"
  },
  {
    "id": "encryption_at_rest",
    "title": "Encryption at Rest Required",
    "severity": "HIGH",
    "filename": "encryption_at_rest.md"
  }
]
```

---

### `query_rag`

Query the RAG vector store with a free-text question. **Mode 3 only.**

```
Input:  question (str) — natural language question about policies or architecture
Output: list of relevant chunks with content and distance scores
```

**Example:**

> User: "What does ADAG say about S3 encryption?"
>
> Claude calls: `query_rag(question="S3 encryption requirements policies")`

Returns policy chunks ranked by semantic similarity.

**When `USE_RAG=false`:**

```json
{
  "error": "RAG is not enabled. Set USE_RAG=true and ensure the RAG microservices are running to use this tool."
}
```

---

### `ingest_document`

Add a document to the RAG vector store. **Mode 3 only.**

```
Input:  path (str) — absolute path to a .md or .txt file
Output: ingestion confirmation dict
```

**Example:**

> User: "Add our internal database standards ADR to ADAG's knowledge base."
>
> Claude calls: `ingest_document(path="/home/me/architecture-docs/adr-001-database.md")`

**When `USE_RAG=false`:**

```json
{
  "error": "RAG is not enabled. Set USE_RAG=true and ensure the RAG microservices are running to ingest documents."
}
```

---

## 3. Connecting Claude Desktop

### Step 1: Find the config file

| OS      | Config path                                                       |
| ------- | ----------------------------------------------------------------- |
| macOS   | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux   | `~/.config/Claude/claude_desktop_config.json`                     |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json`                     |

### Step 2: Add the ADAG MCP server

```json
{
  "mcpServers": {
    "adag": {
      "command": "python",
      "args": ["-m", "adag.mcp_server"],
      "env": {
        "LLM_PROVIDER": "github-copilot",
        "GITHUB_COPILOT_TOKEN": "ghu_your_token_here",
        "USE_RAG": "false"
      }
    }
  }
}
```

If you have a `.env` file and prefer to use it:

```json
{
  "mcpServers": {
    "adag": {
      "command": "bash",
      "args": [
        "-c",
        "cd /path/to/arch_agent && source venv/bin/activate && python -m adag.mcp_server"
      ],
      "env": {}
    }
  }
}
```

### Step 3: Restart Claude Desktop

The server starts automatically when Claude Desktop launches. You should see "adag" in the tools list (hammer icon).

### Step 4: Try it

> "Can you check my Terraform file at `/home/me/projects/infra/main.tf` for any policy violations?"

Claude will call `check_terraform_file` and report violations in the conversation.

---

## 4. Connecting VS Code Copilot

VS Code Copilot Chat supports MCP servers through the workspace settings.

### Option A: Workspace settings (`.vscode/settings.json`)

```json
{
  "github.copilot.chat.mcp.enabled": true,
  "github.copilot.chat.mcp.servers": {
    "adag": {
      "command": "python",
      "args": ["-m", "adag.mcp_server"],
      "env": {
        "LLM_PROVIDER": "github-copilot",
        "GITHUB_COPILOT_TOKEN": "${env:GITHUB_COPILOT_TOKEN}",
        "USE_RAG": "false"
      }
    }
  }
}
```

### Option B: User settings (applies to all workspaces)

Add the same JSON to your VS Code user settings (`Ctrl+Shift+P` → "Open User Settings (JSON)").

### Using ADAG in Copilot Chat

Open Copilot Chat (`Ctrl+Shift+I`) and ask:

> "@adag scan the Terraform files in my infra/ directory"

---

## 5. Connecting Other MCP Clients

ADAG uses stdio transport, which is compatible with any MCP client that supports local process spawning.

**Generic stdio configuration:**

```json
{
  "command": "python",
  "args": ["-m", "adag.mcp_server"],
  "env": {
    "LLM_PROVIDER": "github-copilot",
    "GITHUB_COPILOT_TOKEN": "ghu_your_token_here"
  }
}
```

**Cursor:**

Add to `.cursor/mcp.json` in the project root:

```json
{
  "mcpServers": {
    "adag": {
      "command": "python",
      "args": ["-m", "adag.mcp_server"],
      "env": {
        "LLM_PROVIDER": "ollama",
        "OLLAMA_MODEL": "deepseek-r1:8b"
      }
    }
  }
}
```

**Continue.dev:**

Add to `~/.continue/config.json`:

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "python",
          "args": ["-m", "adag.mcp_server"],
          "env": {
            "LLM_PROVIDER": "github-copilot",
            "GITHUB_COPILOT_TOKEN": "ghu_your_token_here"
          }
        }
      }
    ]
  }
}
```

---

## 6. Offline vs RAG-Enabled Behavior

| Tool                   | `USE_RAG=false`                         | `USE_RAG=true`                                |
| ---------------------- | --------------------------------------- | --------------------------------------------- |
| `check_terraform_file` | Loads policies from `policies/` on disk | Queries ChromaDB for relevant policies        |
| `scan_terraform_dir`   | Loads policies from `policies/` on disk | Queries ChromaDB for relevant policies        |
| `list_policies`        | Reads all `.md` files from `policies/`  | Reads all `.md` files from `policies/` (same) |
| `query_rag`            | Returns error dict                      | Returns ranked chunks from ChromaDB           |
| `ingest_document`      | Returns error dict                      | Runs full ingestion pipeline                  |

The `check_terraform_file` and `scan_terraform_dir` tools always work in both modes. `query_rag` and `ingest_document` are Mode 3 only and fail gracefully (return an error dict rather than raising an exception) so the AI assistant can respond helpfully.

---

## 7. Running the Server Manually

For debugging or testing:

```bash
cd /path/to/arch_agent
source venv/bin/activate

# Offline mode
USE_RAG=false python -m adag.mcp_server

# RAG mode (requires running microservices)
USE_RAG=true python -m adag.mcp_server
```

The server uses stdio transport, so it reads JSON-RPC requests from stdin and writes responses to stdout. Use [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) for interactive testing:

```bash
npx @modelcontextprotocol/inspector python -m adag.mcp_server
```

---

## 8. Extending the MCP Server

Adding a new tool to the MCP server is straightforward. Open `adag/mcp_server.py` and add a function decorated with `@mcp.tool()`.

### Example: Add a `get_policy_details` tool

```python
@mcp.tool()
def get_policy_details(policy_id: str) -> dict:
    """
    Get full details for a specific policy by ID.

    Args:
        policy_id: The policy ID (e.g., 'delete_protection')

    Returns:
        Full policy details including requirements and examples.
    """
    policies = policy_loader.load_all_policies()
    for policy in policies:
        if policy.id == policy_id:
            return {
                "id": policy.id,
                "title": policy.title,
                "severity": policy.severity,
                "description": policy.description,
                "scope": policy.scope,
                "requirements": policy.requirements,
                "remediation": policy.remediation,
            }
    return {"error": f"Policy '{policy_id}' not found."}
```

That's all. FastMCP auto-discovers the tool, generates the JSON schema from the type hints, and exposes it to the connected AI client.

### Tool design guidelines

- **Return dicts, not exceptions.** MCP clients handle error dicts better than Python exceptions. Always return `{"error": "message"}` for failures.
- **Keep inputs simple.** Use `str`, `int`, `bool`, `list[str]`. Complex Pydantic models in function signatures work but produce verbose JSON schemas.
- **Write a clear docstring.** The docstring becomes the tool's description in the AI client's tool list. The AI reads it to decide when to call the tool.
- **Make it idempotent.** MCP tools may be called multiple times. Tools that modify state (like `ingest_document`) should be safe to retry.
