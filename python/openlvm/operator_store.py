"""Storage layer for workspaces, collections, saved scenarios, and baselines."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import BaselineRecord, CollectionRecord, SavedScenarioRecord, WorkspaceRecord


class OperatorStore:
    """Persist operator-layer objects for the agent testing workbench."""

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            root_dir = Path(__file__).resolve().parents[2]
            db_path = root_dir / ".openlvm" / "operator_store.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    collection_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    collection_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    config_path TEXT NOT NULL,
                    input_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS baselines (
                    baseline_id TEXT PRIMARY KEY,
                    collection_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def create_workspace(self, name: str, description: str = "") -> WorkspaceRecord:
        record = WorkspaceRecord(
            workspace_id=self._new_id("ws"),
            name=name,
            description=description,
            created_at=self._timestamp(),
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO workspaces (workspace_id, name, description, created_at) VALUES (?, ?, ?, ?)",
                (record.workspace_id, record.name, record.description, record.created_at),
            )
        return record

    def list_workspaces(self) -> list[WorkspaceRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM workspaces ORDER BY created_at DESC").fetchall()
        return [WorkspaceRecord(**dict(row)) for row in rows]

    def get_workspace(self, workspace_id: str) -> WorkspaceRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Workspace not found: {workspace_id}")
        return WorkspaceRecord(**dict(row))

    def create_collection(self, workspace_id: str, name: str, description: str = "") -> CollectionRecord:
        record = CollectionRecord(
            collection_id=self._new_id("col"),
            workspace_id=workspace_id,
            name=name,
            description=description,
            created_at=self._timestamp(),
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO collections (collection_id, workspace_id, name, description, created_at) VALUES (?, ?, ?, ?, ?)",
                (record.collection_id, record.workspace_id, record.name, record.description, record.created_at),
            )
        return record

    def list_collections(self, workspace_id: Optional[str] = None) -> list[CollectionRecord]:
        with self._connect() as conn:
            if workspace_id:
                rows = conn.execute(
                    "SELECT * FROM collections WHERE workspace_id = ? ORDER BY created_at DESC",
                    (workspace_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM collections ORDER BY created_at DESC").fetchall()
        return [CollectionRecord(**dict(row)) for row in rows]

    def save_scenario(self, collection_id: str, name: str, config_path: str, input_text: str) -> SavedScenarioRecord:
        record = SavedScenarioRecord(
            scenario_id=self._new_id("scn"),
            collection_id=collection_id,
            name=name,
            config_path=config_path,
            input_text=input_text,
            created_at=self._timestamp(),
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO saved_scenarios (scenario_id, collection_id, name, config_path, input_text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.scenario_id,
                    record.collection_id,
                    record.name,
                    record.config_path,
                    record.input_text,
                    record.created_at,
                ),
            )
        return record

    def list_saved_scenarios(self, collection_id: str) -> list[SavedScenarioRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM saved_scenarios WHERE collection_id = ? ORDER BY created_at DESC",
                (collection_id,),
            ).fetchall()
        return [SavedScenarioRecord(**dict(row)) for row in rows]

    def get_saved_scenario(self, scenario_id: str) -> SavedScenarioRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM saved_scenarios WHERE scenario_id = ?",
                (scenario_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Saved scenario not found: {scenario_id}")
        return SavedScenarioRecord(**dict(row))

    def update_saved_scenario(
        self,
        scenario_id: str,
        *,
        name: Optional[str] = None,
        config_path: Optional[str] = None,
        input_text: Optional[str] = None,
    ) -> SavedScenarioRecord:
        scenario = self.get_saved_scenario(scenario_id)
        updated = SavedScenarioRecord(
            scenario_id=scenario.scenario_id,
            collection_id=scenario.collection_id,
            name=name if name is not None else scenario.name,
            config_path=config_path if config_path is not None else scenario.config_path,
            input_text=input_text if input_text is not None else scenario.input_text,
            created_at=scenario.created_at,
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE saved_scenarios
                SET name = ?, config_path = ?, input_text = ?
                WHERE scenario_id = ?
                """,
                (
                    updated.name,
                    updated.config_path,
                    updated.input_text,
                    scenario_id,
                ),
            )
        return updated

    def delete_saved_scenario(self, scenario_id: str) -> bool:
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM saved_scenarios WHERE scenario_id = ?",
                (scenario_id,),
            )
        return result.rowcount > 0

    def create_baseline(self, collection_id: str, run_id: str, label: str) -> BaselineRecord:
        record = BaselineRecord(
            baseline_id=self._new_id("base"),
            collection_id=collection_id,
            run_id=run_id,
            label=label,
            created_at=self._timestamp(),
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO baselines (baseline_id, collection_id, run_id, label, created_at) VALUES (?, ?, ?, ?, ?)",
                (record.baseline_id, record.collection_id, record.run_id, record.label, record.created_at),
            )
        return record

    def list_baselines(self, collection_id: str) -> list[BaselineRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM baselines WHERE collection_id = ? ORDER BY created_at DESC",
                (collection_id,),
            ).fetchall()
        return [BaselineRecord(**dict(row)) for row in rows]

    def get_collection(self, collection_id: str) -> CollectionRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM collections WHERE collection_id = ?",
                (collection_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Collection not found: {collection_id}")
        return CollectionRecord(**dict(row))

    def get_collection_summary(self, collection_id: str) -> dict:
        collection = self.get_collection(collection_id)
        workspace = self.get_workspace(collection.workspace_id)
        scenarios = self.list_saved_scenarios(collection_id)
        baselines = self.list_baselines(collection_id)
        return {
            "workspace": workspace.model_dump(),
            "collection": collection.model_dump(),
            "scenario_count": len(scenarios),
            "baseline_count": len(baselines),
            "scenarios": [scenario.model_dump() for scenario in scenarios],
            "baselines": [baseline.model_dump() for baseline in baselines],
        }

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
