'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  EvidenceList,
  PageHeader,
  ResourceState,
  StatusBadge,
} from '@/components/command-center'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { apiClient } from '@/lib/api-client'
import { useApiResource } from '@/hooks/useApiResource'
import type { SupervityFormSync, WorkbenchItem } from '@/types/command-center'

type Decision = 'approve' | 'modify' | 'reject' | 'escalate'

interface UserFormOption {
  value: string
  label: string
}

interface UserFormField {
  id: string
  name: string
  label: string
  type: string
  required: boolean
  placeholder?: string | null
  options: UserFormOption[]
}

interface ReviewRecommendation {
  option_id?: string | null
  option_type?: string | null
  supplier_id?: string | null
  source_location?: string | null
  destination_location?: string | null
  item_number?: string | null
  requested_quantity?: number | null
  proposed_quantity?: number | null
  available_quantity?: number | null
  fulfills_required_quantity?: boolean | null
  unit?: string | null
  lead_time_days?: number | null
  incremental_cost_myr?: number | null
  guard_verdict?: string | null
  source_row_refs?: string[] | null
}

interface ReviewSummary {
  incident_id?: string | null
  severity: string
  requires_human_review: boolean
  recommendation?: ReviewRecommendation | null
  alternatives: ReviewRecommendation[]
  review_reasons: { code: string; explanation: string }[]
  governance: {
    decision?: string | null
    guard_status?: string | null
    portfolio_status?: string | null
    approval_roles: string[]
    policy_count: number
    policy_references: {
      policy_id: string
      version?: number | string | null
    }[]
  }
  technical_details: {
    operator_run_ids: Record<string, string>
  }
}

interface ParsedUserForm {
  title: string
  description: string
  context: { label: string; value: string }[]
  fields: UserFormField[]
  reviewSummary: ReviewSummary | null
}

function parsedUserForm(item: WorkbenchItem | null): ParsedUserForm | null {
  const value = item?.proposed_action.user_form
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const form = value as Partial<ParsedUserForm>
  if (!Array.isArray(form.context) || !Array.isArray(form.fields)) return null
  const rawSummary = (value as Record<string, unknown>).review_summary
  const reviewSummary =
    rawSummary && typeof rawSummary === 'object' && !Array.isArray(rawSummary)
      ? (rawSummary as ReviewSummary)
      : null
  return {
    title: typeof form.title === 'string' ? form.title : 'Human Review',
    description: typeof form.description === 'string' ? form.description : '',
    context: form.context,
    fields: form.fields,
    reviewSummary,
  }
}

function contextValue(value: string) {
  if (!value) return 'Not provided'
  if (!value.startsWith('{') && !value.startsWith('[')) return value
  try {
    return JSON.stringify(JSON.parse(value), null, 2)
  } catch {
    return value
  }
}

function humanize(value?: string | null) {
  if (!value) return 'Not provided'
  return value
    .replaceAll('-', '_')
    .split('_')
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

function quantity(value?: number | null, unit?: string | null) {
  if (typeof value !== 'number') return 'Not provided'
  const amount = new Intl.NumberFormat('en-MY', {
    maximumFractionDigits: 2,
  }).format(value)
  return unit ? `${amount} ${unit}` : amount
}

function money(value?: number | null) {
  if (typeof value !== 'number') return 'Not provided'
  return new Intl.NumberFormat('en-MY', {
    style: 'currency',
    currency: 'MYR',
    maximumFractionDigits: 2,
  }).format(value)
}

function portfolioStatus(value?: string | null) {
  if (value?.trim().toLowerCase() === 'ok') return 'No portfolio conflict'
  return humanize(value)
}

function recommendationDescription(option: ReviewRecommendation) {
  const amount = quantity(
    option.proposed_quantity ?? option.requested_quantity,
    option.unit
  )
  if (
    option.option_type === 'transfer_inventory' &&
    option.item_number &&
    option.source_location &&
    option.destination_location
  ) {
    return `Transfer ${amount} of ${option.item_number} from ${option.source_location} to ${option.destination_location}.`
  }
  if (option.item_number && option.supplier_id) {
    return `Source ${amount} of ${option.item_number} from supplier ${option.supplier_id}.`
  }
  return `Review the proposed ${humanize(option.option_type).toLowerCase()} recovery.`
}

function RecommendationCard({
  option,
  compact = false,
}: {
  option: ReviewRecommendation
  compact?: boolean
}) {
  const facts = [
    option.available_quantity !== undefined && {
      label: 'Available at source',
      value: quantity(option.available_quantity, option.unit),
    },
    option.fulfills_required_quantity !== undefined && {
      label: 'Quantity coverage',
      value: option.fulfills_required_quantity
        ? 'Fully covers the request'
        : 'Does not fully cover the request',
    },
    option.lead_time_days !== undefined && {
      label: 'Estimated lead time',
      value:
        typeof option.lead_time_days === 'number'
          ? `${option.lead_time_days} days`
          : 'Not provided',
    },
    option.incremental_cost_myr !== undefined && {
      label: 'Incremental cost',
      value: money(option.incremental_cost_myr),
    },
  ].filter((fact): fact is { label: string; value: string } => fact !== false)

  return (
    <div className='rounded-xl border border-brand-cornflower/30 bg-brand-cornflower/5 p-4'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <p className='text-xs font-semibold uppercase tracking-wide text-brand-cornflower'>
            {compact ? 'Alternative' : 'Recommended recovery'}
          </p>
          <h4 className='mt-1 font-semibold text-brand-navy'>
            {humanize(option.option_type)}
          </h4>
        </div>
        {option.guard_verdict && (
          <StatusBadge
            value={option.guard_verdict}
            label={`Option ${humanize(option.guard_verdict).toLowerCase()}`}
          />
        )}
      </div>
      <p className='mt-3 text-sm font-medium text-brand-navy'>
        {recommendationDescription(option)}
      </p>
      {!compact && facts.length > 0 && (
        <dl className='mt-4 grid gap-3 sm:grid-cols-2'>
          {facts.map((fact) => (
            <div key={fact.label} className='rounded-lg bg-white/70 p-3'>
              <dt className='text-xs text-muted-foreground'>{fact.label}</dt>
              <dd className='mt-1 text-sm font-semibold text-brand-navy'>
                {fact.value}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

function HumanReviewSummary({ summary }: { summary: ReviewSummary }) {
  const operatorRuns = Object.entries(
    summary.technical_details?.operator_run_ids ?? {}
  )
  const policyReferences = summary.governance?.policy_references ?? []
  const sourceReferences = summary.recommendation?.source_row_refs ?? []
  const hasTechnicalDetails =
    operatorRuns.length > 0 ||
    policyReferences.length > 0 ||
    sourceReferences.length > 0

  return (
    <div className='space-y-4'>
      <div className='rounded-xl border border-amber-200 bg-amber-50 p-4'>
        <div className='flex flex-wrap items-center justify-between gap-3'>
          <div>
            <p className='text-xs font-semibold uppercase tracking-wide text-amber-700'>
              Decision required
            </p>
            <p className='mt-1 font-semibold text-amber-950'>
              {summary.requires_human_review
                ? 'Human review is required before this recovery can continue.'
                : 'Review this recovery before continuing.'}
            </p>
          </div>
        </div>
        {summary.incident_id && (
          <p className='mt-2 text-xs text-amber-800'>
            Incident {summary.incident_id}
          </p>
        )}
      </div>

      {summary.recommendation && (
        <RecommendationCard option={summary.recommendation} />
      )}

      {summary.review_reasons.length > 0 && (
        <section className='rounded-xl border p-4'>
          <h4 className='font-semibold text-brand-navy'>
            Why your decision is needed
          </h4>
          <ul className='mt-3 space-y-2 text-sm text-slate-700'>
            {summary.review_reasons.map((reason) => (
              <li key={reason.code} className='flex gap-2'>
                <span className='mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-cornflower' />
                <span>{reason.explanation}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className='rounded-xl border p-4'>
        <h4 className='font-semibold text-brand-navy'>Governance summary</h4>
        <dl className='mt-3 grid gap-3 sm:grid-cols-2'>
          <div className='rounded-lg bg-muted/20 p-3'>
            <dt className='text-xs text-muted-foreground'>Overall decision</dt>
            <dd className='mt-1 text-sm font-semibold text-brand-navy'>
              {summary.requires_human_review
                ? 'Human review required'
                : humanize(summary.governance?.decision)}
            </dd>
          </div>
          <div className='rounded-lg bg-muted/20 p-3'>
            <dt className='text-xs text-muted-foreground'>Approval role</dt>
            <dd className='mt-1 text-sm font-semibold text-brand-navy'>
              {summary.governance?.approval_roles?.join(', ') ||
                'Not specified'}
            </dd>
          </div>
          <div className='rounded-lg bg-muted/20 p-3'>
            <dt className='text-xs text-muted-foreground'>Portfolio check</dt>
            <dd className='mt-1 text-sm font-semibold text-brand-navy'>
              {portfolioStatus(summary.governance?.portfolio_status)}
            </dd>
          </div>
          <div className='rounded-lg bg-muted/20 p-3'>
            <dt className='text-xs text-muted-foreground'>
              Policies evaluated
            </dt>
            <dd className='mt-1 text-sm font-semibold text-brand-navy'>
              {summary.governance?.policy_count ?? 0}
            </dd>
          </div>
        </dl>
      </section>

      {summary.alternatives.length > 0 && (
        <section className='space-y-3'>
          <h4 className='font-semibold text-brand-navy'>
            Other viable options
          </h4>
          {summary.alternatives.map((option, index) => (
            <RecommendationCard
              key={option.option_id ?? index}
              option={option}
              compact
            />
          ))}
        </section>
      )}

      {hasTechnicalDetails && (
        <details className='rounded-xl border bg-muted/10 p-4 text-sm'>
          <summary className='cursor-pointer font-medium text-brand-navy'>
            Technical details
          </summary>
          <div className='mt-4 space-y-4 text-xs'>
            {policyReferences.length > 0 && (
              <div>
                <p className='font-semibold text-muted-foreground'>
                  Governance policies
                </p>
                <div className='mt-2 flex flex-wrap gap-2'>
                  {policyReferences.map((policy) => (
                    <code
                      key={`${policy.policy_id}-${policy.version ?? ''}`}
                      className='rounded bg-slate-100 px-2 py-1 text-slate-700'
                    >
                      {policy.policy_id}
                      {policy.version ? ` v${policy.version}` : ''}
                    </code>
                  ))}
                </div>
              </div>
            )}
            {sourceReferences.length > 0 && (
              <div>
                <p className='font-semibold text-muted-foreground'>
                  Source records
                </p>
                {sourceReferences.map((reference) => (
                  <code key={reference} className='mt-1 block break-all'>
                    {reference}
                  </code>
                ))}
              </div>
            )}
            {operatorRuns.length > 0 && (
              <div>
                <p className='font-semibold text-muted-foreground'>
                  Operator runs
                </p>
                <dl className='mt-2 space-y-1'>
                  {operatorRuns.map(([name, runId]) => (
                    <div
                      key={name}
                      className='grid gap-1 sm:grid-cols-[7rem_1fr]'
                    >
                      <dt>{name}</dt>
                      <dd className='break-all font-mono'>{runId}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  )
}

export default function WorkbenchPage() {
  const resource = useApiResource<WorkbenchItem[]>(
    '/api/command-center/workbench'
  )
  const refreshWorkbench = resource.refresh
  const openItems = useMemo(
    () => (resource.data ?? []).filter((item) => item.status === 'open'),
    [resource.data]
  )
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected =
    openItems.find((item) => item.item_id === selectedId) ??
    openItems[0] ??
    null
  const userForm = useMemo(() => parsedUserForm(selected), [selected])
  const [reason, setReason] = useState('')
  const [modification, setModification] = useState('{}')
  const [formValues, setFormValues] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState<Decision | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncSummary, setSyncSummary] = useState<SupervityFormSync | null>(null)

  const syncApprovals = useCallback(async () => {
    setSyncing(true)
    setActionError(null)
    try {
      const result = await apiClient.post<SupervityFormSync>(
        '/api/command-center/workbench/sync-supervity'
      )
      setSyncSummary(result)
      await refreshWorkbench()
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : 'Approval sync failed'
      )
    } finally {
      setSyncing(false)
    }
  }, [refreshWorkbench])

  useEffect(() => {
    void syncApprovals()
  }, [syncApprovals])

  useEffect(() => {
    setFormValues(
      Object.fromEntries(
        (userForm?.fields ?? []).map((field) => [field.name, ''])
      )
    )
  }, [selected?.item_id, userForm])

  async function decide(
    decision: Decision,
    payloadOverride?: Record<string, unknown>,
    reasonOverride?: string
  ) {
    const decisionReason = reasonOverride?.trim() || reason.trim()
    if (!selected || !decisionReason) {
      setActionError('Add a decision rationale before continuing.')
      return
    }
    let payload = payloadOverride
    if (decision === 'modify' && !payload) {
      try {
        payload = JSON.parse(modification) as Record<string, unknown>
      } catch {
        setActionError('Modification payload must be valid JSON.')
        return
      }
    }
    setActionError(null)
    setSubmitting(decision)
    try {
      await apiClient.post(
        `/api/command-center/workbench/${selected.item_id}/decision`,
        {
          decision,
          reason: decisionReason,
          payload,
          expected_version: selected.version,
        }
      )
      setReason('')
      setModification('{}')
      setSelectedId(null)
      await resource.refresh()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Decision failed')
    } finally {
      setSubmitting(null)
    }
  }

  async function submitUserFormDecision() {
    if (!userForm) return
    const missing = userForm.fields.find(
      (field) => field.required && !formValues[field.name]?.trim()
    )
    if (missing) {
      setActionError(`${missing.label} is required.`)
      return
    }
    const reviewerAction = formValues['Reviewer Action']?.trim().toLowerCase()
    const decisionByAction: Record<string, Decision> = {
      approve: 'approve',
      modify: 'modify',
      'request replan': 'modify',
      reject: 'reject',
    }
    const decision = decisionByAction[reviewerAction]
    if (!decision) {
      setActionError('Select a Reviewer Action before continuing.')
      return
    }
    const decisionReason =
      formValues['Decision Rationale']?.trim() ||
      `Submitted Supervity Human Review action: ${formValues['Reviewer Action']}`
    await decide(decision, formValues, decisionReason)
  }

  return (
    <div className='space-y-6'>
      <PageHeader
        eyebrow='Human in command'
        title='Decision Workbench'
        description='Resolve policy exceptions with source evidence, alternatives, and a persisted continuation.'
        actions={
          <Button
            variant='outline'
            disabled={syncing}
            onClick={() => void syncApprovals()}
          >
            {syncing ? 'Syncing Auto approvals…' : 'Sync Auto approvals'}
          </Button>
        }
      />

      {syncSummary && (
        <section aria-label='Auto form reconciliation' className='space-y-3'>
          <div className='rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800'>
            Reconciled {syncSummary.forms_seen} Auto forms across{' '}
            {syncSummary.matched_runs} matched runs ·{' '}
            {syncSummary.items_created} added · {syncSummary.items_updated}{' '}
            refreshed
            {syncSummary.other_forms > 0 && (
              <> · {syncSummary.other_forms} with another status</>
            )}
          </div>
          <div className='grid gap-3 sm:grid-cols-2 xl:grid-cols-5'>
            <div className='rounded-xl border border-amber-200 bg-amber-50 p-4'>
              <p className='text-xs font-semibold uppercase tracking-wide text-amber-700'>
                Pending
              </p>
              <p className='mt-1 text-2xl font-semibold text-amber-950'>
                {syncSummary.pending_forms}
              </p>
              <p className='text-xs text-amber-800'>Awaiting a decision</p>
            </div>
            <div className='rounded-xl border border-emerald-200 bg-emerald-50 p-4'>
              <p className='text-xs font-semibold uppercase tracking-wide text-emerald-700'>
                Approved
              </p>
              <p className='mt-1 text-2xl font-semibold text-emerald-950'>
                {syncSummary.approved_forms}
              </p>
              <p className='text-xs text-emerald-800'>Confirmed by the API</p>
            </div>
            <div className='rounded-xl border border-blue-200 bg-blue-50 p-4'>
              <p className='text-xs font-semibold uppercase tracking-wide text-blue-700'>
                Modified
              </p>
              <p className='mt-1 text-2xl font-semibold text-blue-950'>
                {syncSummary.modified_forms}
              </p>
              <p className='text-xs text-blue-800'>Returned for replanning</p>
            </div>
            <div className='rounded-xl border border-rose-200 bg-rose-50 p-4'>
              <p className='text-xs font-semibold uppercase tracking-wide text-rose-700'>
                Rejected
              </p>
              <p className='mt-1 text-2xl font-semibold text-rose-950'>
                {syncSummary.rejected_forms}
              </p>
              <p className='text-xs text-rose-800'>Closed by the API</p>
            </div>
            <div className='rounded-xl border border-slate-200 bg-slate-50 p-4'>
              <p className='text-xs font-semibold uppercase tracking-wide text-slate-700'>
                Expired
              </p>
              <p className='mt-1 text-2xl font-semibold text-slate-950'>
                {syncSummary.expired_forms}
              </p>
              <p className='text-xs text-slate-700'>No longer actionable</p>
            </div>
          </div>
        </section>
      )}
      {actionError && !selected && (
        <div className='rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700'>
          {actionError}
        </div>
      )}

      <ResourceState
        isLoading={resource.isLoading}
        error={resource.error}
        isEmpty={openItems.length === 0}
        emptyTitle='No decisions are waiting'
        emptyDescription='Governed Auto runs will create Workbench items here before execution.'
        onRetry={resource.refresh}
      >
        <div className='grid gap-6 lg:grid-cols-[0.8fr_1.2fr]'>
          <Card>
            <CardHeader>
              <CardTitle>Open decisions ({openItems.length})</CardTitle>
            </CardHeader>
            <CardContent className='space-y-3'>
              {openItems.map((item) => (
                <button
                  key={item.item_id}
                  onClick={() => setSelectedId(item.item_id)}
                  className={`w-full rounded-xl border p-4 text-left transition ${
                    selected?.item_id === item.item_id
                      ? 'border-brand-cornflower bg-brand-cornflower/5'
                      : 'hover:border-brand-cornflower/40 hover:bg-muted/20'
                  }`}
                >
                  <div className='flex items-center justify-between gap-2'>
                    <p className='font-semibold text-brand-navy'>
                      {item.incident_id}
                    </p>
                    <StatusBadge value={item.severity} />
                  </div>
                  <p className='mt-2 text-sm font-medium'>{item.title}</p>
                  {item.supervity_form_id && (
                    <p className='mt-1 text-xs font-medium text-brand-cornflower'>
                      Auto approval · {item.supervity_form_status ?? 'pending'}
                    </p>
                  )}
                  <p className='mt-1 line-clamp-2 text-xs text-muted-foreground'>
                    {item.summary}
                  </p>
                </button>
              ))}
            </CardContent>
          </Card>

          {selected && (
            <Card>
              <CardHeader>
                <div className='flex flex-wrap items-center gap-2'>
                  <StatusBadge value={selected.severity} />
                  {selected.supervity_form_id && (
                    <StatusBadge
                      value={selected.supervity_form_status ?? 'pending'}
                      label='Awaiting decision'
                    />
                  )}
                </div>
                <CardTitle className='pt-2'>{selected.title}</CardTitle>
                <p className='text-sm text-muted-foreground'>
                  {userForm
                    ? 'Review the proposed recovery and governance checks before deciding.'
                    : selected.summary}
                </p>
              </CardHeader>
              <CardContent className='space-y-6'>
                {userForm ? (
                  <section className='space-y-3'>
                    <div>
                      <p className='text-xs font-semibold uppercase tracking-wide text-brand-cornflower'>
                        Supervity Human Review
                      </p>
                      <h3 className='mt-1 text-lg font-semibold text-brand-navy'>
                        {userForm.title}
                      </h3>
                      {userForm.description && !userForm.reviewSummary && (
                        <p className='mt-1 text-sm text-muted-foreground'>
                          {userForm.description}
                        </p>
                      )}
                    </div>
                    {userForm.reviewSummary ? (
                      <HumanReviewSummary summary={userForm.reviewSummary} />
                    ) : (
                      <div className='grid gap-3 sm:grid-cols-2'>
                        {userForm.context.map((item, index) => (
                          <div
                            key={`${item.label}-${index}`}
                            className='rounded-xl border bg-muted/20 p-3'
                          >
                            <p className='text-xs text-muted-foreground'>
                              {item.label}
                            </p>
                            <pre className='mt-1 whitespace-pre-wrap break-words font-sans text-sm font-medium text-brand-navy'>
                              {contextValue(item.value)}
                            </pre>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                ) : (
                  <section>
                    <h3 className='text-sm font-semibold text-brand-navy'>
                      Proposed action
                    </h3>
                    <pre className='mt-2 overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-100'>
                      {JSON.stringify(selected.proposed_action, null, 2)}
                    </pre>
                  </section>
                )}

                {!userForm && selected.alternatives.length > 0 && (
                  <section>
                    <h3 className='text-sm font-semibold text-brand-navy'>
                      Alternatives
                    </h3>
                    <div className='mt-2 space-y-2'>
                      {selected.alternatives.map((alternative, index) => (
                        <pre
                          key={index}
                          className='overflow-x-auto rounded-lg border bg-muted/20 p-3 text-xs'
                        >
                          {JSON.stringify(alternative, null, 2)}
                        </pre>
                      ))}
                    </div>
                  </section>
                )}

                {!userForm && (
                  <section>
                    <h3 className='mb-2 text-sm font-semibold text-brand-navy'>
                      Evidence
                    </h3>
                    <EvidenceList evidence={selected.evidence} />
                  </section>
                )}

                {userForm ? (
                  <section className='space-y-4 border-t pt-5'>
                    <div>
                      <h3 className='text-sm font-semibold text-brand-navy'>
                        Decision form
                      </h3>
                      <p className='mt-1 text-xs text-muted-foreground'>
                        Parsed securely from the pending Supervity form.
                        Required fields are marked with an asterisk.
                      </p>
                    </div>
                    <div className='grid gap-4 sm:grid-cols-2'>
                      {userForm.fields.map((field) => (
                        <label
                          key={field.id}
                          className={`block text-sm font-medium text-brand-navy ${
                            field.type === 'textarea' ? 'sm:col-span-2' : ''
                          }`}
                        >
                          {field.label}
                          {field.required && (
                            <span className='ml-1 text-red-600'>*</span>
                          )}
                          {field.type === 'select' ? (
                            <select
                              value={formValues[field.name] ?? ''}
                              onChange={(event) =>
                                setFormValues((current) => ({
                                  ...current,
                                  [field.name]: event.target.value,
                                }))
                              }
                              className='mt-2 h-10 w-full rounded-xl border bg-white px-3 text-sm outline-none focus:border-brand-cornflower'
                            >
                              {field.options.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                          ) : field.type === 'textarea' ? (
                            <textarea
                              value={formValues[field.name] ?? ''}
                              onChange={(event) =>
                                setFormValues((current) => ({
                                  ...current,
                                  [field.name]: event.target.value,
                                }))
                              }
                              className='mt-2 min-h-24 w-full rounded-xl border bg-white p-3 text-sm outline-none focus:border-brand-cornflower'
                              placeholder={field.placeholder ?? undefined}
                            />
                          ) : (
                            <input
                              type={field.type === 'email' ? 'email' : 'text'}
                              value={formValues[field.name] ?? ''}
                              onChange={(event) =>
                                setFormValues((current) => ({
                                  ...current,
                                  [field.name]: event.target.value,
                                }))
                              }
                              className='mt-2 h-10 w-full rounded-xl border bg-white px-3 text-sm outline-none focus:border-brand-cornflower'
                              placeholder={field.placeholder ?? undefined}
                            />
                          )}
                        </label>
                      ))}
                    </div>
                    {actionError && (
                      <p className='text-sm text-red-600'>{actionError}</p>
                    )}
                    <Button
                      onClick={() => void submitUserFormDecision()}
                      disabled={submitting !== null}
                    >
                      {submitting ? 'Submitting decision…' : 'Submit decision'}
                    </Button>
                  </section>
                ) : (
                  <section className='space-y-3 border-t pt-5'>
                    <label className='block text-sm font-medium text-brand-navy'>
                      Decision rationale
                      <textarea
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                        className='mt-2 min-h-24 w-full rounded-xl border bg-white p-3 text-sm outline-none focus:border-brand-cornflower'
                        placeholder='Explain the trade-off and supporting evidence…'
                      />
                    </label>
                    <label className='block text-sm font-medium text-brand-navy'>
                      Modification payload
                      <textarea
                        value={modification}
                        onChange={(event) =>
                          setModification(event.target.value)
                        }
                        className='mt-2 min-h-20 w-full rounded-xl border bg-white p-3 font-mono text-xs outline-none focus:border-brand-cornflower'
                        spellCheck={false}
                      />
                    </label>
                    {actionError && (
                      <p className='text-sm text-red-600'>{actionError}</p>
                    )}
                    <div className='flex flex-wrap gap-2'>
                      <Button
                        onClick={() => void decide('approve')}
                        disabled={submitting !== null}
                      >
                        Approve and continue
                      </Button>
                      <Button
                        variant='outline'
                        onClick={() => void decide('modify')}
                        disabled={submitting !== null}
                      >
                        Modify and continue
                      </Button>
                      <Button
                        variant='outline'
                        className='border-red-200 text-red-700 hover:bg-red-50'
                        onClick={() => void decide('reject')}
                        disabled={submitting !== null}
                      >
                        Reject
                      </Button>
                      <Button
                        variant='outline'
                        className='border-amber-200 text-amber-800 hover:bg-amber-50'
                        onClick={() => void decide('escalate')}
                        disabled={submitting !== null}
                      >
                        Escalate for review
                      </Button>
                    </div>
                  </section>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </ResourceState>
    </div>
  )
}
