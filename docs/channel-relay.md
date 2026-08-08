# Omnichannel relay

The command center treats Slack and Supervity Chat as interaction surfaces, not
as the system of record. Incidents, decisions, actions, and notification
receipts remain in the command-center database.

## Route model

Operators emit a stable `route_key`. The Omnichannel Relay Operator resolves the
Slack destination from Supabase table `channel_routes`; the model never chooses
or hardcodes a channel ID.

| Route key | Slack channel | Purpose |
| --- | --- | --- |
| `disruption_alerts` | `#disruptions` | Immediate, unverified source alert |
| `incident_reports` | `#incident-report` | Agent-triaged report and incident thread |
| `human_approval` | `#approvals` | Explicit approve/reject decision |
| `inventory_updates` | `#inventory-updates` | Verified stock changes and stock-position notifications |
| `management_insights` | `#insight` | Management summaries and requested insight |
| `originating_chat` | current Supervity conversation | Reply to the user who initiated the request |

Use one Slack thread per incident. Post state changes to the existing thread
instead of creating a new top-level message for every operator step.

## Operator contract

Required inputs:

- `provider`: `slack` or `supervity_chat`
- `route_key`: one of the business routes above
- `message_text`

For Slack, `destination_id` may be supplied by a trusted caller. If omitted,
the operator looks up exactly one enabled row using `workspace_key`,
`route_key`, and `provider`. A missing or ambiguous route fails closed.

An optional `action_url` also lives in `channel_routes`. When the
`human_approval` route has an absolute HTTP(S) URL, the Slack message includes
a **Review & Decide** button. The operator contains no application hostname.
For local demos the seeded URL is `http://localhost:3001/workbench`; after
deployment, update only the Supabase route:

```sql
update channel_routes
set action_url = 'https://your-command-center.example/workbench',
    updated_at = now()
where workspace_key = 'default'
  and route_key = 'human_approval'
  and provider = 'slack';
```

Configure these values as Supervity secrets after importing the operator:

- `SLACK_BOT_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_KEY` with read access to `channel_routes`

The seed enables Row Level Security. Anonymous and authenticated keys may only
select routes where `enabled = true`; disabled routes stay hidden.

The Slack token must be a bot token so posts appear from the app, not from the
connected user's identity.

## Outlook ownership

When Supervity owns the native Outlook trigger and mailbox connection, a local
Microsoft Graph access token is not part of production delivery. Its expiry can
only break the local Graph health check or local poller. Operational health
should instead use the last signed event received, last successful workflow
run, and last relay receipt.

## Local validation

From the repository root:

```powershell
python scripts\rebuild-omnichannel-relay-operator-json.py
python scripts\validate-omnichannel-relay-operator-json.py
python scripts\validate-supervity-operator-json.py
```

Apply `seeding/channel_routes.sql` to an existing Supabase project (or use
`seeding/schema.sql` for a fresh setup) before running a Slack route,
then import `operators/exported/omnichannel-relay-operator-export.json` into
Supervity. All five Slack routes are seeded with enabled destinations.
