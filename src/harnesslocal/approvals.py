import asyncio
import uuid
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
from . import db

APPROVAL_TIMEOUT = 300  # seconds

TOOLS_REQUIRING_APPROVAL = {"write_file", "edit_file", "execute"}


@dataclass
class PendingApproval:
    id: str
    created_at: str
    workspace: str
    tool: str
    arguments: dict[str, Any]
    future: asyncio.Future = field(repr=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "workspace": self.workspace,
            "tool": self.tool,
            "arguments": self.arguments,
        }


# In-memory pending approvals
pending_approvals: dict[str, PendingApproval] = {}

# Mutation lock for serializing state-changing operations
mutation_lock = asyncio.Lock()

# SSE subscribers
_sse_queues: list[asyncio.Queue] = []


def add_sse_queue(queue: asyncio.Queue) -> None:
    _sse_queues.append(queue)


def remove_sse_queue(queue: asyncio.Queue) -> None:
    if queue in _sse_queues:
        _sse_queues.remove(queue)


async def broadcast_sse(event: str, data: dict) -> None:
    msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    for q in _sse_queues:
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


async def request_approval(tool: str, arguments: dict, workspace: str) -> dict:
    """Create a pending approval and wait for resolution. Returns result dict."""
    approval_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    approval = PendingApproval(
        id=approval_id,
        created_at=now,
        workspace=workspace,
        tool=tool,
        arguments=arguments,
        future=future,
    )
    pending_approvals[approval_id] = approval

    # Save to DB as pending
    await db.save_approval({
        "id": approval_id,
        "created_at": now,
        "resolved_at": None,
        "workspace": workspace,
        "tool": tool,
        "arguments_json": json.dumps(arguments),
        "decision": "pending",
        "execution_status": None,
        "result_summary": None,
    })

    # Broadcast to SSE
    await broadcast_sse("approval_new", approval.to_dict())

    try:
        result = await asyncio.wait_for(future, timeout=APPROVAL_TIMEOUT)
        return result
    except asyncio.TimeoutError:
        pending_approvals.pop(approval_id, None)
        resolved_at = datetime.now(timezone.utc).isoformat()
        await db.save_approval({
            "id": approval_id,
            "created_at": now,
            "resolved_at": resolved_at,
            "workspace": workspace,
            "tool": tool,
            "arguments_json": json.dumps(arguments),
            "decision": "timeout",
            "execution_status": "approval_timeout",
            "result_summary": "Approval timed out after 300 seconds",
        })
        await broadcast_sse("approval_resolved", {
            "id": approval_id, "decision": "timeout"
        })
        return {"error": "approval_timeout", "message": "Approval timed out after 300 seconds"}


async def resolve_approval(approval_id: str, decision: str, executor) -> dict:
    """Resolve a pending approval. executor is an async callable for 'approve'."""
    approval = pending_approvals.pop(approval_id, None)
    if approval is None:
        return {"error": "not_found", "message": "Approval not found or already resolved"}

    resolved_at = datetime.now(timezone.utc).isoformat()

    if decision == "approve":
        # Execute under mutation lock
        async with mutation_lock:
            try:
                exec_result = await executor(approval.tool, approval.arguments)
                result = {
                    "decision": "approved",
                    "execution_status": "success",
                    "result": exec_result,
                }
                await db.save_approval({
                    "id": approval.id,
                    "created_at": approval.created_at,
                    "resolved_at": resolved_at,
                    "workspace": approval.workspace,
                    "tool": approval.tool,
                    "arguments_json": json.dumps(approval.arguments),
                    "decision": "approved",
                    "execution_status": "success",
                    "result_summary": json.dumps(exec_result)[:500],
                })
            except Exception as e:
                result = {
                    "decision": "approved",
                    "execution_status": "error",
                    "error": str(e),
                }
                await db.save_approval({
                    "id": approval.id,
                    "created_at": approval.created_at,
                    "resolved_at": resolved_at,
                    "workspace": approval.workspace,
                    "tool": approval.tool,
                    "arguments_json": json.dumps(approval.arguments),
                    "decision": "approved",
                    "execution_status": "error",
                    "result_summary": str(e)[:500],
                })
    else:
        result = {
            "decision": "declined",
            "execution_status": "declined",
            "message": "Operation declined by user",
        }
        await db.save_approval({
            "id": approval.id,
            "created_at": approval.created_at,
            "resolved_at": resolved_at,
            "workspace": approval.workspace,
            "tool": approval.tool,
            "arguments_json": json.dumps(approval.arguments),
            "decision": "declined",
            "execution_status": "declined",
            "result_summary": "Declined by user",
        })

    # Resolve the future
    if not approval.future.done():
        approval.future.set_result(result)

    # Broadcast
    await broadcast_sse("approval_resolved", {
        "id": approval.id, "decision": decision
    })

    return result


def has_pending_approvals() -> bool:
    return len(pending_approvals) > 0


def get_pending_list() -> list[dict]:
    return [a.to_dict() for a in pending_approvals.values()]
