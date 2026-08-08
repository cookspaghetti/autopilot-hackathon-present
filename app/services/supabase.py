"""Minimal backend Supabase REST adapter for the operational plane."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx


class SupabaseConfigurationError(RuntimeError):
    pass


class SupabaseAPIError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SupabaseSettings:
    url: str
    api_key: str
    timeout_seconds: float

    @classmethod
    def from_environment(cls) -> SupabaseSettings:
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        secret_key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        compatibility_key = os.getenv("SUPABASE_API_KEY", "").strip()
        publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()

        # During migration, reject a publishable key accidentally placed in the
        # legacy service-role slot when an elevated compatibility key is present.
        if service_role_key.startswith("sb_publishable_"):
            service_role_key = ""

        api_key = secret_key or service_role_key or compatibility_key or publishable_key
        if not url or not api_key:
            missing = []
            if not url:
                missing.append("SUPABASE_URL")
            if not api_key:
                missing.append("SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY")
            raise SupabaseConfigurationError(
                f"Missing backend configuration: {', '.join(missing)}"
            )
        return cls(
            url=url,
            api_key=api_key,
            timeout_seconds=float(
                os.getenv("SUPABASE_TIMEOUT_SECONDS", "").strip() or "30"
            ),
        )


class SupabaseClient:
    def __init__(
        self,
        settings: SupabaseSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._transport = transport

    @classmethod
    def from_environment(cls) -> SupabaseClient:
        return cls(SupabaseSettings.from_environment())

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "apikey": self.settings.api_key,
            "Accept": "application/json",
        }
        # New sb_publishable_/sb_secret_ keys are opaque API keys, not JWTs.
        # Legacy anon/service_role keys still authenticate as bearer JWTs.
        if not self.settings.api_key.startswith(("sb_publishable_", "sb_secret_")):
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        return headers

    async def fetch_rows(
        self,
        table: str,
        *,
        select: str = "*",
        filters: Mapping[str, str] | None = None,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {"select": select, "limit": limit}
        if filters:
            params.update(filters)
        payload = await self._request("GET", f"/rest/v1/{table}", params=params)
        if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
            raise SupabaseAPIError(f"Expected a row list from {table}")
        return [dict(row) for row in payload if isinstance(row, Mapping)]

    async def insert_rows(
        self,
        table: str,
        rows: Sequence[Mapping[str, Any]],
        *,
        upsert: bool = False,
        on_conflict: str | None = None,
    ) -> list[dict[str, Any]]:
        headers = {"Prefer": "return=representation"}
        if upsert:
            headers["Prefer"] += ",resolution=merge-duplicates"
        params = {"on_conflict": on_conflict} if on_conflict else None
        payload = await self._request(
            "POST",
            f"/rest/v1/{table}",
            params=params,
            json=[dict(row) for row in rows],
            headers=headers,
        )
        if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
            raise SupabaseAPIError(f"Expected inserted rows from {table}")
        return [dict(row) for row in payload if isinstance(row, Mapping)]

    async def call_rpc(
        self,
        function_name: str,
        arguments: Mapping[str, Any],
    ) -> Any:
        return await self._request(
            "POST",
            f"/rest/v1/rpc/{function_name}",
            json=dict(arguments),
            headers={"Prefer": "return=representation"},
        )

    async def count(self, table: str) -> int:
        url = f"{self.settings.url}/rest/v1/{table}"
        headers = {**self.headers, "Prefer": "count=exact", "Range": "0-0"}
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    url,
                    headers=headers,
                    params={"select": "*"},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SupabaseAPIError(
                f"Supabase returned {exc.response.status_code}: {exc.response.text[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SupabaseAPIError(f"Supabase request failed: {exc}") from exc
        content_range = response.headers.get("content-range", "")
        try:
            return int(content_range.rsplit("/", 1)[1])
        except (IndexError, ValueError) as exc:
            raise SupabaseAPIError(
                "Supabase count response had no exact Content-Range"
            ) from exc

    async def count_tables(self, tables: Sequence[str]) -> dict[str, int]:
        """Return exact counts for a group of tables using parallel HEAD-sized reads."""
        table_names = tuple(tables)
        counts = await asyncio.gather(*(self.count(table) for table in table_names))
        return dict(zip(table_names, counts))

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    f"{self.settings.url}{path}",
                    headers={**self.headers, **dict(headers or {})},
                    params=params,
                    json=json,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SupabaseAPIError(
                f"Supabase returned {exc.response.status_code}: {exc.response.text[:500]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SupabaseAPIError(f"Supabase request failed: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise SupabaseAPIError("Supabase returned non-JSON data") from exc
