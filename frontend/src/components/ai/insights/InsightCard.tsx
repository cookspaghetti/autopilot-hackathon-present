'use client'

import { cn } from '@/lib/utils'
import { Icons } from '@/components/ui/icons'
import { Button } from '@/components/ui/button'

export type InsightSeverity = 'critical' | 'high' | 'warning' | 'medium' | 'low' | 'info'
export type InsightType = 'pattern' | 'anomaly' | 'recommendation' | 'trend' | 'alert'

export interface Insight {
  id: string
  type: InsightType
  severity: InsightSeverity
  title: string
  description: string
  data?: Record<string, unknown>
  suggested_action?: string
  action_type?: string
  confidence?: number
  created_at: string
  is_dismissed?: boolean
  is_actioned?: boolean
  is_demo?: boolean
}

interface InsightCardProps {
  insight: Insight
  onAction?: (insight: Insight) => void
  onDismiss?: (id: string) => void
}

/**
 * Get severity configuration for consistent styling across the app.
 * Supports both old severity names and new ones.
 */
export function getSeverityConfig(severity: InsightSeverity) {
  const configs = {
    critical: {
      icon: Icons.alertCircle,
      bg: 'bg-red-50',
      border: 'border-red-200',
      accent: 'border-l-red-500',
      iconBg: 'bg-red-100',
      iconColor: 'text-red-600',
      badge: 'bg-red-100 text-red-700',
      textColor: 'text-red-700',
    },
    high: {
      icon: Icons.alertCircle,
      bg: 'bg-red-50/70',
      border: 'border-red-200',
      accent: 'border-l-red-400',
      iconBg: 'bg-red-100',
      iconColor: 'text-red-500',
      badge: 'bg-red-100 text-red-600',
      textColor: 'text-red-600',
    },
    warning: {
      icon: Icons.alertTriangle,
      bg: 'bg-amber-50',
      border: 'border-amber-200',
      accent: 'border-l-amber-500',
      iconBg: 'bg-amber-100',
      iconColor: 'text-amber-600',
      badge: 'bg-amber-100 text-amber-700',
      textColor: 'text-amber-700',
    },
    medium: {
      icon: Icons.alertTriangle,
      bg: 'bg-amber-50/70',
      border: 'border-amber-200',
      accent: 'border-l-amber-400',
      iconBg: 'bg-amber-100',
      iconColor: 'text-amber-500',
      badge: 'bg-amber-100 text-amber-600',
      textColor: 'text-amber-600',
    },
    low: {
      icon: Icons.info,
      bg: 'bg-sky-50/70',
      border: 'border-sky-200',
      accent: 'border-l-sky-400',
      iconBg: 'bg-sky-100',
      iconColor: 'text-sky-500',
      badge: 'bg-sky-100 text-sky-600',
      textColor: 'text-sky-600',
    },
    info: {
      icon: Icons.info,
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      accent: 'border-l-blue-500',
      iconBg: 'bg-blue-100',
      iconColor: 'text-blue-600',
      badge: 'bg-blue-100 text-blue-700',
      textColor: 'text-blue-700',
    },
  }
  return configs[severity] || configs.info
}

const typeConfig: Record<InsightType, { label: string; icon: typeof Icons.activity }> = {
  pattern: { label: 'Pattern', icon: Icons.activity },
  anomaly: { label: 'Anomaly', icon: Icons.alertTriangle },
  recommendation: { label: 'Recommendation', icon: Icons.lightbulb },
  trend: { label: 'Trend', icon: Icons.trendingUp },
  alert: { label: 'Alert', icon: Icons.bell },
}

export function InsightCard({ insight, onAction, onDismiss }: InsightCardProps) {
  const severity = getSeverityConfig(insight.severity)
  const type = typeConfig[insight.type] || typeConfig.recommendation
  const SeverityIcon = severity.icon

  return (
    <div className={cn(
      'rounded-xl border p-4',
      'transition-all duration-200 hover:shadow-soft',
      severity.bg,
      severity.border
    )}>
      <div className="flex gap-4">
        {/* Icon */}
        <div className={cn(
          'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg',
          severity.iconBg
        )}>
          <SeverityIcon className={cn('h-5 w-5', severity.iconColor)} strokeWidth={1.5} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-semibold text-foreground">{insight.title}</h4>
                <span className={cn(
                  'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase',
                  severity.badge
                )}>
                  {insight.severity}
                </span>
                {insight.confidence && (
                  <span className="text-xs text-muted-foreground">
                    {Math.round(insight.confidence * 100)}% confident
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <type.icon className="h-3 w-3 text-muted-foreground" strokeWidth={1.5} />
                <span className="text-xs text-muted-foreground">{type.label}</span>
                <span className="text-xs text-muted-foreground">•</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(insight.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
            
            {onDismiss && (
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => onDismiss(insight.id)}
                className="text-muted-foreground hover:text-foreground"
              >
                <Icons.close className="h-4 w-4" />
              </Button>
            )}
          </div>

          <p className="mt-2 text-sm text-muted-foreground">
            {insight.description}
          </p>

          {/* Data preview */}
          {insight.data && Object.keys(insight.data).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(insight.data).slice(0, 3).map(([key, value]) => (
                <span
                  key={key}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1',
                    'bg-white/50 text-xs font-medium text-foreground'
                  )}
                >
                  <span className="text-muted-foreground">{key.replace(/_/g, ' ')}:</span>
                  <span className="font-semibold">{String(value)}</span>
                </span>
              ))}
            </div>
          )}

          {/* Suggested Action */}
          {insight.suggested_action && (
            <div className="mt-4 flex items-center gap-3">
              <Button
                variant="default"
                size="sm"
                onClick={() => onAction?.(insight)}
              >
                <Icons.zap className="mr-1.5 h-3.5 w-3.5" strokeWidth={1.5} />
                {insight.suggested_action.slice(0, 30)}
                {insight.suggested_action.length > 30 ? '...' : ''}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

