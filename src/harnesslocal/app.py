import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from . import db
from . import workspace
from . import approvals
from .tools import execute_tool
from .mcp_server import create_mcp_server


STATIC_DIR = Path(__file__).parent / "static"


# Create MCP server and get Starlette ASGI app
mcp_server = create_mcp_server()
mcp_app = mcp_server.streamable_http_app(streamable_http_path="/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    await db.init_db()
    # Load workspace from DB
    await workspace.load_workspace()
    # Start MCP session manager (mounted apps don't get their lifespan called)
    async with mcp_server._session_manager.run():
        yield


app = FastAPI(title="PC Harness", lifespan=lifespan)


# Mount MCP at /mcp
app.mount("/mcp", mcp_app)


# --- API Routes ---

@app.get("/api/approvals")
async def get_approvals():
    return JSONResponse(approvals.get_pending_list())


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: str):
    result = await approvals.resolve_approval(
        approval_id, "approve", execute_tool
    )
    return JSONResponse(result)


@app.post("/api/approvals/{approval_id}/decline")
async def decline(approval_id: str):
    result = await approvals.resolve_approval(
        approval_id, "decline", execute_tool
    )
    return JSONResponse(result)


@app.get("/api/history")
async def get_history(limit: int = 100, offset: int = 0):
    history = await db.get_history(limit=limit, offset=offset)
    return JSONResponse(history)


@app.get("/api/workspace")
async def get_workspace():
    path = workspace.get_workspace_path()
    return JSONResponse({"path": path})


@app.post("/api/workspace")
async def set_workspace_route(request: Request):
    if approvals.has_pending_approvals():
        return JSONResponse(
            {"error": "pending_approvals", "message": "Cannot switch workspace while approvals are pending"},
            status_code=409,
        )
    body = await request.json()
    path = body.get("path")
    if not path:
        return JSONResponse({"error": "missing_path"}, status_code=400)
    await workspace.set_workspace(path)
    await approvals.broadcast_sse("workspace_changed", {"path": path})
    return JSONResponse({"path": path})


@app.post("/api/workspace/choose")
async def choose_workspace():
    if approvals.has_pending_approvals():
        return JSONResponse(
            {"error": "pending_approvals", "message": "Cannot switch workspace while approvals are pending"},
            status_code=409,
        )
    # Run zenity in a thread to avoid blocking
    loop = asyncio.get_running_loop()
    path = await loop.run_in_executor(None, workspace.choose_folder)
    if path is None:
        return JSONResponse({"path": None, "message": "No folder selected"})
    await workspace.set_workspace(path)
    await approvals.broadcast_sse("workspace_changed", {"path": path})
    return JSONResponse({"path": path})


@app.get("/events")
async def sse_events():
    queue = asyncio.Queue(maxsize=50)
    approvals.add_sse_queue(queue)

    async def event_generator():
        try:
            while True:
                msg = await queue.get()
                yield msg
        except asyncio.CancelledError:
            pass
        finally:
            approvals.remove_sse_queue(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Serve static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
