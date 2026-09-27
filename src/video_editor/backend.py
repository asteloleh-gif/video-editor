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

    def add_feedback(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.insert("feedback", {"project_id": project_id, **payload})
