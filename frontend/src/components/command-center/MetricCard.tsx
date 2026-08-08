import type { ReactNode } from 'react'

import { Card, CardContent } from '@/components/ui/card'

interface MetricCardProps {
  label: string
  value: string | number
  caption?: string
  icon?: ReactNode
}

export function MetricCard({ label, value, caption, icon }: MetricCardProps) {
  return (
    <Card className='h-full'>
      <CardContent className='flex items-start justify-between p-5'>
        <div>
          <p className='text-micro uppercase text-brand-muted'>{label}</p>
          <p className='mt-2 font-display text-3xl font-bold text-brand-navy'>
            {value}
          </p>
          {caption && (
            <p className='mt-2 text-xs text-muted-foreground'>{caption}</p>
          )}
        </div>
        {icon && (
          <div className='rounded-xl bg-brand-navy p-2.5 text-white'>{icon}</div>
        )}
      </CardContent>
    </Card>
  )
}
