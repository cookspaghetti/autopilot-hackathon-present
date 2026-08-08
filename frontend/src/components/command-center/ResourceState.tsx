import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

interface ResourceStateProps {
  isLoading: boolean
  error: string | null
  isEmpty?: boolean
  emptyTitle?: string
  emptyDescription?: string
  onRetry?: () => void
  children: ReactNode
}

export function ResourceState({
  isLoading,
  error,
  isEmpty = false,
  emptyTitle = 'Nothing here yet',
  emptyDescription = 'New records will appear when the workflow produces them.',
  onRetry,
  children,
}: ResourceStateProps) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className='p-8 text-center text-sm text-muted-foreground'>
          Loading live state…
        </CardContent>
      </Card>
    )
  }
  if (error) {
    return (
      <Card className='border-red-200'>
        <CardContent className='space-y-3 p-8 text-center'>
          <p className='text-sm font-semibold text-red-700'>Unable to load data</p>
          <p className='text-sm text-muted-foreground'>{error}</p>
          {onRetry && (
            <Button variant='outline' size='sm' onClick={onRetry}>
              Retry
            </Button>
          )}
        </CardContent>
      </Card>
    )
  }
  if (isEmpty) {
    return (
      <Card>
        <CardContent className='p-8 text-center'>
          <p className='font-semibold text-brand-navy'>{emptyTitle}</p>
          <p className='mt-1 text-sm text-muted-foreground'>{emptyDescription}</p>
        </CardContent>
      </Card>
    )
  }
  return <>{children}</>
}
