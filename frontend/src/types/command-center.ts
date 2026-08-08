export type Severity = 'unknown' | 'low' | 'medium' | 'high' | 'critical'

export type WorkflowStatus =
  | 'queued'
  | 'running'
  | 'awaiting_approval'
  | 'executing'
  | 'completed'
  | 'needs_review'
  | 'failed'
  | 'cancelled'

export type PolicyDecision = 'allow' | 'review' | 'block'
export type WorkbenchStatus =
  | 'open'
  | 'approved'
  | 'modified'
  | 'rejected'
  | 'escalated'
  | 'expired'
export type IntegrationStatus =
  | 'unknown'
  | 'healthy'
  | 'degraded'
  | 'disconnected'

export interface EvidenceReference {
  system: string
  entity_type: string
  entity_id: string
  observed_at: string
  fields: string[]
  observed_values: Record<string, unknown>
  uri?: string | null
  checksum?: string | null
}

export interface WorkflowRun {
  run_id: string
  incident_id: string
  status: WorkflowStatus
  source: string
  source_ref?: string | null
  duplicate_trigger_count: number
  input_payload: Record<string, unknown>
  output_payload?: Record<string, unknown> | null
  requested_by?: string | null
  auto_run_id?: string | null
  current_operator?: string | null
  plan_run_id?: string | null
  error?: string | null
  severity: Severity
  cost_at_risk_myr: string
  cost_avoided_myr: string
  time_to_mitigation_hours?: number | null
  created_at: string
  updated_at: string
}

export interface PolicyCondition {
  field_path: string
  operator: string
  value?: unknown
}

export interface Policy {
  policy_id: string
  name: string
  description: string
  version: number
  priority: number
  enabled: boolean
  match_mode: 'all' | 'any'
  conditions: PolicyCondition[]
  decision: PolicyDecision
  reason_template: string
  approval_role?: string | null
  parameters: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface WorkbenchItem {
  item_id: string
  run_id: string
  incident_id: string
  title: string
  summary: string
  severity: Severity
  proposed_action: Record<string, unknown>
  alternatives: Record<string, unknown>[]
  policy_evaluation_ids: string[]
  evidence: EvidenceReference[]
  assigned_to?: string | null
  supervity_form_id?: string | null
  supervity_activity_run_id?: string | null
  supervity_form_status?: string | null
  status: WorkbenchStatus
  decision?: 'approve' | 'modify' | 'reject' | 'escalate' | null
  decision_by?: string | null
  decision_reason?: string | null
  decision_payload?: Record<string, unknown> | null
  decision_source?: 'command_center' | 'slack' | 'supervity_workbench' | null
  decision_external_ref?: string | null
  decided_at?: string | null
  created_at: string
  updated_at: string
  version: number
}

export interface IntegrationHealth {
  integration_id: string
  name: string
  category: string
  status: IntegrationStatus
  checked_at: string
  last_success_at?: string | null
  last_error?: string | null
  records_seen?: number | null
  metadata: Record<string, unknown>
}

export interface OutlookAuthorizationStart {
  authorization_url: string
}

export interface SupervityRunSync {
  run_id: string
  auto_run_id: string
  remote_status: string
  local_status: WorkflowStatus
  activities_seen: number
  operator_results_added: number
}

export interface SupervityFormSync {
  forms_seen: number
  pending_forms: number
  approved_forms: number
  modified_forms: number
  rejected_forms: number
  expired_forms: number
  other_forms: number
  matched_runs: number
  items_created: number
  items_updated: number
  forms_skipped: number
}

export interface SupervityConnectedAccount {
  name: string
  integration: string
  status: string
  actions_count: number
}

export interface SupervityIntegrationAction {
  name: string
  integration: string
  description?: string | null
}

export interface SupervityIntegrationInventory {
  connected_accounts: SupervityConnectedAccount[]
  actions: SupervityIntegrationAction[]
}

export interface SupervitySchedule {
  schedule_id: string
  name: string
  workflow_name?: string | null
  status: string
  timezone?: string | null
  expression?: string | null
  next_run_at?: string | null
  parameters: Record<string, unknown>
}

export interface Insight {
  insight_id: string
  kind: 'pattern' | 'anomaly' | 'recommendation'
  severity: Severity
  title: string
  summary: string
  recommendation: string
  evidence: EvidenceReference[]
  affected_entity_ids: string[]
  action_type?: string | null
  action_payload?: Record<string, unknown> | null
  created_at: string
}

export interface DashboardSummary {
  open_disruptions: number
  critical_disruptions: number
  awaiting_decision: number
  completed_runs: number
  cost_at_risk_myr: string
  cost_avoided_myr: string
  average_time_to_mitigation_hours?: number | null
  healthy_integrations: number
  total_integrations: number
}
