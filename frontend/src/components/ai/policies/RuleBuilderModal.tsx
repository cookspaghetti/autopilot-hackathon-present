'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

// ============================================================================
// Types
// ============================================================================

export interface RuleFormData {
  name: string
  description: string
  naturalLanguage: string
  policyType: 'BASE' | 'INSTRUCTION'
  entityName?: string
  priority: number
  tags: string[]
}

export interface RuleConflict {
  conflicting_rule_id: string
  conflicting_rule_name: string
  explanation: string
}

export interface RuleOverride {
  overridden_rule_id: string
  overridden_rule_name: string
  explanation: string
}

export interface RuleAnalysis {
  conflicts: RuleConflict[]
  overrides: RuleOverride[]
  clarifications: string[]
  suggested_instructions: string[]
  refined_instruction: string
  is_valid: boolean
  warnings?: string[]
}

interface RuleBuilderModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (data: RuleFormData & { refined_instruction: string; conflict_resolution?: { deactivate_ids: string[] } }) => Promise<void>
  initialData?: Partial<RuleFormData>
  entityName?: string
  existingRuleIds?: string[]
}

// ============================================================================
// Analysis Steps Animation
// ============================================================================

const analysisSteps = [
  { text: 'Parsing your rule intent...', icon: Icons.fileText, delay: 0 },
  { text: 'Comparing against existing policies...', icon: Icons.sparkles, delay: 0.5 },
  { text: 'Checking for logical conflicts...', icon: Icons.alertTriangle, delay: 1.0 },
  { text: 'Generating refined instructions...', icon: Icons.bot, delay: 1.5 },
]

function AnalyzingState({ currentStep }: { currentStep: number }) {
  return (
    <div className="p-6 bg-gradient-to-br from-brand-navy/5 to-brand-purple/5 rounded-xl border border-brand-navy/10">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-navy to-brand-purple shadow-soft">
          <Icons.brain className="h-5 w-5 text-white animate-pulse" strokeWidth={1.5} />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-brand-navy">AutoPilot AI is analyzing...</h3>
          <p className="text-sm text-muted-foreground">Please wait while we process your rule</p>
        </div>
      </div>
      
      <div className="space-y-3 mt-6">
        {analysisSteps.map((step, index) => {
          const Icon = step.icon
          const isComplete = index < currentStep
          const isCurrent = index === currentStep
          
          return (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: step.delay, duration: 0.3 }}
              className={cn(
                'flex items-center gap-3 p-3 rounded-lg transition-colors',
                isComplete && 'bg-emerald-50',
                isCurrent && 'bg-brand-cornflower/10',
              )}
            >
              <div className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full',
                isComplete && 'bg-emerald-100',
                isCurrent && 'bg-brand-cornflower/20',
                !isComplete && !isCurrent && 'bg-muted'
              )}>
                {isComplete ? (
                  <Icons.check className="h-4 w-4 text-emerald-600" strokeWidth={2} />
                ) : isCurrent ? (
                  <Icons.loader className="h-4 w-4 text-brand-cornflower animate-spin" strokeWidth={2} />
                ) : (
                  <Icon className="h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
                )}
              </div>
              <span className={cn(
                'text-sm font-medium',
                isComplete && 'text-emerald-700',
                isCurrent && 'text-brand-navy',
                !isComplete && !isCurrent && 'text-muted-foreground'
              )}>
                {step.text}
              </span>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

// ============================================================================
// Conflict Resolution
// ============================================================================

function ConflictResolution({
  analysis,
  selectedConflicts,
  onToggleConflict,
}: {
  analysis: RuleAnalysis
  selectedConflicts: Set<string>
  onToggleConflict: (id: string) => void
}) {
  if (!analysis.conflicts.length && !analysis.overrides.length && !analysis.clarifications.length) {
    return null
  }
  
  return (
    <div className="space-y-4">
      {/* Overrides - Good news */}
      {analysis.overrides.length > 0 && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
          <div className="flex items-start gap-3">
            <Icons.checkCircle className="h-5 w-5 text-emerald-600 mt-0.5" strokeWidth={1.5} />
            <div>
              <h4 className="font-semibold text-emerald-800">Override Notice</h4>
              <p className="text-sm text-emerald-700 mt-1">
                This INSTRUCTION rule will correctly override system-wide BASE rules for the specified entity.
              </p>
              <ul className="mt-2 space-y-1">
                {analysis.overrides.map((override, i) => (
                  <li key={i} className="text-sm text-emerald-600">
                    • Overrides: <span className="font-medium">{override.overridden_rule_name}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
      
      {/* Conflicts - Must resolve */}
      {analysis.conflicts.length > 0 && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl">
          <div className="flex items-start gap-3">
            <Icons.alertTriangle className="h-5 w-5 text-red-600 mt-0.5" strokeWidth={1.5} />
            <div className="flex-1">
              <h4 className="font-semibold text-red-800">Conflicts Detected</h4>
              <p className="text-sm text-red-700 mt-1">
                The following rules conflict with your new rule. Select which ones to deactivate:
              </p>
              <div className="mt-3 space-y-2">
                {analysis.conflicts.map((conflict) => (
                  <label
                    key={conflict.conflicting_rule_id}
                    className={cn(
                      'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                      selectedConflicts.has(conflict.conflicting_rule_id)
                        ? 'bg-red-100 border-red-300'
                        : 'bg-white border-red-100 hover:bg-red-50'
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={selectedConflicts.has(conflict.conflicting_rule_id)}
                      onChange={() => onToggleConflict(conflict.conflicting_rule_id)}
                      className="mt-0.5 h-4 w-4 rounded border-red-300 text-red-600 focus:ring-red-500"
                    />
                    <div>
                      <span className="font-medium text-red-800">
                        {conflict.conflicting_rule_name}
                      </span>
                      <p className="text-xs text-red-600 mt-0.5">{conflict.explanation}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Clarifications - Questions from AI */}
      {analysis.clarifications.length > 0 && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <div className="flex items-start gap-3">
            <Icons.helpCircle className="h-5 w-5 text-amber-600 mt-0.5" strokeWidth={1.5} />
            <div>
              <h4 className="font-semibold text-amber-800">AI needs clarification</h4>
              <p className="text-sm text-amber-700 mt-1">
                Consider addressing these questions to make your rule more precise:
              </p>
              <ul className="mt-2 space-y-1">
                {analysis.clarifications.map((q, i) => (
                  <li key={i} className="text-sm text-amber-700">• {q}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================================
// AI Suggestions
// ============================================================================

function AISuggestions({
  suggestions,
  selected,
  onSelect,
}: {
  suggestions: string[]
  selected: string | null
  onSelect: (instruction: string) => void
}) {
  if (!suggestions.length) return null
  
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Icons.sparkles className="h-4 w-4 text-brand-cornflower" strokeWidth={1.5} />
        <h4 className="font-medium text-foreground">AI-Suggested Instructions</h4>
      </div>
      <p className="text-sm text-muted-foreground">
        Select the version that best captures your intent:
      </p>
      <div className="space-y-2">
        {suggestions.map((instruction, i) => (
          <button
            key={i}
            onClick={() => onSelect(instruction)}
            className={cn(
              'w-full flex items-start gap-3 p-4 rounded-xl border text-left transition-all',
              selected === instruction
                ? 'bg-brand-cornflower/10 border-brand-cornflower ring-2 ring-brand-cornflower/30'
                : 'bg-white/50 border-border/50 hover:bg-white hover:border-brand-cornflower/30'
            )}
          >
            <div className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full border-2 flex-shrink-0 mt-0.5',
              selected === instruction
                ? 'border-brand-cornflower bg-brand-cornflower'
                : 'border-muted-foreground/30'
            )}>
              {selected === instruction && (
                <Icons.check className="h-3 w-3 text-white" strokeWidth={3} />
              )}
            </div>
            <p className="text-sm text-foreground leading-relaxed">{instruction}</p>
          </button>
        ))}
      </div>
    </div>
  )
}

// ============================================================================
// Collapsible Refined Instruction
// ============================================================================

function RefinedInstructionPreview({
  instruction,
  onEdit,
  isEditing,
  editValue,
  onEditChange,
  onEditSave,
  onEditCancel,
}: {
  instruction: string
  onEdit: () => void
  isEditing: boolean
  editValue: string
  onEditChange: (value: string) => void
  onEditSave: () => void
  onEditCancel: () => void
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  
  return (
    <div className="border border-border/50 rounded-xl bg-muted/30 overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <Icons.chevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <Icons.chevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <span className="font-medium text-foreground">AI-Refined Instruction</span>
          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-brand-cornflower/10 text-brand-cornflower">
            System Internal
          </span>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation()
            onEdit()
          }}
        >
          <Icons.edit className="h-3.5 w-3.5 mr-1.5" />
          Edit
        </Button>
      </button>
      
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 border-t border-border/50">
              {isEditing ? (
                <div className="mt-3 space-y-3">
                  <textarea
                    value={editValue}
                    onChange={(e) => onEditChange(e.target.value)}
                    className="w-full min-h-[100px] p-3 text-sm font-mono bg-white border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50"
                  />
                  <div className="flex justify-end gap-2">
                    <Button type="button" variant="ghost" size="sm" onClick={onEditCancel}>
                      Cancel
                    </Button>
                    <Button type="button" variant="default" size="sm" onClick={onEditSave}>
                      Save Changes
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="mt-3">
                  <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                    {instruction}
                  </p>
                  <p className="mt-3 text-xs text-muted-foreground italic flex items-center gap-1.5">
                    <Icons.info className="h-3 w-3" />
                    This is the AI-optimized version that powers the rule engine.
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ============================================================================
// Main Modal Component
// ============================================================================

type ModalStep = 'input' | 'analyzing' | 'review' | 'saving'

export function RuleBuilderModal({
  isOpen,
  onClose,
  onSave,
  initialData,
  entityName,
}: RuleBuilderModalProps) {
  // Form state
  const [step, setStep] = useState<ModalStep>('input')
  const [analysisStep, setAnalysisStep] = useState(0)
  const [formData, setFormData] = useState<RuleFormData>({
    name: initialData?.name || '',
    description: initialData?.description || '',
    naturalLanguage: initialData?.naturalLanguage || '',
    policyType: initialData?.policyType || (entityName ? 'INSTRUCTION' : 'BASE'),
    entityName: initialData?.entityName || entityName,
    priority: initialData?.priority || 100,
    tags: initialData?.tags || [],
  })
  
  // Analysis state
  const [analysis, setAnalysis] = useState<RuleAnalysis | null>(null)
  const [selectedSuggestion, setSelectedSuggestion] = useState<string | null>(null)
  const [selectedConflicts, setSelectedConflicts] = useState<Set<string>>(new Set())
  
  // Refined instruction editing
  const [isEditingRefined, setIsEditingRefined] = useState(false)
  const [editedRefined, setEditedRefined] = useState('')
  
  // Error state
  const [error, setError] = useState<string | null>(null)
  
  // Reset on open
  useEffect(() => {
    if (isOpen) {
      setStep('input')
      setAnalysis(null)
      setSelectedSuggestion(null)
      setSelectedConflicts(new Set())
      setError(null)
    }
  }, [isOpen])
  
  // Simulate analysis steps
  useEffect(() => {
    if (step === 'analyzing' && analysisStep < analysisSteps.length) {
      const timer = setTimeout(() => {
        setAnalysisStep((prev) => prev + 1)
      }, 600)
      return () => clearTimeout(timer)
    }
    if (step === 'analyzing' && analysisStep >= analysisSteps.length) {
      // Analysis complete, move to review
      performAnalysis()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, analysisStep])
  
  const performAnalysis = async () => {
    try {
      const data = await apiClient.post<RuleAnalysis>('/api/ai/policies/analyze', {
        natural_language: formData.naturalLanguage,
        policy_type: formData.policyType,
        entity_name: formData.entityName,
      })
      
      setAnalysis(data)
      setSelectedSuggestion(data.refined_instruction)
      setEditedRefined(data.refined_instruction)
      setStep('review')
    } catch {
      // Use mock analysis for demo
      const mockAnalysis: RuleAnalysis = {
        conflicts: [],
        overrides: [],
        clarifications: [],
        suggested_instructions: [
          formData.naturalLanguage.charAt(0).toUpperCase() + formData.naturalLanguage.slice(1) + '. If this condition is not met, flag for REVIEW.',
          'Verify that ' + formData.naturalLanguage.toLowerCase() + '. Log results in the audit trace.',
        ],
        refined_instruction: formData.naturalLanguage.charAt(0).toUpperCase() + formData.naturalLanguage.slice(1) + '. If this condition is not met, flag for REVIEW.',
        is_valid: true,
      }
      setAnalysis(mockAnalysis)
      setSelectedSuggestion(mockAnalysis.refined_instruction)
      setEditedRefined(mockAnalysis.refined_instruction)
      setStep('review')
    }
  }
  
  const handleAnalyze = () => {
    if (!formData.naturalLanguage.trim()) {
      setError('Please enter a rule description')
      return
    }
    if (!formData.name.trim()) {
      // Auto-generate name
      const words = formData.naturalLanguage.split(' ').slice(0, 5).join(' ')
      setFormData((prev) => ({ ...prev, name: words + '...' }))
    }
    setError(null)
    setAnalysisStep(0)
    setStep('analyzing')
  }
  
  const handleSave = async () => {
    if (!analysis) return
    
    setStep('saving')
    
    try {
      await onSave({
        ...formData,
        refined_instruction: isEditingRefined ? editedRefined : (selectedSuggestion || analysis.refined_instruction),
        conflict_resolution: selectedConflicts.size > 0 
          ? { deactivate_ids: Array.from(selectedConflicts) }
          : undefined,
      })
      onClose()
    } catch (err) {
      console.error('Save error:', err)
      setError('Failed to save rule. Please try again.')
      setStep('review')
    }
  }
  
  const toggleConflict = (id: string) => {
    setSelectedConflicts((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }
  
  const canSave = analysis?.is_valid || 
    (analysis?.conflicts.length === selectedConflicts.size)
  
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icons.brain className="h-5 w-5 text-brand-cornflower" strokeWidth={1.5} />
            {step === 'input' && 'Create AI Policy'}
            {step === 'analyzing' && 'Analyzing Rule...'}
            {step === 'review' && 'Review & Confirm'}
            {step === 'saving' && 'Saving Rule...'}
          </DialogTitle>
          <DialogDescription>
            {step === 'input' && 'Describe your rule in plain English. The AI will refine it into executable logic.'}
            {step === 'analyzing' && 'Please wait while AutoPilot AI processes your rule.'}
            {step === 'review' && 'Review the AI analysis and select your preferred instruction.'}
            {step === 'saving' && 'Saving your rule...'}
          </DialogDescription>
        </DialogHeader>
        
        <div className="mt-4 space-y-6">
          {/* Step 1: Input */}
          {step === 'input' && (
            <>
              {/* Name */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Rule Name <span className="text-muted-foreground">(optional)</span>
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., Auto-approve low-value items"
                  className="w-full px-3 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50"
                />
              </div>
              
              {/* Natural Language Rule */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Describe the Rule in Plain English <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={formData.naturalLanguage}
                  onChange={(e) => setFormData((prev) => ({ ...prev, naturalLanguage: e.target.value }))}
                  placeholder="e.g., If the total amount is less than $100, automatically approve the item without requiring manual review"
                  rows={4}
                  className="w-full px-3 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50 resize-none"
                />
                <p className="text-xs text-muted-foreground">
                  Be descriptive. Include specific values, conditions, and what should happen when they are met.
                </p>
              </div>
              
              {/* Policy Type */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Policy Type</label>
                  <select
                    value={formData.policyType}
                    onChange={(e) => setFormData((prev) => ({ ...prev, policyType: e.target.value as 'BASE' | 'INSTRUCTION' }))}
                    className="w-full px-3 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50"
                  >
                    <option value="BASE">BASE (System-wide)</option>
                    <option value="INSTRUCTION">INSTRUCTION (Entity-specific)</option>
                  </select>
                </div>
                
                {formData.policyType === 'INSTRUCTION' && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">Entity Name</label>
                    <input
                      type="text"
                      value={formData.entityName || ''}
                      onChange={(e) => setFormData((prev) => ({ ...prev, entityName: e.target.value }))}
                      placeholder="e.g., Acme Corp"
                      className="w-full px-3 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50"
                    />
                  </div>
                )}
              </div>
              
              {/* Error */}
              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}
              
              {/* Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t">
                <Button variant="ghost" onClick={onClose}>Cancel</Button>
                <Button variant="gradient" onClick={handleAnalyze}>
                  <Icons.sparkles className="mr-2 h-4 w-4" strokeWidth={1.5} />
                  Analyze with AI
                </Button>
              </div>
            </>
          )}
          
          {/* Step 2: Analyzing */}
          {step === 'analyzing' && (
            <AnalyzingState currentStep={analysisStep} />
          )}
          
          {/* Step 3: Review */}
          {step === 'review' && analysis && (
            <>
              {/* Original Rule */}
              <div className="p-4 bg-muted/30 rounded-xl border border-border/50">
                <p className="text-sm font-medium text-muted-foreground mb-1">Your Rule:</p>
                <p className="text-foreground">{formData.naturalLanguage}</p>
              </div>
              
              {/* Conflict Resolution */}
              <ConflictResolution
                analysis={analysis}
                selectedConflicts={selectedConflicts}
                onToggleConflict={toggleConflict}
              />
              
              {/* AI Suggestions */}
              <AISuggestions
                suggestions={analysis.suggested_instructions}
                selected={selectedSuggestion}
                onSelect={setSelectedSuggestion}
              />
              
              {/* Refined Instruction Preview */}
              <RefinedInstructionPreview
                instruction={selectedSuggestion || analysis.refined_instruction}
                onEdit={() => setIsEditingRefined(true)}
                isEditing={isEditingRefined}
                editValue={editedRefined}
                onEditChange={setEditedRefined}
                onEditSave={() => {
                  setSelectedSuggestion(editedRefined)
                  setIsEditingRefined(false)
                }}
                onEditCancel={() => {
                  setEditedRefined(selectedSuggestion || analysis.refined_instruction)
                  setIsEditingRefined(false)
                }}
              />
              
              {/* Error */}
              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}
              
              {/* Actions */}
              <div className="flex justify-between gap-3 pt-4 border-t">
                <Button variant="ghost" onClick={() => setStep('input')}>
                  <Icons.arrowLeft className="mr-2 h-4 w-4" />
                  Back to Edit
                </Button>
                <div className="flex gap-3">
                  <Button variant="ghost" onClick={onClose}>Cancel</Button>
                  <Button 
                    variant="gradient" 
                    onClick={handleSave}
                    disabled={!canSave}
                  >
                    <Icons.check className="mr-2 h-4 w-4" />
                    Save Rule
                  </Button>
                </div>
              </div>
            </>
          )}
          
          {/* Step 4: Saving */}
          {step === 'saving' && (
            <div className="flex flex-col items-center justify-center py-12">
              <Icons.loader className="h-10 w-10 text-brand-cornflower animate-spin" strokeWidth={1.5} />
              <p className="mt-4 text-muted-foreground">Saving your rule...</p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

