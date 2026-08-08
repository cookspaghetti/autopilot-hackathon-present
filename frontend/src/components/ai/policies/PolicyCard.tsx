'use client'

import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Icons } from '@/components/ui/icons'

// ============================================================================
// Types
// ============================================================================

export interface PolicyCondition {
  field: string
  operator: string
  value: unknown
}

export interface PolicyAction {
  type: string
  value?: unknown
  params?: Record<string, unknown>
}

export interface PolicyDSL {
  conditions: PolicyCondition[]
  actions: PolicyAction[]
  match_mode?: 'all' | 'any'
  stop_on_match?: boolean
}

export interface Policy {
  id: string
  name: string
  description: string
  summary: string | null
  natural_language: string
  policy_type: 'logical' | 'natural_language'
  policy_scope?: 'base' | 'instruction' | 'custom'
  dsl: PolicyDSL | null
  refined_instruction: string | null
  ai_instruction: string | null
  entity_name: string | null
  is_active: boolean
  priority: number
  tags: string[]
  source?: string
  created_at: string
  updated_at: string
  execution_count: number
  last_executed_at: string | null
}

interface PolicyCardProps {
  policy: Policy
  onClick: (policy: Policy) => void
}

// ============================================================================
// Operator Symbol Map
// ============================================================================

const OPERATOR_SYMBOLS: Record<string, { symbol: string }> = {
  eq: { symbol: '=' },
  neq: { symbol: '≠' },
  gt: { symbol: '>' },
  lt: { symbol: '<' },
  gte: { symbol: '≥' },
  lte: { symbol: '≤' },
  in: { symbol: '∈' },
  not_in: { symbol: '∉' },
  contains: { symbol: '⊃' },
}

// ============================================================================
// Helpers
// ============================================================================

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') {
    if (value >= 100) return `$${value.toLocaleString()}`
    return String(value)
  }
  if (Array.isArray(value)) {
    if (value.length <= 2) return value.join(', ')
    return `${value.slice(0, 2).join(', ')}...`
  }
  return String(value)
}

const formatActionType = (type: string): string => {
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

// ============================================================================
// Main Component - Fixed Height Card with Animations
// ============================================================================

export function PolicyCard({ policy, onClick }: PolicyCardProps) {
  const isLogical = policy.policy_type === 'logical'
  const displaySummary = policy.summary || policy.description || policy.natural_language.slice(0, 100)

  // Get up to 2 conditions and 2 actions for chips
  const topConditions = policy.dsl?.conditions?.slice(0, 2) || []
  const topActions = policy.dsl?.actions?.slice(0, 2) || []
  const moreCount = 
    Math.max(0, (policy.dsl?.conditions?.length || 0) - 2) +
    Math.max(0, (policy.dsl?.actions?.length || 0) - 2)

  return (
    <motion.div
      onClick={() => onClick(policy)}
      className={cn(
        'relative h-[200px] rounded-xl border cursor-pointer',
        'bg-white',
        'flex flex-col group',
        !policy.is_active && 'opacity-60'
      )}
      whileHover={{ 
        y: -4, 
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05)',
        borderColor: 'rgba(156, 163, 175, 0.5)'
      }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
    >
      {/* Subtle gradient overlay on hover */}
      <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-transparent to-gray-50/50 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
      
      {/* Header */}
      <div className="relative flex items-start justify-between gap-2 p-4 pb-2">
        <div className="flex items-start gap-2 flex-1 min-w-0">
          {/* Status Dot with pulse animation for active */}
          <div className="relative mt-1.5 flex-shrink-0">
            <div className={cn(
              'h-2.5 w-2.5 rounded-full',
              policy.is_active ? 'bg-emerald-500' : 'bg-gray-300'
            )} />
            {policy.is_active && (
              <div className="absolute inset-0 h-2.5 w-2.5 rounded-full bg-emerald-500 animate-ping opacity-40" />
            )}
          </div>
          
          {/* Name */}
          <h3 className="font-semibold text-brand-navy line-clamp-1 text-sm group-hover:text-brand-cornflower transition-colors duration-200">
            {policy.name}
          </h3>
        </div>
        
        {/* Type Badge */}
        <motion.div 
          className={cn(
            'flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase flex-shrink-0',
            isLogical
              ? 'bg-blue-100 text-blue-700'
              : 'bg-purple-100 text-purple-700'
          )}
          whileHover={{ scale: 1.05 }}
        >
          {isLogical ? (
            <>
              <Icons.grid className="h-3 w-3" />
              Structured
            </>
          ) : (
            <>
              <Icons.brain className="h-3 w-3" />
              Natural
            </>
          )}
        </motion.div>
      </div>
      
      {/* Summary - Fixed 2 lines */}
      <div className="relative px-4 pb-2 flex-shrink-0">
        <p className="text-sm text-muted-foreground line-clamp-2 h-[40px]">
          {displaySummary}
        </p>
      </div>
      
      {/* Chips Row - Conditional based on type */}
      <div className="relative px-4 pb-2 flex-1 min-h-0 overflow-hidden">
        {isLogical && (topConditions.length > 0 || topActions.length > 0) ? (
          <div className="flex flex-wrap gap-1.5">
            {topConditions.map((cond, idx) => {
              const opInfo = OPERATOR_SYMBOLS[cond.operator] || { symbol: cond.operator }
              return (
                <span
                  key={`cond-${idx}`}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-blue-50 text-blue-700 border border-blue-100"
                >
                  <span className="font-medium">{cond.field.replace(/_/g, ' ')}</span>
                  <span className="text-blue-500">{opInfo.symbol}</span>
                  <span className="font-mono">{formatValue(cond.value)}</span>
                </span>
              )
            })}
            {topActions.map((action, idx) => (
              <span
                key={`action-${idx}`}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-emerald-50 text-emerald-700 border border-emerald-100"
              >
                <Icons.zap className="h-2.5 w-2.5" />
                <span>{formatActionType(action.type)}</span>
              </span>
            ))}
            {moreCount > 0 && (
              <span className="text-[11px] text-muted-foreground px-1.5 py-0.5">
                +{moreCount} more
              </span>
            )}
          </div>
        ) : !isLogical ? (
          <div className="flex items-center gap-1.5">
            <Icons.sparkles className="h-3.5 w-3.5 text-purple-500" />
            <span className="text-xs text-purple-600 font-medium">AI-refined instruction</span>
          </div>
        ) : null}
      </div>
      
      {/* Footer - Fixed at bottom */}
      <div className="relative flex items-center justify-between px-4 py-3 border-t border-gray-100 mt-auto bg-gray-50/50 rounded-b-xl">
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>{formatDate(policy.created_at)}</span>
          {policy.execution_count > 0 && (
            <span className="flex items-center gap-1">
              <Icons.activity className="h-3 w-3" />
              {policy.execution_count}
            </span>
          )}
        </div>
        
        {/* Click hint with animation */}
        <motion.div 
          className="flex items-center gap-1 text-xs text-muted-foreground group-hover:text-brand-cornflower transition-colors duration-200"
          initial={{ x: 0 }}
          whileHover={{ x: 2 }}
        >
          <span>View</span>
          <Icons.chevronRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform duration-200" />
        </motion.div>
      </div>
    </motion.div>
  )
}
