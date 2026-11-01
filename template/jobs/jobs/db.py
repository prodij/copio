from typing import Any

from sqlalchemy import Engine, text


class MissingWorkspaceScope(Exception):
    pass


class ScopedDb:
    """The jobs' way to the database: every query must name one workspace.

    This guards against forgetting the scope. It is not an isolation boundary: it checks that
    `:workspace_id` appears in the SQL and is bound, not that every table in the query is filtered by it.
    """

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def execute(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if not params.get("workspace_id") or ":workspace_id" not in sql:
            raise MissingWorkspaceScope(sql)
        with self.engine.begin() as conn:
            result = conn.execute(text(sql), params)
            return [dict(row._mapping) for row in result] if result.returns_rows else []

    def unscoped_workspaces(self) -> list[dict[str, Any]]:
        """The single cross-workspace read: ready workspace ids, for fanning a job out."""
        with self.engine.connect() as conn:
            rows = conn.execute(text("select id from workspaces where status = 'ready' order by id"))
            return [dict(r._mapping) for r in rows]
