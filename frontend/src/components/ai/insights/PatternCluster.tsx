'use client'

import { cn } from '@/lib/utils'
import { Icons } from '@/components/ui/icons'

export interface Pattern {
  name: string
  frequency: string
  confidence: number
  sample_size?: number
  description?: string
  is_demo?: boolean
}

interface PatternClusterProps {
  patterns: Pattern[]
}

export function PatternCluster({ patterns }: PatternClusterProps) {
  if (patterns.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className={cn(
          'mb-4 flex h-12 w-12 items-center justify-center rounded-xl',
          'bg-muted/50'
        )}>
          <Icons.activity className="h-6 w-6 text-muted-foreground" strokeWidth={1.5} />
        </div>
        <p className="text-sm text-muted-foreground">No patterns detected yet.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {patterns.map((pattern, idx) => (
        <div
          key={idx}
          className={cn(
            'flex items-center gap-4 rounded-xl p-4',
            'bg-white/50 border border-border/50',
            'transition-all duration-200 hover:bg-white hover:shadow-soft'
          )}
        >
          {/* Icon */}
          <div className={cn(
            'flex h-10 w-10 items-center justify-center rounded-lg',
            'bg-brand-cornflower/10'
          )}>
            <Icons.activity className="h-5 w-5 text-brand-cornflower" strokeWidth={1.5} />
          </div>

          {/* Info */}
          <div className="flex-1">
            <h4 className="font-medium text-foreground">{pattern.name}</h4>
            {pattern.description && (
              <p className="text-xs text-muted-foreground mt-0.5">{pattern.description}</p>
            )}
            <p className="text-xs text-muted-foreground">
              Frequency: {pattern.frequency}
              {pattern.sample_size ? ` · ${pattern.sample_size.toLocaleString()} samples` : ''}
            </p>
          </div>

          {/* Confidence */}
          <div className="flex flex-col items-end">
            <span className="text-sm font-semibold text-brand-navy">
              {Math.round(pattern.confidence * 100)}%
            </span>
            <span className="text-[10px] text-muted-foreground">confidence</span>
          </div>

          {/* Confidence bar */}
          <div className="hidden sm:block w-24">
            <div className="h-2 rounded-full bg-muted/50 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-brand-cornflower to-brand-purple transition-all duration-500"
                style={{ width: `${pattern.confidence * 100}%` }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

