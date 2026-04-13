"""Storage layer for workspaces, collections, saved scenarios, baselines, and compare artifacts."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import (
    ArenaRunRecord,
    BaselineRecord,
    CollectionRecord,
    CompareArtifactRecord,
    SavedScenarioRecord,
    WorkspaceMemberRecord,
    WorkspaceRecord,
)


class OperatorStore:
    """Persist operator-layer objects for the agent testing workbench."""

    _ROLE_RANK = {
        "viewer": 1,
        "editor": 2,
        "admin": 3,
        "owner": 4,
    }

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
                CREATE TABLE IF NOT EXISTS workspace_members (
                    workspace_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, user_id)
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compare_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    collection_id TEXT NOT NULL,
                    candidate_run_id TEXT NOT NULL,
                    baseline_ids_json TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    actor_id TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_runs (
                    arena_run_id TEXT PRIMARY KEY,
                    agent_address TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    score REAL NOT NULL,
                    status TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    actor_id TEXT NOT NULL
                )
                """
            )

    def create_workspace(self, name: str, description: str = "", actor_id: str = "system") -> WorkspaceRecord:
        record = WorkspaceRecord(
            workspace_id=self._new_id("ws"),
            name=name,
            description=description,
            created_at=self._timestamp(),
        )
        owner_user_id = self._actor_user_id(actor_id)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO workspaces (workspace_id, name, description, created_at) VALUES (?, ?, ?, ?)",
                (record.workspace_id, record.name, record.description, record.created_at),
            )
            if owner_user_id != "system":
                conn.execute(
                    """
                    INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (record.workspace_id, owner_user_id, "owner", self._timestamp()),
                )
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="workspace.create",
                entity_type="workspace",
                entity_id=record.workspace_id,
                details={"name": record.name, "owner_user_id": owner_user_id},
            )
        return record

    def list_workspaces(self, user_id: Optional[str] = None) -> list[WorkspaceRecord]:
        with self._connect() as conn:
            if user_id:
                rows = conn.execute(
                    """
                    SELECT w.*
                    FROM workspaces w
                    WHERE EXISTS (
                        SELECT 1
                        FROM workspace_members m
                        WHERE m.workspace_id = w.workspace_id AND m.user_id = ?
                    )
                    OR NOT EXISTS (
                        SELECT 1
                        FROM workspace_members m2
                        WHERE m2.workspace_id = w.workspace_id
                    )
                    ORDER BY w.created_at DESC
                    """,
                    (user_id,),
                ).fetchall()
            else:
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

    def list_workspace_members(self, workspace_id: str) -> list[WorkspaceMemberRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT workspace_id, user_id, role, created_at
                FROM workspace_members
                WHERE workspace_id = ?
                ORDER BY created_at ASC
                """,
                (workspace_id,),
            ).fetchall()
        return [WorkspaceMemberRecord(**dict(row)) for row in rows]

    def get_workspace_member_role(self, workspace_id: str, user_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT role
                FROM workspace_members
                WHERE workspace_id = ? AND user_id = ?
                """,
                (workspace_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return str(row["role"])

    def upsert_workspace_member(
        self,
        workspace_id: str,
        user_id: str,
        role: str,
        *,
        actor_id: str = "system",
    ) -> WorkspaceMemberRecord:
        normalized_role = self._normalize_role(role)
        created_at = self._timestamp()
        with self._connect() as conn:
            current = conn.execute(
                """
                SELECT role
                FROM workspace_members
                WHERE workspace_id = ? AND user_id = ?
                """,
                (workspace_id, user_id),
            ).fetchone()
            if current is not None and current["role"] == "owner" and normalized_role != "owner":
                raise PermissionError("Cannot demote workspace owner")
            conn.execute(
                """
                INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id, user_id)
                DO UPDATE SET role = excluded.role
                """,
                (workspace_id, user_id, normalized_role, created_at),
            )
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="workspace.member.upsert",
                entity_type="workspace",
                entity_id=workspace_id,
                details={"user_id": user_id, "role": normalized_role},
            )
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT workspace_id, user_id, role, created_at
                FROM workspace_members
                WHERE workspace_id = ? AND user_id = ?
                """,
                (workspace_id, user_id),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to upsert workspace member")
        return WorkspaceMemberRecord(**dict(row))

    def remove_workspace_member(
        self,
        workspace_id: str,
        user_id: str,
        *,
        actor_id: str = "system",
    ) -> bool:
        with self._connect() as conn:
            current = conn.execute(
                """
                SELECT role
                FROM workspace_members
                WHERE workspace_id = ? AND user_id = ?
                """,
                (workspace_id, user_id),
            ).fetchone()
            if current is not None and current["role"] == "owner":
                raise PermissionError("Cannot remove workspace owner")
            deleted = conn.execute(
                """
                DELETE FROM workspace_members
                WHERE workspace_id = ? AND user_id = ?
                """,
                (workspace_id, user_id),
            ).rowcount
            if deleted > 0:
                self._insert_audit_event(
                    conn,
                    actor_id=actor_id,
                    action="workspace.member.remove",
                    entity_type="workspace",
                    entity_id=workspace_id,
                    details={"user_id": user_id},
                )
        return deleted > 0

    def ensure_workspace_access(
        self,
        workspace_id: str,
        user_id: str,
        *,
        min_role: str = "viewer",
    ) -> str:
        required_role = self._normalize_role(min_role)
        if self._workspace_is_legacy_public(workspace_id):
            return "owner"
        member_role = self.get_workspace_member_role(workspace_id, user_id)
        if member_role is None:
            raise PermissionError(
                f"user {user_id} is not a member of workspace {workspace_id}"
            )
        if self._ROLE_RANK[member_role] < self._ROLE_RANK[required_role]:
            raise PermissionError(
                f"user {user_id} requires {required_role} role in workspace {workspace_id}"
            )
        return member_role

    def update_workspace(
        self,
        workspace_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        actor_id: str = "system",
    ) -> WorkspaceRecord:
        workspace = self.get_workspace(workspace_id)
        updated = WorkspaceRecord(
            workspace_id=workspace.workspace_id,
            name=name if name is not None else workspace.name,
            description=description if description is not None else workspace.description,
            created_at=workspace.created_at,
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE workspaces
                SET name = ?, description = ?
                WHERE workspace_id = ?
                """,
                (updated.name, updated.description, workspace_id),
            )
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="workspace.update",
                entity_type="workspace",
                entity_id=workspace_id,
                details={"name": updated.name, "description": updated.description},
            )
        return updated

    def delete_workspace(self, workspace_id: str, actor_id: str = "system") -> bool:
        with self._connect() as conn:
            collection_ids = [
                row["collection_id"]
                for row in conn.execute(
                    "SELECT collection_id FROM collections WHERE workspace_id = ?",
                    (workspace_id,),
                ).fetchall()
            ]
            for collection_id in collection_ids:
                conn.execute("DELETE FROM saved_scenarios WHERE collection_id = ?", (collection_id,))
                conn.execute("DELETE FROM baselines WHERE collection_id = ?", (collection_id,))
                conn.execute("DELETE FROM compare_artifacts WHERE collection_id = ?", (collection_id,))
            conn.execute("DELETE FROM collections WHERE workspace_id = ?", (workspace_id,))
            conn.execute("DELETE FROM workspace_members WHERE workspace_id = ?", (workspace_id,))
            deleted = conn.execute(
                "DELETE FROM workspaces WHERE workspace_id = ?",
                (workspace_id,),
            ).rowcount
            if deleted > 0:
                self._insert_audit_event(
                    conn,
                    actor_id=actor_id,
                    action="workspace.delete",
                    entity_type="workspace",
                    entity_id=workspace_id,
                    details={"cascade_collections": len(collection_ids)},
                )
        return deleted > 0

    def create_collection(
        self,
        workspace_id: str,
        name: str,
        description: str = "",
        actor_id: str = "system",
    ) -> CollectionRecord:
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
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="collection.create",
                entity_type="collection",
                entity_id=record.collection_id,
                details={"workspace_id": workspace_id, "name": name},
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

    def update_collection(
        self,
        collection_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        actor_id: str = "system",
    ) -> CollectionRecord:
        collection = self.get_collection(collection_id)
        updated = CollectionRecord(
            collection_id=collection.collection_id,
            workspace_id=collection.workspace_id,
            name=name if name is not None else collection.name,
            description=description if description is not None else collection.description,
            created_at=collection.created_at,
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE collections
                SET name = ?, description = ?
                WHERE collection_id = ?
                """,
                (updated.name, updated.description, collection_id),
            )
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="collection.update",
                entity_type="collection",
                entity_id=collection_id,
                details={"name": updated.name, "description": updated.description},
            )
        return updated

    def delete_collection(self, collection_id: str, actor_id: str = "system") -> bool:
        with self._connect() as conn:
            deleted_scenarios = conn.execute(
                "DELETE FROM saved_scenarios WHERE collection_id = ?",
                (collection_id,),
            ).rowcount
            deleted_baselines = conn.execute(
                "DELETE FROM baselines WHERE collection_id = ?",
                (collection_id,),
            ).rowcount
            deleted_artifacts = conn.execute(
                "DELETE FROM compare_artifacts WHERE collection_id = ?",
                (collection_id,),
            ).rowcount
            deleted = conn.execute(
                "DELETE FROM collections WHERE collection_id = ?",
                (collection_id,),
            ).rowcount
            if deleted > 0:
                self._insert_audit_event(
                    conn,
                    actor_id=actor_id,
                    action="collection.delete",
                    entity_type="collection",
                    entity_id=collection_id,
                    details={
                        "deleted_scenarios": deleted_scenarios,
                        "deleted_baselines": deleted_baselines,
                        "deleted_artifacts": deleted_artifacts,
                    },
                )
        return deleted > 0

    def save_scenario(
        self,
        collection_id: str,
        name: str,
        config_path: str,
        input_text: str,
        actor_id: str = "system",
    ) -> SavedScenarioRecord:
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
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="scenario.create",
                entity_type="scenario",
                entity_id=record.scenario_id,
                details={"collection_id": collection_id, "name": name},
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
        actor_id: str = "system",
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
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="scenario.update",
                entity_type="scenario",
                entity_id=scenario_id,
                details={"name": updated.name},
            )
        return updated

    def delete_saved_scenario(self, scenario_id: str, actor_id: str = "system") -> bool:
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM saved_scenarios WHERE scenario_id = ?",
                (scenario_id,),
            )
            if result.rowcount > 0:
                self._insert_audit_event(
                    conn,
                    actor_id=actor_id,
                    action="scenario.delete",
                    entity_type="scenario",
                    entity_id=scenario_id,
                    details={},
                )
        return result.rowcount > 0

    def create_baseline(
        self,
        collection_id: str,
        run_id: str,
        label: str,
        actor_id: str = "system",
    ) -> BaselineRecord:
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
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="baseline.create",
                entity_type="baseline",
                entity_id=record.baseline_id,
                details={"collection_id": collection_id, "run_id": run_id, "label": label},
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

    def save_compare_artifact(
        self,
        collection_id: str,
        candidate_run_id: str,
        baseline_ids: list[str],
        payload: dict,
        *,
        filename: Optional[str] = None,
        actor_id: str = "system",
    ) -> CompareArtifactRecord:
        record = CompareArtifactRecord(
            artifact_id=self._new_id("cmp"),
            collection_id=collection_id,
            candidate_run_id=candidate_run_id,
            baseline_ids=baseline_ids,
            filename=filename or self._default_compare_filename(candidate_run_id),
            payload=payload,
            created_at=self._timestamp(),
            actor_id=actor_id,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO compare_artifacts (
                    artifact_id, collection_id, candidate_run_id, baseline_ids_json,
                    filename, payload_json, created_at, actor_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    record.collection_id,
                    record.candidate_run_id,
                    json.dumps(record.baseline_ids),
                    record.filename,
                    json.dumps(record.payload),
                    record.created_at,
                    record.actor_id,
                ),
            )
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="compare_artifact.create",
                entity_type="compare_artifact",
                entity_id=record.artifact_id,
                details={
                    "collection_id": collection_id,
                    "candidate_run_id": candidate_run_id,
                    "baseline_count": len(baseline_ids),
                    "filename": record.filename,
                },
            )
        return record

    def list_compare_artifacts(self, collection_id: str, limit: int = 50) -> list[CompareArtifactRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT artifact_id, collection_id, candidate_run_id, baseline_ids_json, filename, payload_json, created_at, actor_id
                FROM compare_artifacts
                WHERE collection_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (collection_id, limit),
            ).fetchall()
        return [self._row_to_compare_artifact(row) for row in rows]

    def get_compare_artifact(self, artifact_id: str) -> CompareArtifactRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT artifact_id, collection_id, candidate_run_id, baseline_ids_json, filename, payload_json, created_at, actor_id
                FROM compare_artifacts
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Compare artifact not found: {artifact_id}")
        return self._row_to_compare_artifact(row)

    def delete_compare_artifact(self, artifact_id: str, *, actor_id: str = "system") -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT collection_id, candidate_run_id, filename
                FROM compare_artifacts
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            ).fetchone()
            deleted = conn.execute(
                "DELETE FROM compare_artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).rowcount
            if deleted > 0:
                details = {"artifact_id": artifact_id}
                if row is not None:
                    details.update(
                        {
                            "collection_id": row["collection_id"],
                            "candidate_run_id": row["candidate_run_id"],
                            "filename": row["filename"],
                        }
                    )
                self._insert_audit_event(
                    conn,
                    actor_id=actor_id,
                    action="compare_artifact.delete",
                    entity_type="compare_artifact",
                    entity_id=artifact_id,
                    details=details,
                )
        return deleted > 0

    def delete_compare_artifacts_bulk(
        self,
        artifact_ids: list[str],
        *,
        actor_id: str = "system",
    ) -> int:
        unique_ids = [artifact_id for artifact_id in dict.fromkeys(artifact_ids) if artifact_id]
        if not unique_ids:
            return 0
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT artifact_id, collection_id
                FROM compare_artifacts
                WHERE artifact_id IN ({",".join("?" for _ in unique_ids)})
                """,
                unique_ids,
            ).fetchall()
            existing_ids = [row["artifact_id"] for row in rows]
            if not existing_ids:
                return 0
            conn.execute(
                f"""
                DELETE FROM compare_artifacts
                WHERE artifact_id IN ({",".join("?" for _ in existing_ids)})
                """,
                existing_ids,
            )
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="compare_artifact.bulk_delete",
                entity_type="compare_artifact",
                entity_id=existing_ids[0] if len(existing_ids) == 1 else "bulk",
                details={
                    "deleted_count": len(existing_ids),
                    "artifact_ids": existing_ids,
                },
            )
        return len(existing_ids)

    def prune_compare_artifacts(
        self,
        collection_id: str,
        keep_latest: int,
        *,
        actor_id: str = "system",
    ) -> int:
        keep_latest = max(0, int(keep_latest))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT artifact_id
                FROM compare_artifacts
                WHERE collection_id = ?
                ORDER BY created_at DESC
                """,
                (collection_id,),
            ).fetchall()
            artifact_ids = [row["artifact_id"] for row in rows]
            to_delete = artifact_ids[keep_latest:]
            if to_delete:
                conn.executemany(
                    "DELETE FROM compare_artifacts WHERE artifact_id = ?",
                    [(artifact_id,) for artifact_id in to_delete],
                )
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="compare_artifact.prune",
                entity_type="collection",
                entity_id=collection_id,
                details={
                    "keep_latest": keep_latest,
                    "deleted_count": len(to_delete),
                },
            )
        return len(to_delete)

    def create_arena_run(
        self,
        agent_address: str,
        scenario_id: str,
        score: float,
        status: str,
        *,
        metadata: Optional[dict] = None,
        actor_id: str = "system",
    ) -> ArenaRunRecord:
        record = ArenaRunRecord(
            arena_run_id=self._new_id("arena"),
            agent_address=agent_address,
            scenario_id=scenario_id,
            score=float(score),
            status=status,
            metadata=metadata or {},
            created_at=self._timestamp(),
            actor_id=actor_id,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO arena_runs (
                    arena_run_id, agent_address, scenario_id, score, status,
                    metadata_json, created_at, actor_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.arena_run_id,
                    record.agent_address,
                    record.scenario_id,
                    record.score,
                    record.status,
                    json.dumps(record.metadata),
                    record.created_at,
                    record.actor_id,
                ),
            )
            self._insert_audit_event(
                conn,
                actor_id=actor_id,
                action="arena.run.create",
                entity_type="arena_run",
                entity_id=record.arena_run_id,
                details={
                    "agent_address": agent_address,
                    "scenario_id": scenario_id,
                    "score": record.score,
                    "status": status,
                },
            )
        return record

    def list_arena_runs(self, limit: int = 50) -> list[ArenaRunRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT arena_run_id, agent_address, scenario_id, score, status, metadata_json, created_at, actor_id
                FROM arena_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            ArenaRunRecord(
                arena_run_id=row["arena_run_id"],
                agent_address=row["agent_address"],
                scenario_id=row["scenario_id"],
                score=float(row["score"]),
                status=row["status"],
                metadata=json.loads(row["metadata_json"]),
                created_at=row["created_at"],
                actor_id=row["actor_id"],
            )
            for row in rows
        ]

    def get_collection_summary(self, collection_id: str) -> dict:
        collection = self.get_collection(collection_id)
        workspace = self.get_workspace(collection.workspace_id)
        members = self.list_workspace_members(workspace.workspace_id)
        scenarios = self.list_saved_scenarios(collection_id)
        baselines = self.list_baselines(collection_id)
        return {
            "workspace": workspace.model_dump(),
            "workspace_members": [member.model_dump() for member in members],
            "collection": collection.model_dump(),
            "scenario_count": len(scenarios),
            "baseline_count": len(baselines),
            "scenarios": [scenario.model_dump() for scenario in scenarios],
            "baselines": [baseline.model_dump() for baseline in baselines],
        }

    def list_audit_events(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_id, actor_id, action, entity_type, entity_id, details_json, created_at
                FROM audit_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        events: list[dict] = []
        for row in rows:
            event = dict(row)
            event["details"] = json.loads(event.pop("details_json"))
            events.append(event)
        return events

    @staticmethod
    def _row_to_compare_artifact(row: sqlite3.Row) -> CompareArtifactRecord:
        return CompareArtifactRecord(
            artifact_id=row["artifact_id"],
            collection_id=row["collection_id"],
            candidate_run_id=row["candidate_run_id"],
            baseline_ids=json.loads(row["baseline_ids_json"]),
            filename=row["filename"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
            actor_id=row["actor_id"],
        )

    def _workspace_is_legacy_public(self, workspace_id: str) -> bool:
        with self._connect() as conn:
            count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM workspace_members
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
        member_count = int(count["count"]) if count is not None else 0
        return member_count == 0

    @classmethod
    def _normalize_role(cls, role: str) -> str:
        normalized = (role or "").strip().lower()
        if normalized not in cls._ROLE_RANK:
            raise ValueError(f"invalid role: {role}")
        return normalized

    @staticmethod
    def _actor_user_id(actor_id: str) -> str:
        token = (actor_id or "").strip()
        if not token:
            return "system"
        return token.split("#", 1)[0] or "system"

    def _insert_audit_event(
        self,
        conn: sqlite3.Connection,
        *,
        actor_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: dict,
    ) -> None:
        conn.execute(
            """
            INSERT INTO audit_events (event_id, actor_id, action, entity_type, entity_id, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._new_id("evt"),
                actor_id,
                action,
                entity_type,
                entity_id,
                json.dumps(details),
                self._timestamp(),
            ),
        )

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _default_compare_filename(candidate_run_id: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"openlvm-compare-{candidate_run_id}-{stamp}.json"
