"""Backend-only Microsoft Graph adapter for Outlook health and polling."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence, TYPE_CHECKING
from urllib.parse import quote, urlsplit

import httpx

from .outlook_auth import (
    OutlookAuthorizationRequired,
    OutlookOAuthConfigurationError,
    OutlookTokenManager,
    outlook_oauth_configuration,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class OutlookConfigurationError(RuntimeError):
    pass


class OutlookAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class OutlookDelta:
    messages: tuple[Mapping[str, Any], ...]
    delta_link: str
    pages_seen: int


@dataclass(frozen=True, slots=True)
class OutlookSettings:
    graph_base_url: str
    access_token: str | None
    timeout_seconds: float

    @classmethod
    def from_environment(
        cls,
        *,
        require_access_token: bool = True,
    ) -> OutlookSettings:
        access_token = os.getenv("OUTLOOK_ACCESS_TOKEN", "").strip()
        if require_access_token and not access_token:
            raise OutlookConfigurationError(
                "Missing backend configuration: OUTLOOK_ACCESS_TOKEN"
            )
        return cls(
            graph_base_url=(
                os.getenv("OUTLOOK_GRAPH_BASE_URL", "").strip()
                or "https://graph.microsoft.com/v1.0"
            ).rstrip("/"),
            access_token=access_token,
            timeout_seconds=float(
                os.getenv("OUTLOOK_TIMEOUT_SECONDS", "").strip() or "10"
            ),
        )


class OutlookClient:
    def __init__(
        self,
        settings: OutlookSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        access_token_provider: Callable[[], str] | None = None,
        auth_metadata_provider: Callable[[], Mapping[str, Any]] | None = None,
    ) -> None:
        self.settings = settings
        self._transport = transport
        self._access_token_provider = access_token_provider
        self._auth_metadata_provider = auth_metadata_provider

    @classmethod
    def from_environment(cls, *, db: Session | None = None) -> OutlookClient:
        oauth = outlook_oauth_configuration()
        if oauth["oauth_configured"]:
            if db is None:
                raise OutlookConfigurationError(
                    "A database session is required for Outlook OAuth"
                )
            try:
                manager = OutlookTokenManager.from_environment(db)
            except OutlookOAuthConfigurationError as exc:
                raise OutlookConfigurationError(str(exc)) from exc
            return cls(
                OutlookSettings.from_environment(require_access_token=False),
                access_token_provider=manager.access_token,
                auth_metadata_provider=manager.account_metadata,
            )
        return cls(OutlookSettings.from_environment())

    def auth_metadata(self) -> dict[str, Any]:
        metadata = outlook_oauth_configuration()
        if self._auth_metadata_provider is not None:
            metadata.update(dict(self._auth_metadata_provider()))
        return metadata

    def _headers(self) -> dict[str, str]:
        token = self.settings.access_token
        if self._access_token_provider is not None:
            try:
                token = self._access_token_provider()
            except (
                OutlookAuthorizationRequired,
                OutlookOAuthConfigurationError,
            ) as exc:
                raise OutlookConfigurationError(str(exc)) from exc
        if not token:
            raise OutlookConfigurationError(
                "Outlook authorization required; connect Outlook in Data Manager"
            )
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def inbox_status(self) -> Mapping[str, Any]:
        """Verify mailbox access and return lightweight Inbox counters."""
        return await self._get_json(
            "/me/mailFolders/inbox",
            params={"$select": "displayName,totalItemCount,unreadItemCount"},
        )

    async def collect_inbox_delta(
        self,
        *,
        delta_link: str | None = None,
        max_pages: int = 25,
    ) -> OutlookDelta:
        """Collect one complete Inbox delta cycle and its new opaque cursor."""
        if max_pages < 1:
            raise OutlookConfigurationError("OUTLOOK_POLL_MAX_PAGES must be positive")
        url = delta_link or "/me/mailFolders/inbox/messages/delta"
        params = (
            None
            if delta_link
            else {"$select": "id,internetMessageId,subject,from,receivedDateTime"}
        )
        messages: list[Mapping[str, Any]] = []
        for page_number in range(1, max_pages + 1):
            payload = await self._get_json(url, params=params)
            values = payload.get("value")
            if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                raise OutlookAPIError(
                    "Microsoft Graph delta response had no value list"
                )
            messages.extend(item for item in values if isinstance(item, Mapping))
            next_link = payload.get("@odata.nextLink")
            delta = payload.get("@odata.deltaLink")
            if isinstance(delta, str) and delta.strip():
                return OutlookDelta(
                    messages=tuple(messages),
                    delta_link=delta.strip(),
                    pages_seen=page_number,
                )
            if not isinstance(next_link, str) or not next_link.strip():
                raise OutlookAPIError(
                    "Microsoft Graph delta response had no nextLink or deltaLink"
                )
            url = next_link.strip()
            params = None
        raise OutlookAPIError(
            f"Microsoft Graph delta exceeded {max_pages} pages; increase "
            "OUTLOOK_POLL_MAX_PAGES"
        )

    async def message_details(self, message_id: str) -> Mapping[str, Any]:
        """Fetch the fields needed to create a Command Center intake run."""
        safe_id = quote(message_id, safe="")
        return await self._get_json(
            f"/me/messages/{safe_id}",
            params={
                "$select": (
                    "id,internetMessageId,subject,from,receivedDateTime,"
                    "body,hasAttachments,webLink"
                )
            },
        )

    async def _get_json(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        url = self._graph_url(path_or_url)
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    url,
                    headers=self._headers(),
                    params=params,
                )
                response.raise_for_status()
        except OutlookConfigurationError:
            raise
        except httpx.HTTPStatusError as exc:
            raise OutlookAPIError(
                f"Microsoft Graph returned {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise OutlookAPIError(f"Microsoft Graph request failed: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise OutlookAPIError("Microsoft Graph returned non-JSON data") from exc
        if not isinstance(payload, Mapping):
            raise OutlookAPIError("Microsoft Graph returned an invalid JSON object")
        return payload

    def _graph_url(self, path_or_url: str) -> str:
        """Keep bearer-authenticated cursor requests on the configured Graph host."""
        base = self.settings.graph_base_url
        if path_or_url.startswith("/"):
            return f"{base}{path_or_url}"
        candidate = urlsplit(path_or_url)
        expected = urlsplit(base)
        if (
            candidate.scheme != expected.scheme
            or candidate.netloc != expected.netloc
            or not candidate.path.startswith(f"{expected.path.rstrip('/')}/")
        ):
            raise OutlookAPIError("Rejected an untrusted Microsoft Graph cursor URL")
        return path_or_url
