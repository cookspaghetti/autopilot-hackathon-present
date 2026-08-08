"""Private Slack Socket Mode ingress for local and firewall-safe deployments."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Event
from typing import Any

from .slack_insights import (
    SlackInsightEvent,
    SlackInsightPayloadError,
    parse_slack_insight_event,
    process_slack_insight_event,
)

log = logging.getLogger(__name__)


class SlackSocketModeConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SlackSocketModeSettings:
    app_token: str

    @classmethod
    def from_environment(cls) -> SlackSocketModeSettings:
        app_token = os.getenv("SLACK_APP_TOKEN", "").strip()
        if not app_token:
            raise SlackSocketModeConfigurationError(
                "Missing backend configuration: SLACK_APP_TOKEN"
            )
        if not app_token.startswith("xapp-"):
            raise SlackSocketModeConfigurationError(
                "SLACK_APP_TOKEN must be an app-level xapp token"
            )
        return cls(app_token=app_token)


def handle_socket_mode_request(
    client: Any,
    request: Any,
    *,
    dispatch_event: Callable[[SlackInsightEvent], str] | None = None,
) -> str:
    """Acknowledge one Socket Mode envelope, then dispatch a valid app mention."""
    from slack_sdk.socket_mode.response import SocketModeResponse

    envelope_id = str(getattr(request, "envelope_id", "") or "").strip()
    if envelope_id:
        client.send_socket_mode_response(SocketModeResponse(envelope_id=envelope_id))

    if getattr(request, "type", None) != "events_api":
        return "ignored"
    payload = getattr(request, "payload", None)
    if not isinstance(payload, Mapping):
        return "ignored"

    try:
        event = parse_slack_insight_event(payload)
    except SlackInsightPayloadError as exc:
        log.warning("Rejected malformed Slack Socket Mode event: %s", exc)
        return "invalid"
    if event is None:
        return "ignored"

    try:
        if dispatch_event is not None:
            return dispatch_event(event)
        return asyncio.run(process_slack_insight_event(event))
    except Exception:
        log.exception("Slack Socket Mode insight dispatch failed")
        return "failed"


def run_socket_mode_forever() -> None:
    """Connect to Slack and keep the authenticated Socket Mode worker alive."""
    from slack_sdk.socket_mode import SocketModeClient

    settings = SlackSocketModeSettings.from_environment()
    client = SocketModeClient(app_token=settings.app_token)
    client.socket_mode_request_listeners.append(handle_socket_mode_request)
    client.connect()
    log.info("Slack insight Socket Mode worker connected")
    try:
        Event().wait()
    except KeyboardInterrupt:
        log.info("Slack insight Socket Mode worker stopping")
    finally:
        client.disconnect()


if __name__ == "__main__":
    run_socket_mode_forever()
