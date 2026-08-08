'use client'

import { useEffect, useMemo, useState } from 'react'

import {
  PageHeader,
  ResourceState,
  StatusBadge,
} from '@/components/command-center'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useApiResource } from '@/hooks/useApiResource'
import { apiClient } from '@/lib/api-client'
import type { Policy } from '@/types/command-center'

export default function PoliciesPage() {
  const resource = useApiResource<Policy[]>('/api/command-center/policies')
  const policies = useMemo(() => resource.data ?? [], [resource.data])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = useMemo(
    () => policies.find((policy) => policy.policy_id === selectedId) ?? policies[0] ?? null,
    [policies, selectedId]
  )
  const [parameters, setParameters] = useState('{}')
  const [reasonTemplate, setReasonTemplate] = useState('')
  const [priority, setPriority] = useState('100')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!selected) return
    setParameters(JSON.stringify(selected.parameters, null, 2))
    setReasonTemplate(selected.reason_template)
    setPriority(String(selected.priority))
    setError(null)
  }, [selected])

  async function patchSelected(update: Record<string, unknown>) {
    if (!selected) return
    setSaving(true)
    setError(null)
    try {
      const updated = await apiClient.patch<Policy>(
        `/api/command-center/policies/${selected.policy_id}`,
        update
      )
      resource.setData(
        policies.map((policy) =>
          policy.policy_id === updated.policy_id ? updated : policy
        )
      )
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Policy update failed')
    } finally {
      setSaving(false)
    }
  }

  async function saveConfiguration() {
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(parameters) as Record<string, unknown>
    } catch {
      setError('Policy parameters must be valid JSON.')
      return
    }
    const parsedPriority = Number(priority)
    if (!Number.isInteger(parsedPriority) || parsedPriority < 0) {
      setError('Priority must be a non-negative integer.')
      return
    }
    await patchSelected({
      parameters: parsed,
      priority: parsedPriority,
      reason_template: reasonTemplate,
    })
  }

  return (
    <div className='space-y-6'>
      <PageHeader
        eyebrow='Pre-action governance'
        title='AI Policies'
        description='Editable, versioned rules evaluated by the backend before Auto executes a governed action.'
      />

      <ResourceState
        isLoading={resource.isLoading}
        error={resource.error}
        isEmpty={policies.length === 0}
        emptyTitle='No policies configured'
        emptyDescription='Run the idempotent control-plane seed to create the required baseline.'
        onRetry={resource.refresh}
      >
        <div className='grid gap-6 lg:grid-cols-[0.8fr_1.2fr]'>
          <Card>
            <CardHeader>
              <CardTitle>Current policy versions</CardTitle>
            </CardHeader>
            <CardContent className='space-y-3'>
              {policies.map((policy) => (
                <button
                  key={policy.policy_id}
                  onClick={() => setSelectedId(policy.policy_id)}
                  className={`w-full rounded-xl border p-4 text-left transition ${
                    selected?.policy_id === policy.policy_id
                      ? 'border-brand-cornflower bg-brand-cornflower/5'
                      : 'hover:border-brand-cornflower/40'
                  }`}
                >
                  <div className='flex flex-wrap items-center justify-between gap-2'>
                    <p className='font-semibold text-brand-navy'>{policy.name}</p>
                    <StatusBadge
                      value={policy.enabled ? policy.decision : 'disabled'}
                      label={policy.enabled ? policy.decision : 'disabled'}
                    />
                  </div>
                  <p className='mt-1 line-clamp-2 text-xs text-muted-foreground'>
                    {policy.description}
                  </p>
                  <p className='mt-2 font-mono text-[11px] text-muted-foreground'>
                    {policy.policy_id} · v{policy.version} · priority {policy.priority}
                  </p>
                </button>
              ))}
            </CardContent>
          </Card>

          {selected && (
            <Card>
              <CardHeader>
                <div className='flex flex-wrap items-center justify-between gap-3'>
                  <div>
                    <CardTitle>{selected.name}</CardTitle>
                    <p className='mt-1 text-sm text-muted-foreground'>
                      {selected.description}
                    </p>
                  </div>
                  <Button
                    variant='outline'
                    disabled={saving}
                    onClick={() => void patchSelected({ enabled: !selected.enabled })}
                  >
                    {selected.enabled ? 'Disable' : 'Enable'}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className='space-y-6'>
                <section>
                  <h3 className='text-sm font-semibold text-brand-navy'>Conditions</h3>
                  <div className='mt-2 space-y-2'>
                    {selected.conditions.map((condition, index) => (
                      <div key={`${condition.field_path}-${index}`} className='rounded-lg border p-3'>
                        <div className='flex flex-wrap items-center gap-2 font-mono text-xs'>
                          <span className='font-semibold text-brand-navy'>
                            {condition.field_path}
                          </span>
                          <span className='rounded bg-muted px-2 py-1'>
                            {condition.operator.replaceAll('_', ' ')}
                          </span>
                          <span>{JSON.stringify(condition.value)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className='mt-2 text-xs text-muted-foreground'>
                    Match mode: {selected.match_mode.toUpperCase()} · Effective decision:{' '}
                    {selected.decision.toUpperCase()}
                    {selected.approval_role && ` · Role: ${selected.approval_role}`}
                  </p>
                </section>

                <section className='space-y-4 border-t pt-5'>
                  <label className='block text-sm font-medium text-brand-navy'>
                    Editable parameters
                    <textarea
                      value={parameters}
                      onChange={(event) => setParameters(event.target.value)}
                      className='mt-2 min-h-32 w-full rounded-xl border p-3 font-mono text-xs outline-none focus:border-brand-cornflower'
                      spellCheck={false}
                    />
                  </label>
                  <label className='block text-sm font-medium text-brand-navy'>
                    Priority
                    <input
                      type='number'
                      min={0}
                      value={priority}
                      onChange={(event) => setPriority(event.target.value)}
                      className='mt-2 w-full rounded-xl border p-3 text-sm outline-none focus:border-brand-cornflower'
                    />
                  </label>
                  <label className='block text-sm font-medium text-brand-navy'>
                    Logged decision reason
                    <textarea
                      value={reasonTemplate}
                      onChange={(event) => setReasonTemplate(event.target.value)}
                      className='mt-2 min-h-20 w-full rounded-xl border p-3 text-sm outline-none focus:border-brand-cornflower'
                    />
                  </label>
                  {error && <p className='text-sm text-red-600'>{error}</p>}
                  <div className='flex items-center justify-between gap-3'>
                    <p className='text-xs text-muted-foreground'>
                      Saving publishes version {selected.version + 1}; prior versions remain auditable.
                    </p>
                    <Button disabled={saving} onClick={() => void saveConfiguration()}>
                      {saving ? 'Publishing…' : 'Publish new version'}
                    </Button>
                  </div>
                </section>
              </CardContent>
            </Card>
          )}
        </div>
      </ResourceState>
    </div>
  )
}
