"""Persistent delegated OAuth for the Outlook Microsoft Graph integration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit

import msal
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from ..models.command_center import IntegrationCredentialRecord


class OutlookOAuthConfigurationError(RuntimeError):
    pass


class OutlookAuthorizationRequired(RuntimeError):
    pass


class OutlookAuthorizationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OutlookOAuthSettings:
    client_id: str
    client_secret: str
    tenant: str
    redirect_uri: str
    scopes: tuple[str, ...]
    token_cache_key: str

    @classmethod
    def from_environment(cls) -> OutlookOAuthSettings:
        values = {
            "OUTLOOK_CLIENT_ID": os.getenv("OUTLOOK_CLIENT_ID", "").strip(),
            "OUTLOOK_CLIENT_SECRET": os.getenv("OUTLOOK_CLIENT_SECRET", "").strip(),
            "OUTLOOK_REDIRECT_URI": os.getenv("OUTLOOK_REDIRECT_URI", "").strip(),
            "OUTLOOK_TOKEN_CACHE_KEY": os.getenv("OUTLOOK_TOKEN_CACHE_KEY", "").strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise OutlookOAuthConfigurationError(
                "Missing Outlook OAuth configuration: " + ", ".join(missing)
            )

        redirect = urlsplit(values["OUTLOOK_REDIRECT_URI"])
        if redirect.scheme not in {"http", "https"} or not redirect.netloc:
            raise OutlookOAuthConfigurationError(
                "OUTLOOK_REDIRECT_URI must be an absolute HTTP(S) URL"
            )

        try:
            Fernet(values["OUTLOOK_TOKEN_CACHE_KEY"].encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise OutlookOAuthConfigurationError(
                "OUTLOOK_TOKEN_CACHE_KEY must be a valid Fernet key"
            ) from exc

        raw_scopes = (
            os.getenv("OUTLOOK_OAUTH_SCOPES", "").strip() or "Mail.Read User.Read"
        )
        reserved = {"openid", "profile", "offline_access"}
        scopes = tuple(
            scope for scope in raw_scopes.split() if scope.lower() not in reserved
        )
        if not scopes:
            raise OutlookOAuthConfigurationError(
                "OUTLOOK_OAUTH_SCOPES must include at least one Graph scope"
            )

        return cls(
            client_id=values["OUTLOOK_CLIENT_ID"],
            client_secret=values["OUTLOOK_CLIENT_SECRET"],
            tenant=os.getenv("OUTLOOK_TENANT", "").strip() or "consumers",
            redirect_uri=values["OUTLOOK_REDIRECT_URI"],
            scopes=scopes,
            token_cache_key=values["OUTLOOK_TOKEN_CACHE_KEY"],
        )

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant}"


def outlook_oauth_configuration() -> dict[str, Any]:
    """Return non-secret configuration readiness for the Data Manager."""
    required = (
        "OUTLOOK_CLIENT_ID",
        "OUTLOOK_CLIENT_SECRET",
        "OUTLOOK_REDIRECT_URI",
        "OUTLOOK_TOKEN_CACHE_KEY",
    )
    present = {name: bool(os.getenv(name, "").strip()) for name in required}
    return {
        "oauth_configured": all(present.values()),
        "oauth_missing": [
            name for name, configured in present.items() if not configured
        ],
        "auth_mode": (
            "oauth_refresh"
            if all(present.values())
            else (
                "static_access_token"
                if os.getenv("OUTLOOK_ACCESS_TOKEN", "").strip()
                else "unconfigured"
            )
        ),
    }


class OutlookCredentialVault:
    """Encrypt the serialized MSAL cache before storing it in PostgreSQL."""

    def __init__(self, db: Session, encryption_key: str) -> None:
        self.db = db
        self._fernet = Fernet(encryption_key.encode("ascii"))

    def load(self) -> dict[str, Any]:
        record = (
            self.db.query(IntegrationCredentialRecord)
            .filter(IntegrationCredentialRecord.integration_id == "outlook")
            .with_for_update()
            .first()
        )
        if record is None:
            return {}
        try:
            plaintext = self._fernet.decrypt(record.encrypted_payload.encode("ascii"))
            payload = json.loads(plaintext.decode("utf-8"))
        except (InvalidToken, UnicodeError, ValueError, TypeError) as exc:
            raise OutlookOAuthConfigurationError(
                "Stored Outlook authorization could not be decrypted; reconnect Outlook"
            ) from exc
        if not isinstance(payload, dict):
            raise OutlookOAuthConfigurationError(
                "Stored Outlook authorization is invalid; reconnect Outlook"
            )
        return payload

    def save(self, payload: Mapping[str, Any]) -> None:
        plaintext = json.dumps(
            dict(payload),
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        encrypted = self._fernet.encrypt(plaintext).decode("ascii")
        record = (
            self.db.query(IntegrationCredentialRecord)
            .filter(IntegrationCredentialRecord.integration_id == "outlook")
            .first()
        )
        if record is None:
            record = IntegrationCredentialRecord(
                integration_id="outlook",
                encrypted_payload=encrypted,
            )
            self.db.add(record)
        else:
            record.encrypted_payload = encrypted
        self.db.flush()


class OutlookTokenManager:
    """Acquire Graph access tokens silently from a persistent MSAL cache."""

    def __init__(self, db: Session, settings: OutlookOAuthSettings) -> None:
        self.db = db
        self.settings = settings
        self._vault = OutlookCredentialVault(db, settings.token_cache_key)
        self._payload = self._vault.load()
        self._cache = msal.SerializableTokenCache()
        serialized = self._payload.get("token_cache")
        if isinstance(serialized, str) and serialized:
            self._cache.deserialize(serialized)
        self._app = msal.ConfidentialClientApplication(
            settings.client_id,
            authority=settings.authority,
            client_credential=settings.client_secret,
            token_cache=self._cache,
        )

    @classmethod
    def from_environment(cls, db: Session) -> OutlookTokenManager:
        return cls(db, OutlookOAuthSettings.from_environment())

    def start_authorization(self) -> str:
        flow = self._app.initiate_auth_code_flow(
            scopes=list(self.settings.scopes),
            redirect_uri=self.settings.redirect_uri,
        )
        authorization_url = flow.get("auth_uri")
        if not isinstance(authorization_url, str) or not authorization_url:
            raise OutlookAuthorizationError(
                "Microsoft did not return an Outlook authorization URL"
            )
        self._payload["pending_auth_flow"] = flow
        self._persist()
        return authorization_url

    def complete_authorization(self, query: Mapping[str, str]) -> Mapping[str, Any]:
        flow = self._payload.get("pending_auth_flow")
        if not isinstance(flow, Mapping):
            raise OutlookAuthorizationError(
                "Outlook authorization session is missing or expired; start again"
            )
        expected_state = flow.get("state")
        if not isinstance(expected_state, str) or query.get("state") != expected_state:
            raise OutlookAuthorizationError("Invalid Outlook OAuth state")
        try:
            result = self._app.acquire_token_by_auth_code_flow(
                dict(flow),
                dict(query),
            )
        except ValueError as exc:
            raise OutlookAuthorizationError("Invalid Outlook OAuth response") from exc

        self._payload.pop("pending_auth_flow", None)
        if "access_token" not in result:
            self._persist()
            description = result.get("error_description") or result.get("error")
            raise OutlookAuthorizationError(
                str(description or "Microsoft did not authorize Outlook")
            )
        self._persist()
        return result

    def access_token(self) -> str:
        accounts = self._app.get_accounts()
        if not accounts:
            raise OutlookAuthorizationRequired(
                "Outlook authorization required; connect Outlook in Data Manager"
            )
        result = self._app.acquire_token_silent(
            scopes=list(self.settings.scopes),
            account=accounts[0],
        )
        if not result or "access_token" not in result:
            if self._cache.has_state_changed:
                self._persist()
            detail = (
                result.get("error_description") or result.get("error")
                if isinstance(result, Mapping)
                else None
            )
            raise OutlookAuthorizationRequired(
                str(detail or "Outlook authorization expired; reconnect Outlook")
            )
        if self._cache.has_state_changed:
            self._persist()
        return str(result["access_token"])

    def account_metadata(self) -> dict[str, Any]:
        accounts = self._app.get_accounts()
        account = accounts[0] if accounts else {}
        username = account.get("username") if isinstance(account, Mapping) else None
        return {
            "oauth_connected": bool(accounts),
            "oauth_account": username if isinstance(username, str) else None,
        }

    def _persist(self) -> None:
        self._payload["token_cache"] = self._cache.serialize()
        self._payload["version"] = 1
        self._vault.save(self._payload)
