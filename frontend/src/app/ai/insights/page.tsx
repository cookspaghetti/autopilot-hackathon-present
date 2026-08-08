'use client'

import Link from 'next/link'
import { useState } from 'react'

import {
  EvidenceList,
  PageHeader,
  ResourceState,
  StatusBadge,
} from '@/components/command-center'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useApiResource } from '@/hooks/useApiResource'
import { apiClient } from '@/lib/api-client'
import type { Insight } from '@/types/command-center'

export default function InsightsPage() {
  const resource = useApiResource<Insight[]>('/api/command-center/insights')
  const insights = resource.data ?? []
  const [generating, setGenerating] = useState(false)
  const [generationError, setGenerationError] = useState<string | null>(null)

  async function generate() {
    setGenerating(true)
    setGenerationError(null)
    try {
      const generated = await apiClient.post<Insight[]>(
        '/api/command-center/insights/generate'
      )
      resource.setData(generated)
    } catch (error) {
      setGenerationError(
        error instanceof Error ? error.message : 'Insight generation failed'
      )
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className='space-y-6'>
      <PageHeader
        eyebrow='Evidence-backed intelligence'
        title='AI Insights'
        description='Patterns, anomalies, and recommendations generated from processed procurement records—not template demo data.'
        actions={
          <Button variant='outline' disabled={generating} onClick={() => void generate()}>
            {generating ? 'Analyzing…' : 'Generate from Supabase'}
          </Button>
        }
      />

      {generationError && (
        <div className='rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700'>
          {generationError}
        </div>
      )}

      <ResourceState
        isLoading={resource.isLoading}
        error={resource.error}
        isEmpty={insights.length === 0}
        emptyTitle='No evidence-backed insights yet'
        emptyDescription='Insights appear after the analysis service processes operational records.'
        onRetry={resource.refresh}
      >
        <div className='grid gap-5 xl:grid-cols-2'>
          {insights.map((insight) => (
            <Card key={insight.insight_id} className='h-full'>
              <CardHeader>
                <div className='flex flex-wrap items-center gap-2'>
                  <StatusBadge value={insight.severity} />
                  <StatusBadge value={insight.kind} />
                </div>
                <CardTitle className='pt-2'>{insight.title}</CardTitle>
                <p className='text-sm text-muted-foreground'>{insight.summary}</p>
              </CardHeader>
              <CardContent className='space-y-5'>
                <div className='rounded-xl bg-brand-cornflower/5 p-4'>
                  <p className='text-micro uppercase text-brand-muted'>Recommended action</p>
                  <p className='mt-1 text-sm font-medium text-brand-navy'>
                    {insight.recommendation}
                  </p>
                </div>
                <div>
                  <h3 className='mb-2 text-sm font-semibold text-brand-navy'>Evidence</h3>
                  <EvidenceList evidence={insight.evidence} />
                </div>
                {insight.affected_entity_ids.length > 0 && (
                  <p className='text-xs text-muted-foreground'>
                    Affected records: {insight.affected_entity_ids.join(', ')}
                  </p>
                )}
                {insight.action_type && (
                  <Button asChild variant='outline'>
                    <Link href={insight.action_type === 'create_policy' ? '/ai/policies' : '/workbench'}>
                      Open action surface
                    </Link>
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </ResourceState>
    </div>
  )
}
