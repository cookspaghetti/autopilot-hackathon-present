from types import SimpleNamespace

import pytest

from app.services.slack_socket_mode import (
    SlackSocketModeConfigurationError,
    SlackSocketModeSettings,
    handle_socket_mode_request,
)


class FakeSocketClient:
    def __init__(self) -> None:
        self.responses = []

    def send_socket_mode_response(self, response) -> None:
        self.responses.append(response)


def test_socket_mode_settings_require_an_app_level_token(monkeypatch) -> None:
    monkeypatch.delenv("SLACK_APP_TOKEN", raising=False)
    with pytest.raises(SlackSocketModeConfigurationError):
        SlackSocketModeSettings.from_environment()
    monkeypatch.setenv("SLACK_APP_TOKEN", "xoxb-wrong-token-type")
    with pytest.raises(SlackSocketModeConfigurationError):
        SlackSocketModeSettings.from_environment()


def test_socket_mode_acknowledges_before_dispatching_mention() -> None:
    client = FakeSocketClient()
    seen = []
    request = SimpleNamespace(
        type="events_api",
        envelope_id="ENV-1",
        payload={
            "type": "event_callback",
            "event_id": "Ev-socket-1",
            "event": {
                "type": "app_mention",
                "channel": "C-INSIGHT",
                "ts": "1720000000.001",
                "user": "U-MANAGER",
                "text": "<@U-BOT> daily briefing",
            },
        },
    )

    def dispatch(event) -> str:
        assert len(client.responses) == 1
        seen.append(event)
        return "triggered"

    result = handle_socket_mode_request(client, request, dispatch_event=dispatch)

    assert result == "triggered"
    assert client.responses[0].envelope_id == "ENV-1"
    assert seen[0].event_id == "Ev-socket-1"
    assert seen[0].thread_ts == "1720000000.001"


def test_socket_mode_acknowledges_and_ignores_unrelated_events() -> None:
    client = FakeSocketClient()
    request = SimpleNamespace(
        type="events_api",
        envelope_id="ENV-2",
        payload={
            "type": "event_callback",
            "event": {"type": "reaction_added"},
        },
    )

    result = handle_socket_mode_request(client, request)

    assert result == "ignored"
    assert client.responses[0].envelope_id == "ENV-2"


def test_socket_mode_dispatches_human_thread_replies() -> None:
    client = FakeSocketClient()
    seen = []
    request = SimpleNamespace(
        type="events_api",
        envelope_id="ENV-3",
        payload={
            "type": "event_callback",
            "event_id": "Ev-socket-thread-1",
            "event": {
                "type": "message",
                "channel_type": "channel",
                "channel": "C-INSIGHT",
                "ts": "1720000000.002",
                "thread_ts": "1720000000.001",
                "user": "U-MANAGER",
                "text": "why is that the highest risk?",
            },
        },
    )

    result = handle_socket_mode_request(
        client,
        request,
        dispatch_event=lambda event: seen.append(event) or "triggered",
    )

    assert result == "triggered"
    assert len(client.responses) == 1
    assert seen[0].event_type == "thread_reply"
