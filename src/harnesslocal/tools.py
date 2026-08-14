import asyncio
import json
from dataclasses import asdict
from typing import Any
from . import workspace


async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool using the deepagents backend. Returns result as string."""
    backend = workspace.get_backend()
    if backend is None:
        return json.dumps({"error": "no_workspace", "message": "No workspace configured"})

    ws_path = workspace.get_workspace_path()

    try:
        if tool_name == "workspace_info":
            return json.dumps({"workspace": ws_path})

        elif tool_name == "ls":
            path = arguments.get("path", "/")
            result = backend.ls(path)
            if result.error:
                return json.dumps({"error": result.error})
            entries = result.entries or []
            return json.dumps({"entries": entries})

        elif tool_name == "read_file":
            file_path = arguments["file_path"]
            offset = arguments.get("offset", 0)
            limit = arguments.get("limit", 2000)
            result = backend.read(file_path, offset=offset, limit=limit)
            if result.error:
                return json.dumps({"error": result.error})
            return json.dumps({
                "content": result.file_data,
                "total_lines": result.total_lines,
                "next_offset": result.next_offset,
            })

        elif tool_name == "glob":
            pattern = arguments["pattern"]
            path = arguments.get("path")
            result = backend.glob(pattern, path=path)
            if result.error:
                return json.dumps({"error": result.error})
            return json.dumps({"matches": result.matches or [], "truncated": result.truncated})

        elif tool_name == "grep":
            pattern = arguments["pattern"]
            path = arguments.get("path")
            glob_filter = arguments.get("glob")
            result = backend.grep(pattern, path=path, glob=glob_filter)
            if result.error:
                return json.dumps({"error": result.error})
            return json.dumps({"matches": result.matches or [], "truncated": result.truncated})

        elif tool_name == "write_file":
            file_path = arguments["file_path"]
            content = arguments["content"]
            result = backend.write(file_path, content)
            if result.error:
                return json.dumps({"error": result.error})
            return json.dumps({"path": result.path, "status": "written"})

        elif tool_name == "edit_file":
            file_path = arguments["file_path"]
            old_string = arguments["old_string"]
            new_string = arguments["new_string"]
            replace_all = arguments.get("replace_all", False)
            result = backend.edit(file_path, old_string, new_string, replace_all=replace_all)
            if result.error:
                return json.dumps({"error": result.error})
            return json.dumps({"path": result.path, "occurrences": result.occurrences})

        elif tool_name == "execute":
            command = arguments["command"]
            timeout = arguments.get("timeout")
            kwargs = {"timeout": timeout} if timeout is not None else {}
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: backend.execute(command, **kwargs)
            )
            return json.dumps({
                "output": result.output,
                "exit_code": result.exit_code,
                "truncated": result.truncated,
            })

        else:
            return json.dumps({"error": "unknown_tool", "message": f"Unknown tool: {tool_name}"})

    except Exception as e:
        return json.dumps({"error": "execution_error", "message": str(e)})
