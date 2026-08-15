from deepagents.backends import LocalShellBackend
from . import db
import asyncio
import subprocess

# Global state
_backend: LocalShellBackend | None = None
_workspace_path: str | None = None
_lock = asyncio.Lock()

def get_backend() -> LocalShellBackend | None:
    return _backend

def get_workspace_path() -> str | None:
    return _workspace_path

async def set_workspace(path: str) -> None:
    global _backend, _workspace_path
    async with _lock:
        _backend = LocalShellBackend(
            root_dir=path,
            virtual_mode=True,
            inherit_env=True,
        )
        _workspace_path = path
        await db.set_workspace(path)

async def load_workspace() -> str | None:
    """Load workspace from DB on startup."""
    path = await db.get_workspace()
    if path:
        await set_workspace(path)
    return path

import os

def choose_folder() -> str | None:
    """Open native folder picker using zenity."""
    try:
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"
        result = subprocess.run(
            ["zenity", "--file-selection", "--directory", "--title=Choose Project Folder"],
            capture_output=True, text=True, timeout=120, env=env
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
