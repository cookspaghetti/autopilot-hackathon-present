'use client'

import { useMemo, useState } from 'react'

import {
  MetricCard,
  PageHeader,
  ResourceState,
  StatusBadge,
} from '@/components/command-center'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Icons } from '@/components/ui/icons'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useApiResource } from '@/hooks/useApiResource'
import { apiClient } from '@/lib/api-client'
import type {
  DashboardSummary,
  SupervityRunSync,
  WorkflowRun,
} from '@/types/command-center'

const money = new Intl.NumberFormat('en-MY', {
  style: 'currency',
  currency: 'MYR',
  maximumFractionDigits: 0,
})

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat('en-MY', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export default function HomePage() {
  const summary = useApiResource<DashboardSummary>(
    '/api/command-center/dashboard'
  )
  const runs = useApiResource<WorkflowRun[]>(
    '/api/command-center/runs?limit=12'
  )
  const [sourceRef, setSourceRef] = useState('')
  const [senderEmail, setSenderEmail] = useState('commander@example.test')
  const [noticeBody, setNoticeBody] = useState('')
  const [dispatching, setDispatching] = useState(false)
  const [dispatchMessage, setDispatchMessage] = useState<string | null>(null)
  const [syncingRun, setSyncingRun] = useState<string | null>(null)
  const activeRuns = useMemo(
    () =>
      (runs.data ?? []).filter(
        (run) => !['completed', 'failed', 'cancelled'].includes(run.status)
      ),
    [runs.data]
  )

  async function dispatchWorkflow() {
    if (!sourceRef.trim() || !senderEmail.trim() || !noticeBody.trim()) {
      setDispatchMessage(
        'Source reference, sender email, and notice body are required.'
      )
      return
    }
    setDispatching(true)
    setDispatchMessage(null)
    try {
      const run = await apiClient.post<WorkflowRun>(
        '/api/command-center/runs',
        {
          incident_id: sourceRef.trim(),
          source: 'command_center',
          input_payload: {
            source: 'command_center',
            source_ref: sourceRef.trim(),
            received_at_raw: new Date().toISOString(),
            sender_email: senderEmail.trim(),
            body: noticeBody.trim(),
          },
        }
      )
      await apiClient.post<WorkflowRun>(
        `/api/command-center/runs/${run.run_id}/start`
      )
      setDispatchMessage(
        `Dispatched ${run.run_id}. Auto is consuming the execution stream in the background.`
      )
      setSourceRef('')
      setNoticeBody('')
      await Promise.all([runs.refresh(), summary.refresh()])
    } catch (error) {
      setDispatchMessage(
        error instanceof Error ? error.message : 'Dispatch failed'
      )
    } finally {
      setDispatching(false)
    }
  }

  async function syncRun(run: WorkflowRun) {
    setSyncingRun(run.run_id)
    setDispatchMessage(null)
    try {
      const result = await apiClient.post<SupervityRunSync>(
        `/api/command-center/runs/${run.run_id}/sync-supervity`
      )
      setDispatchMessage(
        `Synced ${result.activities_seen} Auto activities; ${result.operator_results_added} new Operator results.`
      )
      await Promise.all([runs.refresh(), summary.refresh()])
    } catch (error) {
      setDispatchMessage(
        error instanceof Error ? error.message : 'Auto sync failed'
      )
    } finally {
      setSyncingRun(null)
    }
  }

  return (
    <div className='space-y-6'>
      <PageHeader
        eyebrow='Procurement Exception Commander'
        title='Concurrent disruption portfolio'
        description='Live Auto workflow state, governed decisions, recovery value, and integration health.'
      />

      <ResourceState
        isLoading={summary.isLoading}
        error={summary.error}
        onRetry={summary.refresh}
      >
        {summary.data && (
          <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-4'>
            <MetricCard
              label='Open disruptions'
              value={summary.data.open_disruptions}
              caption={`${summary.data.critical_disruptions} critical`}
              icon={<Icons.alertTriangle className='h-5 w-5' />}
            />
            <MetricCard
              label='Awaiting commander'
              value={summary.data.awaiting_decision}
              caption='Workbench decisions pending'
              icon={<Icons.workbench className='h-5 w-5' />}
            />
            <MetricCard
              label='Cost avoided'
              value={money.format(Number(summary.data.cost_avoided_myr))}
              caption={`${money.format(Number(summary.data.cost_at_risk_myr))} at risk`}
              icon={<Icons.trendingUp className='h-5 w-5' />}
            />
            <MetricCard
              label='Healthy integrations'
              value={`${summary.data.healthy_integrations}/${summary.data.total_integrations}`}
              caption='Channel, system of record, and Auto'
              icon={<Icons.network className='h-5 w-5' />}
            />
          </div>
        )}
      </ResourceState>

      <Card>
        <CardHeader>
          <CardTitle>Start a governed recovery run</CardTitle>
          <p className='text-sm text-muted-foreground'>
            Sends the five published inputs to Exception Commander Orchestrator
            as multipart form data. The API returns immediately while Auto
            streams in the background.
          </p>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-4 md:grid-cols-2'>
            <div className='space-y-2'>
              <Label htmlFor='source-ref'>Incident or source reference</Label>
              <Input
                id='source-ref'
                value={sourceRef}
                onChange={(event) => setSourceRef(event.target.value)}
                placeholder='DN-5046'
              />
            </div>
            <div className='space-y-2'>
              <Label htmlFor='sender-email'>Sender email</Label>
              <Input
                id='sender-email'
                type='email'
                value={senderEmail}
                onChange={(event) => setSenderEmail(event.target.value)}
              />
            </div>
          </div>
          <div className='space-y-2'>
            <Label htmlFor='notice-body'>Disruption notice</Label>
            <textarea
              id='notice-body'
              value={noticeBody}
              onChange={(event) => setNoticeBody(event.target.value)}
              placeholder='Paste or enter the inbound supplier notice.'
              className='min-h-28 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cornflower'
            />
          </div>
          <div className='flex flex-wrap items-center gap-3'>
            <Button
              onClick={() => void dispatchWorkflow()}
              disabled={dispatching}
            >
              {dispatching ? 'Dispatching…' : 'Start Auto workflow'}
            </Button>
            {dispatchMessage && (
              <p className='text-sm text-muted-foreground'>{dispatchMessage}</p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className='flex-row items-center justify-between'>
          <div>
            <CardTitle>Active recovery runs</CardTitle>
            <p className='mt-1 text-sm text-muted-foreground'>
              Every row is persisted backend state; refreshes do not reset
              progress.
            </p>
          </div>
          <button
            onClick={() =>
              void Promise.all([runs.refresh(), summary.refresh()])
            }
            className='rounded-lg border px-3 py-2 text-sm text-brand-navy hover:bg-muted'
          >
            Refresh
          </button>
        </CardHeader>
        <CardContent>
          <ResourceState
            isLoading={runs.isLoading}
            error={runs.error}
            isEmpty={activeRuns.length === 0}
            emptyTitle='No active disruptions'
            emptyDescription='Trigger a notice through Outlook or start a workflow from AI Manager.'
            onRetry={runs.refresh}
          >
            <div className='overflow-x-auto'>
              <table className='w-full text-left text-sm'>
                <thead className='border-b text-xs uppercase text-muted-foreground'>
                  <tr>
                    <th className='pb-3 font-medium'>Incident</th>
                    <th className='pb-3 font-medium'>State</th>
                    <th className='pb-3 font-medium'>Current Operator</th>
                    <th className='pb-3 font-medium'>Severity</th>
                    <th className='pb-3 text-right font-medium'>Updated</th>
                    <th className='pb-3 text-right font-medium'>Auto</th>
                  </tr>
                </thead>
                <tbody className='divide-y'>
                  {activeRuns.map((run) => (
                    <tr key={run.run_id}>
                      <td className='py-4'>
                        <p className='font-semibold text-brand-navy'>
                          {run.incident_id}
                        </p>
                        <p className='font-mono text-xs text-muted-foreground'>
                          {run.run_id}
                        </p>
                      </td>
                      <td className='py-4'>
                        <StatusBadge value={run.status} />
                      </td>
                      <td className='py-4 text-muted-foreground'>
                        {run.current_operator ?? 'Orchestrator'}
                      </td>
                      <td className='py-4'>
                        <StatusBadge value={run.severity} />
                      </td>
                      <td className='py-4 text-right text-muted-foreground'>
                        {formatTimestamp(run.updated_at)}
                      </td>
                      <td className='py-4 text-right'>
                        <Button
                          variant='outline'
                          className='h-8 px-3 text-xs'
                          disabled={!run.auto_run_id || syncingRun !== null}
                          onClick={() => void syncRun(run)}
                        >
                          {syncingRun === run.run_id ? 'Syncing…' : 'Sync'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ResourceState>
        </CardContent>
      </Card>
    </div>
  )
}
