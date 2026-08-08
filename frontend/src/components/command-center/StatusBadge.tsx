import { cn } from '@/lib/utils'

const tones: Record<string, string> = {
  healthy: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  completed: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  approved: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  allow: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  running: 'border-blue-200 bg-blue-50 text-blue-700',
  executing: 'border-blue-200 bg-blue-50 text-blue-700',
  open: 'border-amber-200 bg-amber-50 text-amber-700',
  review: 'border-amber-200 bg-amber-50 text-amber-700',
  awaiting_approval: 'border-amber-200 bg-amber-50 text-amber-700',
  escalated: 'border-amber-200 bg-amber-50 text-amber-700',
  degraded: 'border-amber-200 bg-amber-50 text-amber-700',
  critical: 'border-red-200 bg-red-50 text-red-700',
  failed: 'border-red-200 bg-red-50 text-red-700',
  rejected: 'border-red-200 bg-red-50 text-red-700',
  block: 'border-red-200 bg-red-50 text-red-700',
  disconnected: 'border-red-200 bg-red-50 text-red-700',
}

interface StatusBadgeProps {
  value: string
  label?: string
  className?: string
}

export function StatusBadge({ value, label, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold',
        tones[value] ?? 'border-slate-200 bg-slate-50 text-slate-700',
        className
      )}
    >
      {label ?? value.replaceAll('_', ' ')}
    </span>
  )
}
