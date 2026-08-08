'use client'

import { useMemo, useState } from 'react'

import {
  PageHeader,
  ResourceState,
  StatusBadge,
} from '@/components/command-center'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Icons } from '@/components/ui/icons'
import { useApiResource } from '@/hooks/useApiResource'
import { apiClient } from '@/lib/api-client'
import type {
  IntegrationHealth,
  SupervityConnectedAccount,
  SupervityIntegrationInventory,
  SupervitySchedule,
} from '@/types/command-center'

function timestamp(value?: string | null) {
  if (!value) return 'Never'
  return new Intl.DateTimeFormat('en-MY', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function integrationKey(value: string) {
  return value
    .toLowerCase()
    .replace(/^microsoft[\s_-]+/, '')
    .replace(/[^a-z0-9]/g, '')
}

function canonicalIntegrationKey(value: string) {
  const key = integrationKey(value)
  return key === 'slackviasupervity' ? 'slack' : key
}

function canonicalIntegrationId(integration: IntegrationCardView) {
  return canonicalIntegrationKey(integration.integrationId)
}

function integrationName(value: string) {
  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ')
}

interface IntegrationCardView {
  integrationId: string
  name: string
  category: string
  health: IntegrationHealth | null
  account: SupervityConnectedAccount | null
  actionsCount: number
  connectionStatus: string
  connectionLabel: string
}

function integrationPurpose(integration: IntegrationCardView) {
  const purpose = integration.health?.metadata.purpose
  if (typeof purpose === 'string') return purpose

  switch (canonicalIntegrationId(integration)) {
    case 'outlook':
      return 'Email channel available through Supervity'
    case 'slack':
      return 'Decision and outcome notifications'
    default:
      return integration.account
        ? 'Connected integration available to Auto workflows'
        : 'Orchestrator and Operator execution'
  }
}

function verificationLabel(integration: IntegrationCardView) {
  if (
    ['outlook', 'slack'].includes(canonicalIntegrationId(integration)) ||
    !integration.health
  ) {
    return 'Status reported by the Supervity integrations API'
  }
  return 'Verified by its Auto smoke workflow'
}

function integrationHealthStatus(integration: IntegrationCardView) {
  if (canonicalIntegrationId(integration) === 'slack') {
    return integration.connectionStatus
  }
  return integration.health?.status ?? integration.connectionStatus
}

function recordsObserved(integration: IntegrationCardView) {
  if (
    ['supervityauto', 'outlook', 'slack'].includes(
      canonicalIntegrationId(integration)
    )
  ) {
    return 'Not applicable'
  }
  if (!integration.health) return 'Not reported by API'
  return integration.health.records_seen ?? 'Not yet verified'
}

function lastVerified(integration: IntegrationCardView) {
  if (
    ['outlook', 'slack'].includes(canonicalIntegrationId(integration))
  ) {
    return 'N/A'
  }
  return integration.health
    ? timestamp(integration.health.last_success_at)
    : 'On refresh'
}

export default function DataManagerPage() {
  const healthResource = useApiResource<IntegrationHealth[]>(
    '/api/command-center/integrations'
  )
  const inventoryResource = useApiResource<SupervityIntegrationInventory>(
    '/api/command-center/supervity/integrations'
  )
  const schedulesResource = useApiResource<SupervitySchedule[]>(
    '/api/command-center/supervity/schedules'
  )
  const integrationCards = useMemo<IntegrationCardView[]>(() => {
    const hiddenIntegrationKeys = new Set(['supervitychat'])
    const healthIntegrations = (healthResource.data ?? []).filter(
      (integration) =>
        !hiddenIntegrationKeys.has(
          canonicalIntegrationKey(integration.integration_id)
        )
    )
    const accounts = inventoryResource.data?.connected_accounts ?? []
    const inventoryLoaded = inventoryResource.data !== null
    const accountByKey = new Map(
      accounts.map((account) => [
        canonicalIntegrationKey(account.integration),
        account,
      ])
    )
    const actionCounts = new Map<string, number>()

    for (const action of inventoryResource.data?.actions ?? []) {
      const key = canonicalIntegrationKey(action.integration)
      actionCounts.set(key, (actionCounts.get(key) ?? 0) + 1)
    }

    const matchedAccounts = new Set<string>()
    const cards: IntegrationCardView[] = healthIntegrations.map((health) => {
      const key = canonicalIntegrationKey(health.integration_id)
      const account = accountByKey.get(key) ?? null
      const isSupervityPlatform = health.integration_id === 'supervity-auto'

      if (account) matchedAccounts.add(key)

      return {
        integrationId: health.integration_id,
        name: health.name,
        category: health.category,
        health: health.integration_id === 'outlook' ? null : health,
        account,
        actionsCount: isSupervityPlatform
          ? (inventoryResource.data?.actions.length ?? 0)
          : Math.max(account?.actions_count ?? 0, actionCounts.get(key) ?? 0),
        connectionStatus: isSupervityPlatform
          ? health.status
          : inventoryLoaded
            ? account
              ? 'healthy'
              : 'disconnected'
            : health.status,
        connectionLabel: isSupervityPlatform
          ? health.status
          : inventoryLoaded
            ? (account?.status ?? 'not connected')
            : health.status,
      }
    })

    for (const account of accounts) {
      const key = canonicalIntegrationKey(account.integration)
      if (matchedAccounts.has(key) || hiddenIntegrationKeys.has(key)) continue

      cards.push({
        integrationId: `auto-${account.integration}`,
        name: integrationName(account.integration),
        category: 'auto_integration',
        health: null,
        account,
        actionsCount: account.actions_count,
        connectionStatus: 'healthy',
        connectionLabel: account.status,
      })
    }

    return cards
  }, [healthResource.data, inventoryResource.data])
  const [testing, setTesting] = useState<string | null>(null)
  const [testError, setTestError] = useState<string | null>(null)

  async function testConnection(integrationId: string) {
    setTesting(integrationId)
    setTestError(null)
    try {
      await apiClient.post(
        `/api/command-center/integrations/${integrationId}/test`
      )
      await healthResource.refresh()
    } catch (error) {
      setTestError(
        error instanceof Error ? error.message : 'Health test failed'
      )
      await healthResource.refresh()
    } finally {
      setTesting(null)
    }
  }

  return (
    <div className='space-y-6'>
      <PageHeader
        eyebrow='Live integration proof'
        title='Data Manager'
        description='Connected Auto accounts, available actions, backend health, and processed record counts across channels and systems.'
        actions={
          <Button
            variant='outline'
            onClick={() =>
              void Promise.all([
                healthResource.refresh(),
                inventoryResource.refresh(),
                schedulesResource.refresh(),
              ])
            }
          >
            <Icons.refresh className='mr-2 h-4 w-4' />
            Refresh integrations
          </Button>
        }
      />

      {testError && (
        <div className='rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700'>
          {testError}
        </div>
      )}

      <ResourceState
        isLoading={healthResource.isLoading || inventoryResource.isLoading}
        error={healthResource.error ?? inventoryResource.error}
        isEmpty={integrationCards.length === 0}
        emptyTitle='No integrations registered'
        emptyDescription='No Command Center or Supervity integrations were found.'
        onRetry={() =>
          void Promise.all([
            healthResource.refresh(),
            inventoryResource.refresh(),
          ])
        }
      >
        <div className='grid gap-5 md:grid-cols-2 xl:grid-cols-3'>
          {integrationCards.map((integration) => (
            <Card
              key={integration.integrationId}
              className='flex h-full flex-col'
            >
              <CardHeader>
                <div className='flex items-center justify-between gap-3'>
                  <div className='flex items-center gap-3'>
                    <div className='rounded-xl bg-brand-navy p-2.5 text-white'>
                      <Icons.network className='h-5 w-5' />
                    </div>
                    <div>
                      <CardTitle>{integration.name}</CardTitle>
                      <p className='mt-1 text-xs text-muted-foreground'>
                        {integration.category.replaceAll('_', ' ')}
                      </p>
                    </div>
                  </div>
                  <StatusBadge
                    value={integration.connectionStatus}
                    label={integration.connectionLabel}
                  />
                </div>
              </CardHeader>
              <CardContent className='flex flex-1 flex-col gap-3 text-sm'>
                <div className='grid grid-cols-2 gap-3 rounded-xl bg-muted/20 p-3'>
                  <div>
                    <p className='text-xs text-muted-foreground'>
                      Auto account
                    </p>
                    <p className='mt-1 break-all font-medium'>
                      {integration.integrationId === 'supervity-auto'
                        ? 'Management API'
                        : (integration.account?.name ?? 'Not connected')}
                    </p>
                  </div>
                  <div>
                    <p className='text-xs text-muted-foreground'>
                      Available actions
                    </p>
                    <p className='mt-1 font-semibold text-brand-navy'>
                      {integration.actionsCount}
                    </p>
                  </div>
                </div>
                <div className='grid grid-cols-2 gap-3 rounded-xl border p-3'>
                  <div>
                    <p className='text-xs text-muted-foreground'>
                      Integration health
                    </p>
                    <StatusBadge
                      className='mt-1'
                      value={integrationHealthStatus(integration)}
                    />
                  </div>
                  <div>
                    <p className='text-xs text-muted-foreground'>
                      Last verified
                    </p>
                    <p className='mt-1 font-medium'>
                      {lastVerified(integration)}
                    </p>
                  </div>
                </div>
                <div>
                  <p className='text-xs text-muted-foreground'>
                    Records observed
                  </p>
                  <p className='mt-1 font-semibold text-brand-navy'>
                    {recordsObserved(integration)}
                  </p>
                </div>
                {integration.health?.last_error && (
                  <div className='rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700'>
                    {integration.health.last_error}
                  </div>
                )}
                <p className='text-xs text-muted-foreground'>
                  {integrationPurpose(integration)}
                </p>
                <div className='mt-auto pt-1'>
                  {['supabase', 'supervity-auto'].includes(
                    integration.integrationId
                  ) ? (
                    <Button
                      variant='outline'
                      className='w-full'
                      disabled={testing !== null}
                      onClick={() =>
                        void testConnection(integration.integrationId)
                      }
                    >
                      {testing === integration.integrationId
                        ? 'Testing…'
                        : 'Test connection'}
                    </Button>
                  ) : (
                    <p className='rounded-lg bg-muted/30 p-2 text-center text-xs text-muted-foreground'>
                      {verificationLabel(integration)}
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </ResourceState>

      <section className='space-y-3'>
        <div>
          <h2 className='text-lg font-semibold text-brand-navy'>
            Connected in Auto
          </h2>
          <p className='text-sm text-muted-foreground'>
            Raw OAuth account and action inventory reported by Supervity. The
            cards above combine this inventory with Command Center operational
            health.
          </p>
        </div>
        <ResourceState
          isLoading={inventoryResource.isLoading}
          error={inventoryResource.error}
          isEmpty={
            inventoryResource.data !== null &&
            inventoryResource.data.connected_accounts.length === 0 &&
            inventoryResource.data.actions.length === 0
          }
          emptyTitle='No connected Auto integrations'
          emptyDescription='Connect an OAuth account in Supervity, then refresh this page.'
          onRetry={inventoryResource.refresh}
        >
          {inventoryResource.data && (
            <div className='grid gap-5 lg:grid-cols-2'>
              <Card>
                <CardHeader>
                  <CardTitle>
                    Accounts ({inventoryResource.data.connected_accounts.length}
                    )
                  </CardTitle>
                </CardHeader>
                <CardContent className='space-y-3'>
                  {inventoryResource.data.connected_accounts.map(
                    (account, index) => (
                      <div
                        key={`${account.integration}-${index}`}
                        className='flex items-center justify-between gap-3 rounded-xl border p-3'
                      >
                        <div>
                          <p className='font-medium text-brand-navy'>
                            {account.integration}
                          </p>
                          <p className='text-xs text-muted-foreground'>
                            {account.name}
                          </p>
                        </div>
                        <div className='text-right'>
                          <StatusBadge value={account.status} />
                          <p className='mt-1 text-xs text-muted-foreground'>
                            {account.actions_count} actions
                          </p>
                        </div>
                      </div>
                    )
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>
                    Available actions ({inventoryResource.data.actions.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className='max-h-96 space-y-3 overflow-y-auto'>
                  {inventoryResource.data.actions.map((action, index) => (
                    <div
                      key={`${action.integration}-${action.name}-${index}`}
                      className='rounded-xl border p-3'
                    >
                      <div className='flex items-center justify-between gap-3'>
                        <p className='font-medium text-brand-navy'>
                          {action.name}
                        </p>
                        <span className='text-xs text-muted-foreground'>
                          {action.integration}
                        </span>
                      </div>
                      {action.description && (
                        <p className='mt-1 text-xs text-muted-foreground'>
                          {action.description}
                        </p>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          )}
        </ResourceState>
      </section>

      <section className='space-y-3'>
        <div>
          <h2 className='text-lg font-semibold text-brand-navy'>
            Auto schedules
          </h2>
          <p className='text-sm text-muted-foreground'>
            Read-only recurring workflow plans in the active Supervity
            organization.
          </p>
        </div>
        <ResourceState
          isLoading={schedulesResource.isLoading}
          error={schedulesResource.error}
          isEmpty={
            schedulesResource.data !== null &&
            schedulesResource.data.length === 0
          }
          emptyTitle='No Auto schedules'
          emptyDescription='No recurring workflow schedules were returned for the active organization.'
          onRetry={schedulesResource.refresh}
        >
          <div className='grid gap-5 md:grid-cols-2 xl:grid-cols-3'>
            {(schedulesResource.data ?? []).map((schedule) => (
              <Card key={schedule.schedule_id}>
                <CardHeader>
                  <div className='flex items-start justify-between gap-3'>
                    <div>
                      <CardTitle>{schedule.name}</CardTitle>
                      {schedule.workflow_name && (
                        <p className='mt-1 text-xs text-muted-foreground'>
                          {schedule.workflow_name}
                        </p>
                      )}
                    </div>
                    <StatusBadge value={schedule.status} />
                  </div>
                </CardHeader>
                <CardContent className='space-y-2 text-sm'>
                  <p>
                    <span className='text-muted-foreground'>Timezone:</span>{' '}
                    {schedule.timezone ?? 'Platform default'}
                  </p>
                  <p className='break-words text-xs text-muted-foreground'>
                    {schedule.expression ?? 'Schedule definition not provided'}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </ResourceState>
      </section>
    </div>
  )
}
