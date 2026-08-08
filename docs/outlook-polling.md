# Outlook polling integration

The backend exposes a scheduler-ready endpoint that turns newly received Outlook messages into Command Center workflow runs:

```http
POST /api/command-center/outlook/poll
X-Outlook-Poll-Secret: <OUTLOOK_POLL_SECRET>
```

The request has no body. A platform scheduler should call it every 30–60 seconds. The endpoint is listed in `app/public.map.json` so an external scheduler can reach it, but it performs its own shared-secret check.

## Environment

Register a Microsoft Entra application that supports the target account type. For a personal Outlook.com mailbox, use the consumers authority. Add the callback below as a **Web** redirect URI, not an SPA redirect URI, and grant delegated Microsoft Graph Mail.Read and User.Read permissions.

Create a client secret, then generate OUTLOOK_TOKEN_CACHE_KEY once:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Keep that key stable and secret. It encrypts the serialized MSAL cache stored in command_integration_credentials; rotating it deliberately forces an Outlook reconnect.

```dotenv
OUTLOOK_CLIENT_ID=
OUTLOOK_CLIENT_SECRET=
OUTLOOK_TENANT=consumers
OUTLOOK_REDIRECT_URI=http://localhost:8001/api/command-center/outlook/oauth/callback
OUTLOOK_OAUTH_SCOPES=Mail.Read User.Read
OUTLOOK_TOKEN_CACHE_KEY=
# Temporary static-token fallback only:
OUTLOOK_ACCESS_TOKEN=
OUTLOOK_GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
OUTLOOK_POLL_SECRET=
OUTLOOK_POLL_MAX_PAGES=25
```

- Set `OUTLOOK_POLL_SECRET` to a long, random value in every deployed environment. When it is configured, the matching `X-Outlook-Poll-Secret` header is mandatory.
- Without a poll secret, the endpoint requires an authenticated application user. Local `AUTH_BYPASS=true` also supplies that user for development.
- The access token needs delegated `Mail.Read` for automated processing because the workflow input includes the message body. `Mail.ReadBasic` is enough only for connection checks and limited message metadata; `User.Read` is not enough for mail access.
- `OUTLOOK_POLL_MAX_PAGES` bounds the amount of Graph delta pagination handled by one request and must be between 1 and 100.

## First call and subsequent calls

The first successful call establishes a Microsoft Graph delta cursor and intentionally does not process existing Inbox messages. This prevents rollout from creating runs for the historical mailbox.

Later calls request only changes after that cursor. Each new message:

1. is fetched from Graph with its subject, sender, body, timestamps, and stable IDs;
2. creates one `WorkflowRunRecord` with `source=outlook`;
3. is dispatched to the existing Supervity workflow stream in a background task.

The Graph `internetMessageId` is used as the idempotency key, with the Graph message ID as fallback. Repeated delta entries are skipped, and the private Graph delta cursor is never returned by the integration-health APIs.

If Graph invalidates a cursor, the endpoint establishes a fresh baseline and again skips historical messages rather than replaying the mailbox.

## Response

```json
{
  "baseline_established": false,
  "cursor_reset": false,
  "messages_seen": 1,
  "baseline_messages": 0,
  "runs_created": 1,
  "runs_started": 1,
  "duplicates_skipped": 0,
  "removed_skipped": 0,
  "pages_seen": 1,
  "run_ids": ["RUN-..."],
  "polled_at": "2026-08-08T07:00:00Z"
}
```

An invalid scheduler secret returns `401`. Missing Outlook configuration, expired permissions, Graph errors, or a bounded-pagination failure return `503` and are retained in polling diagnostics. The Outlook card in Data Manager derives its connection status from Supervity's integration inventory, not from this Graph polling path.

## Scheduler example

```bash
curl --fail-with-body \
  --request POST \
  --header "X-Outlook-Poll-Secret: $OUTLOOK_POLL_SECRET" \
  https://your-api.example/api/command-center/outlook/poll
```

Graph Explorer access tokens are suitable for local validation but expire. The production polling path uses a delegated OAuth authorization-code flow, an encrypted persistent MSAL cache, and silent refresh. These credentials govern Command Center inbox polling only; the Data Manager Outlook card reports whether Outlook is connected in Supervity and does not query Microsoft Graph.
