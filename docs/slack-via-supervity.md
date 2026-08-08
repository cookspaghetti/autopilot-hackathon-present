# Slack via Supervity integration

The Command Center does not own a Slack bot or store a Slack token. Supervity owns the connected Slack account and performs Slack actions. The Command Center remains the governance ledger for workflow state, policy evidence, decisions, delivery receipts, and management reporting.

## Channel responsibilities

| Surface                  | Responsibility                                             |
| ------------------------ | ---------------------------------------------------------- |
| Outlook                  | Automatic intake of new procurement messages               |
| Supervity Auto           | Agent execution, human-review activity, and Slack delivery |
| Slack                    | Proactive notification and familiar decision surface       |
| Command Center Workbench | Technical/operator decision surface and audit view         |
| Supabase                 | Operational procurement data                               |

A decision can be made in Slack, Supervity Human Review, or the Command Center Workbench. The first valid decision wins. Replays with the same interaction ID are harmless; a different later decision receives HTTP `409`.

## Enable callback inputs in Auto

The current published workflow accepts only its original five inputs. Add these six text inputs to the Supervity workflow before enabling the backend switch:

```text
command_center_run_id
incident_id
callback_token
status_callback_url
notification_callback_url
decision_callback_url
```

Then set:

```dotenv
COMMAND_CENTER_API_URL=https://your-public-backend.example
COMMAND_CENTER_CALLBACK_SECRET=<long-random-secret>
SUPERVITY_INCLUDE_CALLBACK_INPUTS=true
```

The backend computes `callback_token` as HMAC-SHA256 of `command_center_run_id`, keyed by `COMMAND_CENTER_CALLBACK_SECRET`. Supervity receives only the per-run token, not the global secret.

Keep `SUPERVITY_INCLUDE_CALLBACK_INPUTS=false` until all six inputs exist in the published workflow. The Workflow API can reject undeclared multipart inputs.

## Recommended Auto workflow

1. Receive the Outlook-triggered workflow inputs and preserve `command_center_run_id`, `incident_id`, and `callback_token`.
2. Let the procurement agents process the message.
3. If policy permits automatic execution, continue without a human decision.
4. If review is required, create the Supervity user form and post one Slack approval message. Include the Command Center run ID and Workbench/form identity in the workflow context.
5. After posting the Slack message, call `notification_callback_url` with the Slack channel ID and message timestamp.
6. Accept a decision from either:
   - the Supervity/Slack interaction, followed by `decision_callback_url`; or
   - the Command Center Workbench, which submits the same Supervity form and includes any recorded Slack message context.
7. Update the existing Slack message to “Approved — execution resumed,” “Rejected,” or “Escalated.” Approval is not the same as completion.
8. When execution actually completes or fails, call `status_callback_url`, update the same Slack message or thread, and report the result through `notification_callback_url`.

The link-only Slack button remains a safe fallback when an interactive Slack action cannot be bound in Supervity. It should open the existing Supervity Human Review or Command Center Workbench item, not a second approval system.

## Signed notification receipt

```http
POST /api/command-center/supervity/notification
X-Command-Center-Secret: <callback_token>
Content-Type: application/json
```

```json
{
  "command_center_run_id": "RUN-...",
  "event_id": "slack-review-RUN-...",
  "notification_type": "review_required",
  "status": "delivered",
  "channel_id": "C0BJ12765EX",
  "message_ts": "1723091000.000100",
  "thread_ts": "1723091000.000100",
  "workbench_item_id": "WB-...",
  "attempt": 1,
  "payload": {
    "presentation": "approval_card_v1"
  }
}
```

Supported notification types are `review_required`, `decision_recorded`, `workflow_completed`, and `workflow_failed`. Supported receipt states are `requested`, `delivered`, `updated`, and `failed`.

Delivery and update receipts continue to persist Slack relay health for audit and diagnostics, but Data Manager no longer renders a separate “Slack via Supervity” card. Its Slack card and connection status come from Supervity's integration inventory. A late failed replay cannot downgrade an event already delivered.

## Signed external decision

```http
POST /api/command-center/supervity/decision
X-Command-Center-Secret: <callback_token>
Content-Type: application/json
```

```json
{
  "command_center_run_id": "RUN-...",
  "workbench_item_id": "WB-...",
  "supervity_form_id": "FORM-...",
  "decision": "approve",
  "reason": "Evidence supports the recovery plan",
  "decision_by": "manager@example.com",
  "decision_source": "slack",
  "external_interaction_id": "slack-action-1723091000.000100-user",
  "payload": {
    "selected_option": "OPTION-2"
  }
}
```

Use `decision_source=slack` for a Slack interaction and `decision_source=supervity_workbench` for Supervity Human Review. Supply either `workbench_item_id` or `supervity_form_id`; sending both is useful for traceability.

When a user decides in the Command Center, the backend submits the existing Supervity form with:

```text
command_center_run_id
incident_id
workbench_item_id
decision
reason
payload
decision_by
decision_source=command_center
slack_channel_id
slack_message_ts
slack_thread_ts
```

The Slack fields are included when a prior review-delivery receipt exists, allowing Auto to update the original message.

## Completion and failure

Workflow state and notification delivery are separate receipts:

1. Call `status_callback_url` with `status=completed` or `status=failed`.
2. Update or post the Slack outcome.
3. Call `notification_callback_url` with `notification_type=workflow_completed` and `status=updated`, or `notification_type=workflow_failed` with the actual Slack delivery result.

This ordering prevents an approval from being presented as “done” before the external procurement action is verified.

## Querying the ledger

Authenticated users can inspect correlated receipts:

```http
GET /api/command-center/notifications?run_id=RUN-...
GET /api/command-center/integrations
GET /api/command-center/workbench
```

Workbench responses include `decision_source` and `decision_external_ref`. Notification rows retain the Supervity event ID, Slack channel/message reference, delivery state, attempt, and timestamps, but no Slack credential.

## Local verification

```powershell
$env:DATABASE_URL='sqlite:///./command-center-test.db'
uv run --with-requirements packages/requirements.txt python -m pytest tests/test_command_center.py tests/test_external_clients.py -q
alembic upgrade head
```

The automated coverage proves automatic Outlook deduplication, platform review,
Slack decision replay, simultaneous competing-channel rejection, correlated
completion, failed delivery health, and callback-input exposure. A live Slack
post or interactive action remains an upstream Supervity configuration step.
