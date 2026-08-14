import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "harness.db")

async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS workspace (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                path TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS approval_history (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                workspace TEXT NOT NULL,
                tool TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                decision TEXT,
                execution_status TEXT,
                result_summary TEXT
            )
        """)
        await db.commit()

async def get_workspace() -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT path FROM workspace WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def set_workspace(path: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO workspace (id, path) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET path = ?",
            (path, path)
        )
        await db.commit()

async def save_approval(approval_dict: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO approval_history 
               (id, created_at, resolved_at, workspace, tool, arguments_json, decision, execution_status, result_summary)
               VALUES (:id, :created_at, :resolved_at, :workspace, :tool, :arguments_json, :decision, :execution_status, :result_summary)
               ON CONFLICT(id) DO UPDATE SET
               resolved_at=:resolved_at, decision=:decision, execution_status=:execution_status, result_summary=:result_summary""",
            approval_dict
        )
        await db.commit()

async def get_history(limit: int = 100, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM approval_history ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
