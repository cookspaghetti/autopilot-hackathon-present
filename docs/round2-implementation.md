# Round 2 implementation guide

This directory contains the live Procurement Exception Commander implementation.
The application is split deliberately into two data planes:

- Supabase is the operational system of record for the organizer dataset and
  executed procurement actions.
- The template database is the control plane for workflow runs, immutable
  Operator results, policies and evaluations, Workbench decisions, Insights,
  integration health, resource reservations, and audit history.

## Implemented vertical slice

The current branch includes:

- typed, validated domain dataclasses for workflows, Operator results, policy
  evaluations, Workbench items, evidence, Insights, integrations, and
  reservations;
- versioned no-code policies with deterministic evaluation and five seeded
  procurement policies;
- persisted workflow lifecycle and exact Operator result envelopes for all seven
  Round 2 Operators;
- source-identity deduplication with an auditable duplicate/no-op count;
- v2 Operator result metadata with attempts, subject/version identity, raw observed
  values, `NO_MATCH`, and proposed actions;
- input-hashed policy evaluations and a write-ahead action ledger that rejects
  missing, stale, review, or blocked policy snapshots;
- a real Workbench approve/modify/reject/escalate transition with optimistic
  versioning, first-decision-wins semantics, and an explicit decision source;
- a durable Slack-via-Supervity delivery ledger with message correlation,
  idempotent callbacks, and operational health;
- transactional capacity reservations that prevent concurrent over-allocation;
- a backend-only Supervity Workflow API adapter with start, status, resume, and
  HMAC-protected callback contracts;
- a Supabase REST adapter and deterministic, evidence-backed procurement
  Insights;
- live Dashboard, Policies, Insights, Workbench, Data Manager, and grounded AI
  Manager surfaces; and
- a portable Alembic chain plus a 14-table Supabase schema and seed generator for
  the supplied Round 2 data.

## Environment

Copy `.env.example` to `.env` and set secrets locally. Never prefix the Workflow
API key or Supabase service key with `NEXT_PUBLIC_`.

The Supervity connection needs:

```text
SUPERVITY_WORKFLOW_TRIGGER_URL=<full trigger endpoint>
SUPERVITY_WORKFLOW_API_KEY=<workflow API key>
SUPERVITY_ORCHESTRATOR_ID=<published Orchestrator ID>
SUPERVITY_WORKFLOW_SOURCE=external
SUPERVITY_USER_TIMEZONE=Asia/Kuala_Lumpur
SUPERVITY_API_BASE_URL=<optional management API /api/v1 root>
SUPERVITY_INTEGRATION_API_BASE_URL=<optional integration API /api/v1 root>
SUPERVITY_ACTIVE_ORG=<active organization ID when required by the token>
SUPERVITY_WORKFLOW_STATUS_URL_TEMPLATE=<optional URL containing {run_id}>
SUPERVITY_WORKFLOW_RESUME_URL_TEMPLATE=<optional URL containing {run_id}>
COMMAND_CENTER_API_URL=<public backend URL reachable by Auto>
COMMAND_CENTER_CALLBACK_SECRET=<long random value>
SUPERVITY_INCLUDE_CALLBACK_INPUTS=false
```

The operational data connection needs:

```text
SUPABASE_URL=<project URL>
SUPABASE_SECRET_KEY=<sb_secret_ server-side key>
```

The backend sends new opaque Supabase keys through the `apikey` header only.
`SUPABASE_SERVICE_ROLE_KEY` remains supported for legacy JWT-based projects.
`SUPABASE_PUBLISHABLE_KEY` and `SUPABASE_JWKS_URL` are only required when a
client accesses Supabase under RLS or the backend verifies Supabase Auth users.

The configured trigger endpoint is used verbatim; the adapter does not guess a
Supervity URL shape. The published Exception Commander Orchestrator currently
uses `POST /api/v1/workflow-runs/execute/stream` with `multipart/form-data` and
these exact fields:

```text
workflowId
inputs[source]
inputs[source_ref]
inputs[received_at_raw]
inputs[sender_email]
inputs[body]
```

The backend supplies the required `x-source` and `x-user-timezone` headers,
returns the local `/start` request immediately, consumes the execution stream in
the background, and persists the Auto run ID plus the most recent 50 stream
events when the stream closes. The API key remains backend-only.

Status, Operator-result, notification-receipt, and external-decision endpoints
accept per-run HMAC tokens. The backend can pass all callback URLs, the Command
Center run ID, incident ID, and token when
`SUPERVITY_INCLUDE_CALLBACK_INPUTS=true`. Keep it false until the six inputs
listed in [Slack via Supervity](slack-via-supervity.md) are declared in the
published workflow. Until status/resume endpoint templates are supplied, the
execution stream is the authoritative completion signal and Workbench cannot
resume a paused Auto run through the API.

## Local verification

From `AutoPilot-Template/`:

```powershell
docker compose up --build
```

Or run the backend and frontend separately after installing their dependencies.
The core verification commands are:

```powershell
pytest -q
alembic upgrade head
cd frontend
npm run build
```

Seed Supabase by following the commands in the repository-level
`seeding/schema.md`. Seed the Command Center policy and integration records with
`python scripts/seed_db.py` after migrations.

## Live integration acceptance test

1. Test Supabase from Data Manager and confirm record counts for the organizer
   tables.
2. Test Supervity from Data Manager and start one run from the Dashboard/API.
3. Confirm the returned Auto run ID is persisted on the Command Center run.
4. Confirm each Operator posts an evidence-bearing result with the exact current
   `plan_run_id`.
5. Trigger a review policy, decide the Workbench item, and verify the same Auto
   run resumes.
6. Confirm Executor writes one idempotent operational action, Slack receives
   one notification, and the matching signed delivery receipt appears in the
   Command Center notification ledger.

The multipart Auto trigger has been verified against the live Orchestrator. A
complete live qualification run still requires Supabase deployment and the
documented callback, resume, and Slack actions to be configured in Auto. The
local callback contracts and automated lifecycle coverage are complete; the
application does not fabricate a healthy state before Supervity reports a real
