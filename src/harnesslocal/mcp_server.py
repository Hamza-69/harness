import json
from typing import Any
from mcp.server.lowlevel import Server
import mcp.types as types

from . import workspace
from .approvals import TOOLS_REQUIRING_APPROVAL, request_approval
from .tools import execute_tool


TOOL_DEFINITIONS = [
    types.Tool(
        name="workspace_info",
        description="Return the active workspace directory.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    types.Tool(
        name="ls",
        description="List files and directories at a path in the workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to list (relative to workspace root). Defaults to '/'."}
            },
            "required": [],
        },
    ),
    types.Tool(
        name="read_file",
        description="Read the contents of a file in the workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to read."},
                "offset": {"type": "integer", "description": "Line offset to start reading from. Defaults to 0."},
                "limit": {"type": "integer", "description": "Maximum number of lines to read. Defaults to 2000."},
            },
            "required": ["file_path"],
        },
    ),
    types.Tool(
        name="glob",
        description="Find files matching a glob pattern in the workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')."},
                "path": {"type": "string", "description": "Base path to search from."},
            },
            "required": ["pattern"],
        },
    ),
    types.Tool(
        name="grep",
        description="Search for a text pattern across files in the workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Text pattern to search for."},
                "path": {"type": "string", "description": "Path to search within."},
                "glob": {"type": "string", "description": "Glob filter for files."},
            },
            "required": ["pattern"],
        },
    ),
    types.Tool(
        name="write_file",
        description="Write content to a file in the workspace. Requires human approval.",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to write."},
                "content": {"type": "string", "description": "Content to write to the file."},
            },
            "required": ["file_path", "content"],
        },
    ),
    types.Tool(
        name="edit_file",
        description="Edit a file by replacing a string. Requires human approval.",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to edit."},
                "old_string": {"type": "string", "description": "Exact string to find and replace."},
                "new_string": {"type": "string", "description": "Replacement string."},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences. Defaults to false."},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    ),
    types.Tool(
        name="execute",
        description="Execute a shell command in the workspace. Requires human approval.",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
                "timeout": {"type": "integer", "description": "Timeout in seconds."},
            },
            "required": ["command"],
        },
    ),
]


async def handle_list_tools(ctx, params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOL_DEFINITIONS)


async def handle_call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
    tool_name = params.name
    arguments = params.arguments or {}
    ws_path = workspace.get_workspace_path()

    if ws_path is None and tool_name != "workspace_info":
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps({"error": "no_workspace", "message": "No workspace configured. Set a workspace first."}))],
            isError=True,
        )

    if tool_name in TOOLS_REQUIRING_APPROVAL:
        # Request human approval - this blocks until approved/declined/timeout
        result = await request_approval(
            tool=tool_name,
            arguments=arguments,
            workspace=ws_path or "",
        )

        if "error" in result:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps(result))],
                isError=True,
            )

        # The executor in resolve_approval already ran the tool
        exec_result = result.get("result", result)
        if isinstance(exec_result, str):
            text = exec_result
        else:
            text = json.dumps(exec_result)
        is_error = result.get("execution_status") == "error"
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)],
            isError=is_error,
        )
    else:
        # Auto-execute read-only tools
        result_text = await execute_tool(tool_name, arguments)
        parsed = json.loads(result_text)
        is_error = "error" in parsed
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=result_text)],
            isError=is_error,
        )


def create_mcp_server() -> Server:
    """Create and configure the MCP server."""
    server = Server(
        "pc-harness",
        on_list_tools=handle_list_tools,
        on_call_tool=handle_call_tool,
    )
    return server
