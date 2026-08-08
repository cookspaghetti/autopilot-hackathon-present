"""Public, Slack-signed ingress for management insight mentions."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from ..services.slack_insights import (
    SlackInsightConfigurationError,
    SlackInsightPayloadError,
    SlackInsightSettings,
    parse_slack_insight_event,
    process_slack_insight_event,
    verify_slack_signature,
)

router = APIRouter(prefix="/command-center/slack", tags=["Slack Insights"])


@router.post("/events")
async def receive_slack_event(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    """Acknowledge a verified Slack event and dispatch insight work asynchronously."""
    try:
        settings = SlackInsightSettings.from_environment()
    except SlackInsightConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    raw_body = await request.body()
    if not verify_slack_signature(
        raw_body=raw_body,
        timestamp=request.headers.get("x-slack-request-timestamp"),
        signature=request.headers.get("x-slack-signature"),
        signing_secret=settings.signing_secret,
        max_age_seconds=settings.signature_max_age_seconds,
    ):
        raise HTTPException(status_code=401, detail="Invalid Slack request signature")
    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Slack payload must be JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Slack payload must be an object")

    if payload.get("type") == "url_verification":
        challenge = str(payload.get("challenge") or "").strip()
        if not challenge:
            raise HTTPException(status_code=400, detail="Slack challenge is required")
        return {"challenge": challenge}

    try:
        event = parse_slack_insight_event(payload)
    except SlackInsightPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if event is None:
        return {"ok": True, "ignored": True}

    background_tasks.add_task(
        process_slack_insight_event,
        event,
        settings=settings,
    )
    return {"ok": True, "event_id": event.event_id}
