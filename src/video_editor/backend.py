from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


class BackendNotConfigured(RuntimeError):
    pass


class BackendRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    secret_key: str
    timeout_sec: float = 20.0

    @classmethod
    def from_env(cls) -> "SupabaseSettings":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        key = (
            os.getenv("SUPABASE_SECRET_KEY", "").strip()
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        )
        if not url or not key:
            raise BackendNotConfigured(
                "Set SUPABASE_URL and SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY)."
            )
        return cls(
            url=url,
            secret_key=key,
            timeout_sec=float(os.getenv("SUPABASE_TIMEOUT_SEC", "20")),
        )


class SupabaseRestClient:
    """Small PostgREST client for the AutoEditor backend.

    The secret/service-role key must only be used server-side.
    """

    def __init__(self, settings: SupabaseSettings) -> None:
        self.settings = settings

    @classmethod
    def from_env(cls) -> "SupabaseRestClient":
        return cls(SupabaseSettings.from_env())

    @staticmethod
    def configured() -> bool:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = (
            os.getenv("SUPABASE_SECRET_KEY", "").strip()
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        )
        return bool(url and key)

    @property
    def _headers(self) -> dict[str, str]:
        key = self.settings.secret_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, Any] | None = None,
        payload: Any = None,
        prefer: str | None = None,
    ) -> Any:
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        url = f"{self.settings.url}/rest/v1/{table}"
        try:
            with httpx.Client(timeout=self.settings.timeout_sec) as client:
                response = client.request(
                    method,
                    url,
                    params=params,
                    json=payload,
                    headers=headers,
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:2000]
            raise BackendRequestError(
                f"Supabase {method} {table} failed: {exc.response.status_code} {body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise BackendRequestError(f"Supabase request failed: {exc}") from exc

        if not response.content:
            return None
        return response.json()

    def rpc(self, function_name: str, payload: dict[str, Any]) -> Any:
        headers = dict(self._headers)
        url = f"{self.settings.url}/rest/v1/rpc/{function_name}"
        try:
            with httpx.Client(timeout=self.settings.timeout_sec) as client:
                response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:2000]
            raise BackendRequestError(
                f"Supabase RPC {function_name} failed: {exc.response.status_code} {body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise BackendRequestError(f"Supabase RPC request failed: {exc}") from exc

        if not response.content:
            return None
        return response.json()

    def select(
        self,
        table: str,
        *,
        filters: dict[str, str] | None = None,
        columns: str = "*",
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"select": columns}
        for key, value in (filters or {}).items():
            params[key] = value
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        data = self._request("GET", table, params=params)
        return list(data or [])

    def insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._request(
            "POST",
            table,
            payload=payload,
            prefer="return=representation",
        )
        if not data:
            raise BackendRequestError(f"Supabase insert into {table} returned no row.")
        return dict(data[0])

    def insert_many(self, table: str, payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not payload:
            return []
        data = self._request(
            "POST",
            table,
            payload=payload,
            prefer="return=representation",
        )
        return list(data or [])

    def update(
        self,
        table: str,
        row_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = self._request(
            "PATCH",
            table,
            params={"id": f"eq.{row_id}"},
            payload=payload,
            prefer="return=representation",
        )
        if not data:
            raise BackendRequestError(f"Supabase update of {table}/{row_id} returned no row.")
        return dict(data[0])

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.insert("projects", payload)

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        rows = self.select("projects", filters={"id": f"eq.{project_id}"}, limit=1)
        return rows[0] if rows else None

    def list_presets(self) -> list[dict[str, Any]]:
        return self.select("presets", order="is_default.desc,created_at.desc")

    def add_source(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.insert("source_files", {"project_id": project_id, **payload})

    def add_events(
        self,
        project_id: str,
        source_file_id: str,
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows = [
            {
                "project_id": project_id,
                "source_file_id": source_file_id,
                **event,
            }
            for event in events
        ]
        return self.insert_many("events", rows)

    def create_render(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.insert("renders", {"project_id": project_id, **payload})

    def update_render(self, render_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.update("renders", render_id, payload)

    def add_edit(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.insert("edits", {"project_id": project_id, **payload})

    def add_feedback(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.insert("feedback", {"project_id": project_id, **payload})

    def list_project_events(
        self,
        project_id: str,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self.select(
            "events",
            filters={"project_id": f"eq.{project_id}"},
            order="start_ms.asc",
            limit=limit,
        )

    def get_events_by_ids(self, event_ids: list[str]) -> dict[str, dict[str, Any]]:
        ids = sorted({value for value in event_ids if value})
        if not ids:
            return {}
        rows = self.select(
            "events",
            filters={"id": f"in.({','.join(ids)})"},
            limit=len(ids),
        )
        return {str(row["id"]): row for row in rows}

    def list_project_renders(
        self,
        project_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.select(
            "renders",
            filters={"project_id": f"eq.{project_id}"},
            order="created_at.desc",
            limit=limit,
        )

    def list_project_edits(
        self,
        project_id: str,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self.select(
            "edits",
            filters={"project_id": f"eq.{project_id}"},
            order="created_at.asc",
            limit=limit,
        )

    def list_project_feedback(
        self,
        project_id: str,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self.select(
            "feedback",
            filters={"project_id": f"eq.{project_id}"},
            order="created_at.asc",
            limit=limit,
        )

    def get_preset_by_name(self, name: str) -> dict[str, Any] | None:
        rows = self.select(
            "presets",
            filters={"name": f"eq.{name}"},
            order="version.desc",
            limit=1,
        )
        return rows[0] if rows else None

    def create_learning_snapshot(
        self,
        project_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.insert("learning_snapshots", {"project_id": project_id, **payload})

    def list_learning_snapshots(
        self,
        project_id: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self.select(
            "learning_snapshots",
            filters={"project_id": f"eq.{project_id}"},
            order="created_at.desc",
            limit=limit,
        )

    def create_job(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.insert("jobs", {"project_id": project_id, **payload})

    def list_project_jobs(
        self,
        project_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.select(
            "jobs",
            filters={"project_id": f"eq.{project_id}"},
            order="created_at.desc",
            limit=limit,
        )

    def claim_job(self, worker_id: str) -> dict[str, Any] | None:
        data = self.rpc("claim_autoeditor_job", {"p_worker_id": worker_id})
        if not data:
            return None
        if isinstance(data, list):
            return dict(data[0]) if data else None
        if isinstance(data, dict) and not data.get("id"):
            return None
        return dict(data)

    def update_job(
        self,
        job_id: str,
        payload: dict[str, Any],
        *,
        worker_id: str | None = None,
        expected_status: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"id": f"eq.{job_id}"}
        if worker_id:
            params["worker_id"] = f"eq.{worker_id}"
        if expected_status:
            params["status"] = f"eq.{expected_status}"
        data = self._request(
            "PATCH",
            "jobs",
            params=params,
            payload=payload,
            prefer="return=representation",
        )
        if not data:
            raise BackendRequestError(
                f"Job {job_id} was not updated; worker/status may not match."
            )
        return dict(data[0])
