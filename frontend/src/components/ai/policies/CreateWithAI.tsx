'use client'

import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'

// ============================================================================
// Types
// ============================================================================

interface PolicyDSL {
  conditions: Array<{
    field: string
    operator: string
    value: unknown
  }>
  actions: Array<{
    type: string
    value?: unknown
    params?: Record<string, unknown>
  }>
  match_mode?: 'all' | 'any'
}

interface AnalysisResult {
  suggested_type: 'logical' | 'natural_language'
  confidence: number
  reason: string
  suggested_name: string
  summary: string
  dsl: PolicyDSL | null
  refined_instruction: string | null
  entity_name: string | null
  suggested_tags: string[]
}

interface ConflictResult {
  conflicts: Array<{ conflicting_rule_id: string; conflicting_rule_name: string; explanation: string }>
  overrides: Array<{ overridden_rule_id: string; overridden_rule_name: string; explanation: string }>
  clarifications: string[]
  suggested_instructions: string[]
  refined_instruction: string
  is_valid: boolean
  warnings?: string[]
}

interface CreateWithAIProps {
  onPolicyCreate: (policy: {
    name: string
    description: string
    naturalLanguage: string
    policyType: 'logical' | 'natural_language'
    dsl: PolicyDSL | null
    refinedInstruction: string | null
    entityName: string | null
    tags: string[]
    priority: number
  }) => Promise<void>
  onCancel?: () => void
}

// ============================================================================
// Operator Symbols
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
  between: { symbol: '↔', label: 'between' },
}

// ============================================================================
// Step Components
// ============================================================================

function StepIndicator({ currentStep, steps }: { currentStep: number; steps: string[] }) {
  return (
    <div className="flex items-center justify-center gap-2 mb-6">
      {steps.map((step, idx) => (
        <div key={step} className="flex items-center">
          <div className={cn(
            'flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold transition-all',
            idx < currentStep
              ? 'bg-emerald-500 text-white'
              : idx === currentStep
                ? 'bg-brand-cornflower text-white'
                : 'bg-gray-200 text-gray-500'
          )}>
            {idx < currentStep ? (
              <Icons.check className="h-4 w-4" />
            ) : (
              idx + 1
            )}
          </div>
          <span className={cn(
            'ml-2 text-sm font-medium hidden sm:inline',
            idx === currentStep ? 'text-brand-navy' : 'text-muted-foreground'
          )}>
            {step}
          </span>
          {idx < steps.length - 1 && (
            <div className={cn(
              'w-8 h-0.5 mx-3',
              idx < currentStep ? 'bg-emerald-500' : 'bg-gray-200'
            )} />
          )}
        </div>
      ))}
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export function CreateWithAI({ onPolicyCreate, onCancel }: CreateWithAIProps) {
  const [step, setStep] = useState(0)
  const [input, setInput] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isCheckingConflicts, setIsCheckingConflicts] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Analysis result
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  // Conflict detection result
  const [conflictResult, setConflictResult] = useState<ConflictResult | null>(null)
  const [selectedConflicts, setSelectedConflicts] = useState<Set<string>>(new Set())
  
  // Editable fields (user can override AI suggestions)
  const [policyType, setPolicyType] = useState<'logical' | 'natural_language'>('logical')
  const [policyName, setPolicyName] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')
  const [priority, setPriority] = useState(50)
  const [policyScope] = useState<'base' | 'instruction' | 'custom'>('base')
  
  const steps = ['Write Rule', 'AI Analysis', 'Conflict Check', 'Save']

  // Example policies
  const examples = [
    "Auto-approve invoices under $500 from approved vendors",
    "For vendor Acme Corp, skip GST validation and approve directly",
    "Escalate support tickets from enterprise customers to Tier 2",
    "When a new employee joins, assign the onboarding checklist",
  ]

  // ========== Step 1: Analyze ==========
  const handleAnalyze = useCallback(async () => {
    if (!input.trim()) return

    setIsAnalyzing(true)
    setError(null)

    try {
      const result = await apiClient.post<AnalysisResult>('/api/ai/policies/analyze-input', {
        input: input.trim(),
      })
      
      setAnalysis(result)
      setPolicyType(result.suggested_type)
      setPolicyName(result.suggested_name)
      setTags(result.suggested_tags)
      setStep(1)
    } catch {
      setError('Failed to analyze policy. Please try again.')
    } finally {
      setIsAnalyzing(false)
    }
  }, [input])

  // ========== Step 2: Confirm & Check Conflicts ==========
  const handleConfirmSuggestion = useCallback(async () => {
    setIsCheckingConflicts(true)
    setError(null)
    try {
      const result = await apiClient.post<ConflictResult>('/api/ai/policies/check-conflicts', {
        natural_language: input.trim(),
        policy_scope: policyScope,
        entity_name: analysis?.entity_name || null,
      })
      setConflictResult(result)
      setSelectedConflicts(new Set())
    } catch {
      setConflictResult({ conflicts: [], overrides: [], clarifications: [], suggested_instructions: [], refined_instruction: input, is_valid: true, warnings: ['Conflict check unavailable'] })
    } finally {
      setIsCheckingConflicts(false)
    }
    setStep(2)
  }, [input, policyScope, analysis])

  const handleToggleType = useCallback(() => {
    setPolicyType(prev => prev === 'logical' ? 'natural_language' : 'logical')
  }, [])

  const toggleConflict = useCallback((id: string) => {
    setSelectedConflicts(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  // ========== Step 3: Save ==========
  const handleAddTag = useCallback(() => {
    const tag = tagInput.trim().toLowerCase().replace(/[^a-z0-9-]/g, '-')
    if (tag && !tags.includes(tag)) {
      setTags(prev => [...prev, tag])
    }
    setTagInput('')
  }, [tagInput, tags])

  const handleRemoveTag = useCallback((tagToRemove: string) => {
    setTags(prev => prev.filter(t => t !== tagToRemove))
  }, [])

  const handleConfirmConflicts = useCallback(() => {
    setStep(3)
  }, [])

  const handleSave = useCallback(async () => {
    if (!policyName.trim() || !input.trim()) return

    setIsSaving(true)
    setError(null)

    try {
      await onPolicyCreate({
        name: policyName.trim(),
        description: description.trim(),
        naturalLanguage: input.trim(),
        policyType,
        dsl: policyType === 'logical' ? analysis?.dsl || null : null,
        refinedInstruction: policyType === 'natural_language' ? (conflictResult?.refined_instruction || analysis?.refined_instruction || null) : null,
        entityName: analysis?.entity_name || null,
        tags,
        priority,
      })
    } catch {
      setError('Failed to save policy. Please try again.')
      setIsSaving(false)
    }
  }, [policyName, description, input, policyType, analysis, conflictResult, tags, priority, onPolicyCreate])

  const handleBack = useCallback(() => {
    if (step > 0) setStep(step - 1)
  }, [step])

  // ========== Format Helpers ==========
  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return ''
    if (typeof value === 'number') return value >= 100 ? `$${value.toLocaleString()}` : String(value)
    if (Array.isArray(value)) return value.join(', ')
    return String(value)
  }

  return (
    <div className="w-full max-w-3xl mx-auto">
      <StepIndicator currentStep={step} steps={steps} />

      <AnimatePresence mode="wait">
        {/* ========== Step 1: Write Rule ========== */}
        {step === 0 && (
          <motion.div
            key="step-1"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            className="space-y-6"
          >
            <div className="text-center mb-6">
              <h2 className="text-xl font-bold text-brand-navy">Describe Your Policy</h2>
              <p className="text-muted-foreground mt-1">
                Write your business rule in plain English. Our AI will analyze it.
              </p>
            </div>

            <div className="bg-white/95 backdrop-blur-sm rounded-xl border border-gray-200 p-6 shadow-lg">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Example: If an invoice is under $500 and from an approved vendor, auto-approve it without manual review..."
                className={cn(
                  'w-full min-h-[180px] rounded-lg border-0 bg-gray-50 p-4',
                  'text-base text-foreground placeholder:text-muted-foreground',
                  'resize-none focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50',
                  'transition-all duration-200'
                )}
              />

              {error && (
                <div className="flex items-center gap-2 mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                  <Icons.alertCircle className="h-4 w-4 flex-shrink-0" />
                  {error}
                </div>
              )}

              <div className="flex items-center gap-3 mt-4">
                <Button
                  onClick={handleAnalyze}
                  disabled={!input.trim() || isAnalyzing}
                  variant="gradient"
                  className="flex-1"
                  size="lg"
                >
                  {isAnalyzing ? (
                    <>
                      <Icons.loader className="mr-2 h-5 w-5 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <Icons.sparkles className="mr-2 h-5 w-5" />
                      Analyze with AI
                    </>
                  )}
                </Button>
                {onCancel && (
                  <Button variant="ghost" onClick={onCancel}>
                    Cancel
                  </Button>
                )}
              </div>
            </div>

            {/* Examples */}
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
                Try an example
              </p>
              <div className="flex flex-wrap gap-2">
                {examples.map((example, idx) => (
                  <button
                    key={idx}
                    onClick={() => setInput(example)}
                    className={cn(
                      'text-sm text-left px-3 py-2 rounded-lg',
                      'bg-white border border-gray-200 text-gray-700',
                      'hover:border-brand-cornflower hover:bg-brand-cornflower/5 transition-colors',
                      'max-w-full'
                    )}
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* ========== Step 2: AI Suggestion ========== */}
        {step === 1 && analysis && (
          <motion.div
            key="step-2"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            className="space-y-6"
          >
            <div className="text-center mb-6">
              <h2 className="text-xl font-bold text-brand-navy">AI Suggestion</h2>
              <p className="text-muted-foreground mt-1">
                Review what the AI detected. You can edit or change the type.
              </p>
            </div>

            {/* Confidence Badge */}
            <div className="flex items-center justify-center gap-2">
              <span className={cn(
                'px-3 py-1 rounded-full text-sm font-medium',
                analysis.confidence >= 0.8
                  ? 'bg-emerald-100 text-emerald-700'
                  : analysis.confidence >= 0.6
                    ? 'bg-amber-100 text-amber-700'
                    : 'bg-gray-100 text-gray-700'
              )}>
                {Math.round(analysis.confidence * 100)}% confidence
              </span>
              <span className="text-sm text-muted-foreground">
                {analysis.reason}
              </span>
            </div>

            {/* Type Toggle */}
            <div className="bg-white/95 backdrop-blur-sm rounded-xl border border-gray-200 p-6 shadow-lg">
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-medium text-gray-700">Policy Type</span>
                <button
                  onClick={handleToggleType}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-all',
                    policyType === 'logical'
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-purple-500 bg-purple-50 text-purple-700'
                  )}
                >
                  {policyType === 'logical' ? (
                    <>
                      <Icons.grid className="h-4 w-4" />
                      <span className="font-semibold">Structured Rules</span>
                    </>
                  ) : (
                    <>
                      <Icons.brain className="h-4 w-4" />
                      <span className="font-semibold">Natural Language</span>
                    </>
                  )}
                  <Icons.refresh className="h-3.5 w-3.5 ml-2 opacity-50" />
                </button>
              </div>

              {/* What AI detected */}
              {policyType === 'logical' && analysis.dsl ? (
                <div className="space-y-4">
                  {/* Conditions */}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 mb-2">
                      Conditions ({analysis.dsl.match_mode === 'any' ? 'Match ANY' : 'Match ALL'})
                    </p>
                    <div className="space-y-2">
                      {analysis.dsl.conditions.map((cond, idx) => {
                        const opInfo = OPERATOR_SYMBOLS[cond.operator] || { symbol: cond.operator, label: cond.operator }
                        return (
                          <div key={idx} className="flex items-center gap-3 p-3 rounded-lg bg-blue-50 border border-blue-100">
                            <span className="w-6 h-6 rounded bg-blue-200 text-blue-700 flex items-center justify-center text-xs font-bold">
                              {idx + 1}
                            </span>
                            <span className="font-medium text-blue-900">
                              {cond.field.replace(/_/g, ' ')}
                            </span>
                            <span className="text-blue-500 text-lg font-mono">{opInfo.symbol}</span>
                            <span className="font-mono text-blue-800">{formatValue(cond.value)}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  {/* Actions */}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-emerald-600 mb-2">
                      Then Perform
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {analysis.dsl.actions.map((action, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-100 text-emerald-700"
                        >
                          <Icons.zap className="h-4 w-4" />
                          <span className="font-medium">
                            {action.type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                          </span>
                          {action.value != null && (
                            <span className="text-emerald-600">: {String(action.value as string).slice(0, 30)}</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-purple-600 mb-2">
                    AI-Refined Instruction
                  </p>
                  <div className="p-4 rounded-lg bg-purple-50 border border-purple-100">
                    <p className="text-purple-800">
                      {analysis.refined_instruction || input}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Suggested Name */}
            <div className="bg-white/95 backdrop-blur-sm rounded-xl border border-gray-200 p-4 shadow-lg">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Suggested Name
              </label>
              <input
                type="text"
                value={policyName}
                onChange={(e) => setPolicyName(e.target.value)}
                className="w-full px-4 py-2 rounded-lg border border-gray-200 text-base focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50"
              />
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-3">
              <Button variant="ghost" onClick={handleBack}>
                <Icons.arrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              <Button
                onClick={handleConfirmSuggestion}
                disabled={isCheckingConflicts}
                variant="gradient"
                className="flex-1"
                size="lg"
              >
                {isCheckingConflicts ? (
                  <>
                    <Icons.loader className="mr-2 h-5 w-5 animate-spin" />
                    Checking Conflicts...
                  </>
                ) : (
                  <>
                    Check Conflicts
                    <Icons.arrowRight className="ml-2 h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </motion.div>
        )}

        {/* ========== Step 3: Conflict Check ========== */}
        {step === 2 && conflictResult && (
          <motion.div
            key="step-conflict"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            className="space-y-6"
          >
            <div className="text-center mb-6">
              <h2 className="text-xl font-bold text-brand-navy">Conflict Analysis</h2>
              <p className="text-muted-foreground mt-1">
                Review any conflicts or overrides with existing policies.
              </p>
            </div>

            {/* No conflicts */}
            {conflictResult.conflicts.length === 0 && conflictResult.overrides.length === 0 && conflictResult.clarifications.length === 0 && (
              <div className="p-6 bg-emerald-50 border border-emerald-200 rounded-xl text-center">
                <Icons.check className="h-10 w-10 text-emerald-500 mx-auto mb-3" />
                <h3 className="font-semibold text-emerald-800">No Conflicts Detected</h3>
                <p className="text-sm text-emerald-600 mt-1">This policy is compatible with all existing rules.</p>
              </div>
            )}

            {/* Overrides */}
            {conflictResult.overrides.length > 0 && (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
                <div className="flex items-start gap-3">
                  <Icons.check className="h-5 w-5 text-emerald-600 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-emerald-800">Override Notice</h4>
                    <p className="text-sm text-emerald-700 mt-1">This INSTRUCTION rule will override BASE rules for the specified entity.</p>
                    <ul className="mt-2 space-y-1">
                      {conflictResult.overrides.map((o, i) => (
                        <li key={i} className="text-sm text-emerald-600">• Overrides: <span className="font-medium">{o.overridden_rule_name}</span></li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* Conflicts */}
            {conflictResult.conflicts.length > 0 && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-xl">
                <div className="flex items-start gap-3">
                  <Icons.alertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                  <div className="flex-1">
                    <h4 className="font-semibold text-red-800">Conflicts Detected</h4>
                    <p className="text-sm text-red-700 mt-1">Select conflicting rules to deactivate:</p>
                    <div className="mt-3 space-y-2">
                      {conflictResult.conflicts.map((c) => (
                        <label key={c.conflicting_rule_id} className={cn(
                          'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                          selectedConflicts.has(c.conflicting_rule_id) ? 'bg-red-100 border-red-300' : 'bg-white border-red-100 hover:bg-red-50'
                        )}>
                          <input type="checkbox" checked={selectedConflicts.has(c.conflicting_rule_id)} onChange={() => toggleConflict(c.conflicting_rule_id)} className="mt-0.5 h-4 w-4 rounded border-red-300 text-red-600" />
                          <div>
                            <span className="font-medium text-red-800">{c.conflicting_rule_name}</span>
                            <p className="text-xs text-red-600 mt-0.5">{c.explanation}</p>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Clarifications */}
            {conflictResult.clarifications.length > 0 && (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
                <div className="flex items-start gap-3">
                  <Icons.info className="h-5 w-5 text-amber-600 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-amber-800">AI Suggestions</h4>
                    <ul className="mt-2 space-y-1">
                      {conflictResult.clarifications.map((q, i) => (
                        <li key={i} className="text-sm text-amber-700">• {q}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* Warnings */}
            {conflictResult.warnings && conflictResult.warnings.length > 0 && (
              <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
                <p className="text-xs text-muted-foreground">{conflictResult.warnings.join(', ')}</p>
              </div>
            )}

            <div className="flex items-center gap-3">
              <Button variant="ghost" onClick={handleBack}>
                <Icons.arrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              <Button onClick={handleConfirmConflicts} variant="gradient" className="flex-1" size="lg">
                Continue to Save
                <Icons.arrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </motion.div>
        )}

        {/* ========== Step 4: Details & Save ========== */}
        {step === 3 && (
          <motion.div
            key="step-3"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            className="space-y-6"
          >
            <div className="text-center mb-6">
              <h2 className="text-xl font-bold text-brand-navy">Final Details</h2>
              <p className="text-muted-foreground mt-1">
                Add any additional details and save your policy.
              </p>
            </div>

            <div className="bg-white/95 backdrop-blur-sm rounded-xl border border-gray-200 p-6 shadow-lg space-y-5">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Policy Name *
                </label>
                <input
                  type="text"
                  value={policyName}
                  onChange={(e) => setPolicyName(e.target.value)}
                  placeholder="e.g., Auto-Approve Low Value Invoices"
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-200 text-base focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Description (optional)
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief description of what this policy does..."
                  rows={2}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-200 text-base resize-none focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50"
                />
              </div>

              {/* Priority */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Priority (lower = runs first)
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="1"
                    max="100"
                    value={priority}
                    onChange={(e) => setPriority(parseInt(e.target.value))}
                    className="flex-1"
                  />
                  <span className="w-12 text-center text-sm font-mono bg-gray-100 px-2 py-1 rounded">
                    {priority}
                  </span>
                </div>
              </div>

              {/* Tags */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Tags
                </label>
                <div className="flex items-center gap-2 mb-2">
                  <input
                    type="text"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                    placeholder="Add a tag"
                    className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50"
                  />
                  <Button variant="outline" size="sm" onClick={handleAddTag}>
                    Add
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-gray-100 text-sm"
                    >
                      #{tag}
                      <button
                        onClick={() => handleRemoveTag(tag)}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        <Icons.close className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                <Icons.alertCircle className="h-4 w-4 flex-shrink-0" />
                {error}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center gap-3">
              <Button variant="ghost" onClick={handleBack}>
                <Icons.arrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              <Button
                onClick={handleSave}
                disabled={!policyName.trim() || isSaving}
                variant="gradient"
                className="flex-1"
                size="lg"
              >
                {isSaving ? (
                  <>
                    <Icons.loader className="mr-2 h-5 w-5 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Icons.check className="mr-2 h-5 w-5" />
                    Save Policy
                  </>
                )}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

