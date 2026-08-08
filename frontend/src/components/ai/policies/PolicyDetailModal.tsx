'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import type { Policy } from './PolicyCard'

// ============================================================================
// Types
// ============================================================================

interface PolicyDetailModalProps {
  policy: Policy | null
  isOpen: boolean
  onClose: () => void
  onEdit: (policy: Policy) => void
  onToggleStatus: (id: string, isActive: boolean) => void
  onDelete: (id: string) => void
}

// ============================================================================
// Operator Symbol Map
// ============================================================================

const OPERATOR_SYMBOLS: Record<string, { symbol: string; label: string }> = {
  eq: { symbol: '=', label: 'equals' },
  neq: { symbol: '≠', label: 'not equals' },
  gt: { symbol: '>', label: 'greater than' },
  lt: { symbol: '<', label: 'less than' },
  gte: { symbol: '≥', label: 'at least' },
  lte: { symbol: '≤', label: 'at most' },
  in: { symbol: '∈', label: 'in list' },
  not_in: { symbol: '∉', label: 'not in list' },
  contains: { symbol: '⊃', label: 'contains' },
  not_contains: { symbol: '⊅', label: 'not contains' },
  starts_with: { symbol: '^', label: 'starts with' },
  ends_with: { symbol: '$', label: 'ends with' },
  matches: { symbol: '~', label: 'matches' },
  is_null: { symbol: '∅', label: 'is empty' },
  is_not_null: { symbol: '≢∅', label: 'is not empty' },
  between: { symbol: '↔', label: 'between' },
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

const formatDateTime = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
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
    return value.join(', ')
  }
  return String(value)
}

const formatActionType = (type: string): string => {
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

// ============================================================================
// Animation Variants
// ============================================================================

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.2 } },
  exit: { opacity: 0, transition: { duration: 0.15 } },
}

const modalVariants = {
  hidden: { opacity: 0, scale: 0.92, y: 30 },
  visible: { 
    opacity: 1, 
    scale: 1, 
    y: 0,
    transition: { 
      type: 'spring',
      stiffness: 400,
      damping: 30,
      mass: 0.8
    }
  },
  exit: { 
    opacity: 0, 
    scale: 0.95, 
    y: 20,
    transition: { duration: 0.15 }
  },
}

const contentVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.05, delayChildren: 0.1 }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0 }
}

// ============================================================================
// Component
// ============================================================================

export function PolicyDetailModal({
  policy,
  isOpen,
  onClose,
  onEdit,
  onToggleStatus,
  onDelete,
}: PolicyDetailModalProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (isOpen) {
      window.addEventListener('keydown', handleEscape)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      window.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = ''
    }
  }, [isOpen, onClose])

  // Reset delete confirm when modal closes
  useEffect(() => {
    if (!isOpen) {
      setShowDeleteConfirm(false)
    }
  }, [isOpen])

  const handleDelete = useCallback(() => {
    if (!policy) return
    if (showDeleteConfirm) {
      onDelete(policy.id)
      onClose()
    } else {
      setShowDeleteConfirm(true)
      setTimeout(() => setShowDeleteConfirm(false), 3000)
    }
  }, [showDeleteConfirm, onDelete, policy, onClose])

  const handleEdit = useCallback(() => {
    if (policy) {
      onEdit(policy)
      onClose()
    }
  }, [policy, onEdit, onClose])

  if (!mounted) return null

  const isLogical = policy?.policy_type === 'logical'

  const modalContent = (
    <AnimatePresence mode="wait">
      {isOpen && policy && (
        <motion.div
          key="modal-overlay"
          className="fixed inset-0 flex items-center justify-center p-4"
          style={{
            zIndex: 9999,
            backgroundColor: 'rgba(26, 35, 64, 0.6)',
            backdropFilter: 'blur(8px)',
          }}
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={onClose}
        >
          <motion.div
            key="modal-content"
            className="relative w-full max-w-2xl max-h-[85vh] bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col"
            variants={modalVariants}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <motion.div 
              className="flex items-start justify-between px-6 py-5 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <div className="flex-1 pr-4">
                <h2 className="text-xl font-semibold text-brand-navy mb-2">
                  {policy.name}
                </h2>
                <div className="flex flex-wrap items-center gap-2">
                  {/* Type Badge */}
                  <motion.span 
                    className={cn(
                      'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold',
                      isLogical
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-purple-100 text-purple-700'
                    )}
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.15 }}
                  >
                    {isLogical ? (
                      <>
                        <Icons.grid className="h-3 w-3" />
                        Structured
                      </>
                    ) : (
                      <>
                        <Icons.brain className="h-3 w-3" />
                        Natural Language
                      </>
                    )}
                  </motion.span>
                  
                  {/* Status Badge */}
                  <motion.span 
                    className={cn(
                      'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold',
                      policy.is_active
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-gray-100 text-gray-600'
                    )}
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.2 }}
                  >
                    {policy.is_active ? (
                      <>
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Active
                      </>
                    ) : (
                      <>
                        <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
                        Inactive
                      </>
                    )}
                  </motion.span>

                  {/* Tags */}
                  {policy.tags.slice(0, 3).map((tag, idx) => (
                    <motion.span
                      key={tag}
                      className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600"
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ delay: 0.25 + idx * 0.05 }}
                    >
                      #{tag}
                    </motion.span>
                  ))}
                  {policy.tags.length > 3 && (
                    <span className="text-xs text-muted-foreground">
                      +{policy.tags.length - 3} more
                    </span>
                  )}
                </div>
              </div>
              <motion.div
                whileHover={{ scale: 1.1, rotate: 90 }}
                whileTap={{ scale: 0.9 }}
                transition={{ type: 'spring', stiffness: 400 }}
              >
                <Button variant="ghost" size="icon" onClick={onClose} className="flex-shrink-0">
                  <Icons.close className="h-5 w-5" />
                </Button>
              </motion.div>
            </motion.div>

            {/* Content */}
            <motion.div 
              className="flex-1 overflow-y-auto p-6 space-y-6"
              variants={contentVariants}
              initial="hidden"
              animate="visible"
            >
              {/* Original User Input */}
              <motion.div variants={itemVariants}>
                <div className="flex items-center gap-2 mb-3">
                  <div className="p-1.5 rounded-lg bg-gray-100">
                    <Icons.user className="h-4 w-4 text-gray-600" />
                  </div>
                  <span className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                    Original Input
                  </span>
                </div>
                <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 hover:border-gray-300 transition-colors">
                  <p className="text-sm text-gray-700 leading-relaxed italic">
                    &ldquo;{policy.natural_language}&rdquo;
                  </p>
                </div>
              </motion.div>

              {/* AI Processing - Structured Rules or Natural Language */}
              <motion.div variants={itemVariants}>
                <div className="flex items-center gap-2 mb-3">
                  <div className={cn(
                    'p-1.5 rounded-lg',
                    isLogical ? 'bg-blue-100' : 'bg-purple-100'
                  )}>
                    <Icons.sparkles className={cn(
                      'h-4 w-4',
                      isLogical ? 'text-blue-600' : 'text-purple-600'
                    )} />
                  </div>
                  <span className={cn(
                    'text-sm font-semibold uppercase tracking-wide',
                    isLogical ? 'text-blue-700' : 'text-purple-700'
                  )}>
                    {isLogical ? 'Structured Rules' : 'AI Instruction'}
                  </span>
                </div>

                {isLogical && policy.dsl ? (
                  <div className="bg-blue-50 rounded-xl border border-blue-100 p-4 space-y-4">
                    {/* Conditions */}
                    <div>
                      <p className="text-xs font-semibold text-blue-700 mb-3 uppercase tracking-wide">
                        Conditions ({policy.dsl.match_mode === 'any' ? 'Match ANY' : 'Match ALL'})
                      </p>
                      <div className="space-y-2">
                        {policy.dsl.conditions.map((cond, idx) => {
                          const opInfo = OPERATOR_SYMBOLS[cond.operator] || { symbol: cond.operator }
                          return (
                            <motion.div
                              key={idx}
                              className="flex items-center gap-3 p-2.5 bg-white rounded-lg border border-blue-100 hover:border-blue-200 hover:shadow-sm transition-all"
                              initial={{ opacity: 0, x: -10 }}
                              animate={{ opacity: 1, x: 0 }}
                              transition={{ delay: idx * 0.05 }}
                            >
                              <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
                                {idx + 1}
                              </span>
                              <code className="text-sm font-mono text-blue-800 flex-1">
                                <span className="font-medium">{cond.field.replace(/_/g, ' ')}</span>
                                <span className="mx-2 text-blue-500">{opInfo.symbol}</span>
                                <span className="text-blue-700">{formatValue(cond.value)}</span>
                              </code>
                            </motion.div>
                          )
                        })}
                      </div>
                    </div>

                    {/* Actions */}
                    <div>
                      <p className="text-xs font-semibold text-emerald-700 mb-3 uppercase tracking-wide">
                        Then Perform
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {policy.dsl.actions.map((action, idx) => (
                          <motion.span
                            key={idx}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-emerald-100 text-emerald-700 border border-emerald-200 hover:bg-emerald-150 transition-colors"
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: idx * 0.05 }}
                            whileHover={{ scale: 1.02 }}
                          >
                            <Icons.check className="h-3.5 w-3.5" />
                            <span className="font-medium">{formatActionType(action.type)}</span>
                            {action.value != null && (
                              <span className="text-emerald-600">: {String(action.value).slice(0, 30)}</span>
                            )}
                          </motion.span>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="bg-purple-50 rounded-xl border border-purple-100 p-4 hover:border-purple-200 transition-colors">
                    <p className="text-sm text-purple-800 leading-relaxed">
                      {policy.refined_instruction || policy.ai_instruction || policy.natural_language}
                    </p>
                  </div>
                )}
              </motion.div>

              {/* Metadata */}
              {(policy.entity_name || policy.description) && (
                <motion.div variants={itemVariants}>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="p-1.5 rounded-lg bg-amber-100">
                      <Icons.info className="h-4 w-4 text-amber-600" />
                    </div>
                    <span className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                      Details
                    </span>
                  </div>
                  <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 space-y-2">
                    {policy.description && (
                      <p className="text-sm text-gray-600">{policy.description}</p>
                    )}
                    {policy.entity_name && (
                      <div className="flex items-center gap-2">
                        <Icons.building className="h-4 w-4 text-amber-600" />
                        <span className="text-sm font-medium text-amber-700">
                          Entity: {policy.entity_name}
                        </span>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}

              {/* Stats */}
              <motion.div 
                className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-100"
                variants={itemVariants}
              >
                <motion.div 
                  className="text-center p-3 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
                  whileHover={{ scale: 1.02 }}
                >
                  <p className="text-2xl font-bold text-brand-navy">{policy.execution_count}</p>
                  <p className="text-xs text-muted-foreground">Executions</p>
                </motion.div>
                <motion.div 
                  className="text-center p-3 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
                  whileHover={{ scale: 1.02 }}
                >
                  <p className="text-lg font-bold text-brand-navy">{policy.priority}</p>
                  <p className="text-xs text-muted-foreground">Priority</p>
                </motion.div>
                <motion.div 
                  className="text-center p-3 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
                  whileHover={{ scale: 1.02 }}
                >
                  <p className="text-sm font-medium text-brand-navy">{formatDate(policy.created_at)}</p>
                  <p className="text-xs text-muted-foreground">Created</p>
                </motion.div>
              </motion.div>

              {/* Last Executed */}
              {policy.last_executed_at && (
                <motion.div 
                  className="flex items-center gap-2 text-sm text-muted-foreground"
                  variants={itemVariants}
                >
                  <Icons.clock className="h-4 w-4" />
                  <span>Last executed: {formatDateTime(policy.last_executed_at)}</span>
                </motion.div>
              )}
            </motion.div>

            {/* Footer Actions */}
            <motion.div 
              className="flex items-center justify-between px-6 py-4 border-t border-gray-100 bg-gray-50"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <div className="flex items-center gap-2">
                <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onToggleStatus(policy.id, policy.is_active)}
                    className={cn(
                      'transition-colors',
                      policy.is_active
                        ? 'text-amber-600 hover:text-amber-700 hover:bg-amber-50 hover:border-amber-200'
                        : 'text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 hover:border-emerald-200'
                    )}
                  >
                    {policy.is_active ? (
                      <>
                        <Icons.eyeOff className="h-4 w-4 mr-1.5" />
                        Disable
                      </>
                    ) : (
                      <>
                        <Icons.eye className="h-4 w-4 mr-1.5" />
                        Enable
                      </>
                    )}
                  </Button>
                </motion.div>
                <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDelete}
                    className={cn(
                      'transition-all',
                      showDeleteConfirm
                        ? 'text-white bg-red-500 hover:bg-red-600 border-red-500'
                        : 'text-red-600 hover:text-red-700 hover:bg-red-50 hover:border-red-200'
                    )}
                  >
                    <Icons.trash className="h-4 w-4 mr-1.5" />
                    {showDeleteConfirm ? 'Confirm Delete' : 'Delete'}
                  </Button>
                </motion.div>
              </div>
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                <Button variant="gradient" size="sm" onClick={handleEdit}>
                  <Icons.pencil className="h-4 w-4 mr-1.5" />
                  Edit Policy
                </Button>
              </motion.div>
            </motion.div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )

  return createPortal(modalContent, document.body)
}
