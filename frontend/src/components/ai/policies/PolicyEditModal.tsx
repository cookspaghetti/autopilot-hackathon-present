'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { apiClient } from '@/lib/api-client'
import { StructuredBuilder } from './StructuredBuilder'
import type { Policy, PolicyDSL } from './PolicyCard'

// ============================================================================
// Types
// ============================================================================

interface PolicyEditModalProps {
  policy: Policy | null
  isOpen: boolean
  onClose: () => void
  onSave: (policy: Policy) => void
}

type PolicyType = 'logical' | 'natural_language'

interface FormData {
  name: string
  description: string
  natural_language: string
  policy_type: PolicyType
  refined_instruction: string
  entity_name: string
  priority: number
  tags: string[]
  is_active: boolean
  dsl: PolicyDSL | null
}

// ============================================================================
// Animation Variants
// ============================================================================

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
  exit: { opacity: 0 },
}

const modalVariants = {
  hidden: { opacity: 0, scale: 0.95, y: 20 },
  visible: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.95, y: 20 },
}

// ============================================================================
// Component
// ============================================================================

export function PolicyEditModal({ policy, isOpen, onClose, onSave }: PolicyEditModalProps) {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    description: '',
    natural_language: '',
    policy_type: 'logical',
    refined_instruction: '',
    entity_name: '',
    priority: 100,
    tags: [],
    is_active: true,
    dsl: null,
  })
  const [isTranslating, setIsTranslating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [tagInput, setTagInput] = useState('')
  const [activeTab, setActiveTab] = useState<'basic' | 'advanced'>('basic')

  // Initialize form when policy changes
  useEffect(() => {
    if (policy) {
      setFormData({
        name: policy.name,
        description: policy.description,
        natural_language: policy.natural_language,
        policy_type: policy.policy_type,
        refined_instruction: policy.refined_instruction || '',
        entity_name: policy.entity_name || '',
        priority: policy.priority,
        tags: policy.tags,
        is_active: policy.is_active,
        dsl: policy.dsl,
      })
    } else {
      // Reset for new policy
      setFormData({
        name: '',
        description: '',
        natural_language: '',
        policy_type: 'logical',
        refined_instruction: '',
        entity_name: '',
        priority: 100,
        tags: [],
        is_active: true,
        dsl: null,
      })
    }
  }, [policy])

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

  const handleInputChange = useCallback((field: keyof FormData, value: unknown) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }, [])

  const handleTranslate = useCallback(async () => {
    if (!formData.natural_language.trim()) return

    setIsTranslating(true)
    try {
      const result = await apiClient.post<{ dsl: PolicyDSL; confidence: number }>('/api/ai/policies/translate', {
        natural_language: formData.natural_language,
      })
      handleInputChange('dsl', result.dsl)
      handleInputChange('policy_type', 'logical')
    } catch (error) {
      console.error('Translation failed:', error)
    } finally {
      setIsTranslating(false)
    }
  }, [formData.natural_language, handleInputChange])

  const handleAddTag = useCallback(() => {
    const tag = tagInput.trim().toLowerCase().replace(/[^a-z0-9-]/g, '-')
    if (tag && !formData.tags.includes(tag)) {
      handleInputChange('tags', [...formData.tags, tag])
    }
    setTagInput('')
  }, [tagInput, formData.tags, handleInputChange])

  const handleRemoveTag = useCallback((tagToRemove: string) => {
    handleInputChange('tags', formData.tags.filter((t) => t !== tagToRemove))
  }, [formData.tags, handleInputChange])

  const handleSave = useCallback(async () => {
    if (!formData.name.trim() || !formData.natural_language.trim()) return

    setIsSaving(true)
    try {
      const payload = {
        name: formData.name,
        description: formData.description,
        natural_language: formData.natural_language,
        policy_type: formData.policy_type,
        refined_instruction: formData.policy_type === 'natural_language' ? formData.refined_instruction : null,
        entity_name: formData.entity_name || null,
        priority: formData.priority,
        tags: formData.tags,
        is_active: formData.is_active,
        dsl: formData.policy_type === 'logical' ? formData.dsl : null,
      }

      let savedPolicy: Policy
      if (policy) {
        savedPolicy = await apiClient.patch<Policy>(`/api/ai/policies/${policy.id}`, payload)
      } else {
        savedPolicy = await apiClient.post<Policy>('/api/ai/policies', payload)
      }
      
      onSave(savedPolicy)
      onClose()
    } catch (error) {
      console.error('Save failed:', error)
    } finally {
      setIsSaving(false)
    }
  }, [formData, policy, onSave, onClose])

  if (!isOpen) return null

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[500] flex items-center justify-center p-4"
        style={{
          backgroundColor: 'rgba(26, 35, 64, 0.5)',
          backdropFilter: 'blur(8px)',
        }}
        variants={overlayVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        onClick={onClose}
      >
        <motion.div
          className="relative w-full max-w-2xl max-h-[90vh] bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col"
          variants={modalVariants}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <div className={cn(
                'p-2 rounded-lg',
                policy ? 'bg-blue-100' : 'bg-emerald-100'
              )}>
                {policy ? (
                  <Icons.pencil className="h-5 w-5 text-blue-600" />
                ) : (
                  <Icons.plus className="h-5 w-5 text-emerald-600" />
                )}
              </div>
              <div>
                <h2 className="text-lg font-semibold text-brand-navy">
                  {policy ? 'Edit Policy' : 'Create New Policy'}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {policy ? 'Modify the policy settings below' : 'Define a new AI policy'}
                </p>
              </div>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <Icons.close className="h-5 w-5" />
            </Button>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-gray-200">
            <button
              className={cn(
                'flex-1 py-3 text-sm font-medium transition-colors',
                activeTab === 'basic'
                  ? 'text-brand-cornflower border-b-2 border-brand-cornflower'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              onClick={() => setActiveTab('basic')}
            >
              Basic Settings
            </button>
            <button
              className={cn(
                'flex-1 py-3 text-sm font-medium transition-colors',
                activeTab === 'advanced'
                  ? 'text-brand-cornflower border-b-2 border-brand-cornflower'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              onClick={() => setActiveTab('advanced')}
            >
              Advanced
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {activeTab === 'basic' ? (
              <>
                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    Policy Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    placeholder="e.g., Auto-Approve Low Value Invoices"
                    className={cn(
                      'w-full px-3 py-2 rounded-lg border border-input',
                      'text-sm focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50'
                    )}
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    Description
                  </label>
                  <input
                    type="text"
                    value={formData.description}
                    onChange={(e) => handleInputChange('description', e.target.value)}
                    placeholder="Brief description of what this policy does"
                    className={cn(
                      'w-full px-3 py-2 rounded-lg border border-input',
                      'text-sm focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50'
                    )}
                  />
                </div>

                {/* Natural Language Input */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    Your Rule (Natural Language) *
                  </label>
                  <textarea
                    value={formData.natural_language}
                    onChange={(e) => handleInputChange('natural_language', e.target.value)}
                    placeholder="Describe your rule in plain English. E.g., 'If an invoice is under $500 and from an approved vendor, automatically approve it'"
                    rows={4}
                    className={cn(
                      'w-full px-3 py-2 rounded-lg border border-input resize-none',
                      'text-sm focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50'
                    )}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Write your rule clearly. The AI will determine the best format (logical or natural language).
                  </p>
                </div>

                {/* Policy Type Selection */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Policy Type
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => handleInputChange('policy_type', 'logical')}
                      className={cn(
                        'p-4 rounded-xl border-2 transition-all text-left',
                        formData.policy_type === 'logical'
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      )}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Icons.grid className={cn(
                          'h-5 w-5',
                          formData.policy_type === 'logical' ? 'text-blue-600' : 'text-gray-400'
                        )} />
                        <span className={cn(
                          'font-medium',
                          formData.policy_type === 'logical' ? 'text-blue-700' : 'text-gray-700'
                        )}>
                          Structured Rules
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Visual conditions and actions. Best for clear, quantifiable rules.
                      </p>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleInputChange('policy_type', 'natural_language')}
                      className={cn(
                        'p-4 rounded-xl border-2 transition-all text-left',
                        formData.policy_type === 'natural_language'
                          ? 'border-purple-500 bg-purple-50'
                          : 'border-gray-200 hover:border-gray-300'
                      )}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Icons.brain className={cn(
                          'h-5 w-5',
                          formData.policy_type === 'natural_language' ? 'text-purple-600' : 'text-gray-400'
                        )} />
                        <span className={cn(
                          'font-medium',
                          formData.policy_type === 'natural_language' ? 'text-purple-700' : 'text-gray-700'
                        )}>
                          Natural Language
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        AI interprets refined instruction. Best for complex, contextual rules.
                      </p>
                    </button>
                  </div>
                </div>

                {/* Analyze Button (for logical type) */}
                {formData.policy_type === 'logical' && (
                  <div className="flex items-center gap-3">
                    <Button
                      variant="outline"
                      onClick={handleTranslate}
                      disabled={!formData.natural_language.trim() || isTranslating}
                    >
                      {isTranslating ? (
                        <>
                          <Icons.loader className="h-4 w-4 mr-2 animate-spin" />
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <Icons.sparkles className="h-4 w-4 mr-2" />
                          Generate Rules with AI
                        </>
                      )}
                    </Button>
                    {formData.dsl && (
                      <span className="text-sm text-emerald-600 flex items-center gap-1">
                        <Icons.check className="h-4 w-4" />
                        Rules generated
                      </span>
                    )}
                  </div>
                )}
                
                {/* Visual Rule Builder (for logical type with DSL) */}
                {formData.policy_type === 'logical' && formData.dsl && (
                  <div className="p-4 bg-blue-50/50 rounded-xl border border-blue-100">
                    <StructuredBuilder
                      initialDSL={{
                        conditions: formData.dsl.conditions.map((c, i) => ({
                          id: `cond-${i}`,
                          field: c.field,
                          operator: c.operator,
                          value: String(c.value ?? ''),
                        })),
                        actions: formData.dsl.actions.map((a, i) => ({
                          id: `action-${i}`,
                          type: a.type,
                          value: a.value ? String(a.value) : undefined,
                        })),
                        match_mode: formData.dsl.match_mode || 'all',
                      }}
                      onChange={(dsl) => {
                        handleInputChange('dsl', {
                          conditions: dsl.conditions.map(c => ({
                            field: c.field,
                            operator: c.operator,
                            value: c.value,
                          })),
                          actions: dsl.actions.map(a => ({
                            type: a.type,
                            value: a.value,
                          })),
                          match_mode: dsl.match_mode,
                          stop_on_match: true,
                        })
                      }}
                    />
                  </div>
                )}

                {/* Refined Instruction (for natural language type) */}
                {formData.policy_type === 'natural_language' && (
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">
                      Refined Instruction (AI-optimized)
                    </label>
                    <textarea
                      value={formData.refined_instruction}
                      onChange={(e) => handleInputChange('refined_instruction', e.target.value)}
                      placeholder="The AI will use this refined version. Leave empty to use your original input."
                      rows={3}
                      className={cn(
                        'w-full px-3 py-2 rounded-lg border border-input resize-none',
                        'text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-500/50'
                      )}
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Optionally refine the instruction. This is what the AI will actually use.
                    </p>
                  </div>
                )}
              </>
            ) : (
              <>
                {/* Entity Name */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    Entity Name (Optional)
                  </label>
                  <input
                    type="text"
                    value={formData.entity_name}
                    onChange={(e) => handleInputChange('entity_name', e.target.value)}
                    placeholder="e.g., Vendor name, category, department"
                    className={cn(
                      'w-full px-3 py-2 rounded-lg border border-input',
                      'text-sm focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50'
                    )}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    If this policy applies to a specific entity (vendor, category, etc.)
                  </p>
                </div>

                {/* Priority */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    Priority (Lower = Higher Priority)
                  </label>
                  <div className="flex items-center gap-3">
                    <input
                      type="range"
                      min="1"
                      max="100"
                      value={formData.priority}
                      onChange={(e) => handleInputChange('priority', parseInt(e.target.value))}
                      className="flex-1"
                    />
                    <span className="w-12 text-center text-sm font-mono bg-muted px-2 py-1 rounded">
                      {formData.priority}
                    </span>
                  </div>
                </div>

                {/* Tags */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    Tags
                  </label>
                  <div className="flex items-center gap-2 mb-2">
                    <input
                      type="text"
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                      placeholder="Add a tag"
                      className={cn(
                        'flex-1 px-3 py-2 rounded-lg border border-input',
                        'text-sm focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50'
                      )}
                    />
                    <Button variant="outline" size="sm" onClick={handleAddTag}>
                      Add
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {formData.tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-muted text-sm"
                      >
                        #{tag}
                        <button
                          onClick={() => handleRemoveTag(tag)}
                          className="text-muted-foreground hover:text-foreground"
                        >
                          <Icons.close className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                </div>

                {/* Active Status */}
                <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
                  <div>
                    <p className="font-medium text-foreground">Active Status</p>
                    <p className="text-sm text-muted-foreground">
                      {formData.is_active ? 'Policy is active and will be evaluated' : 'Policy is inactive'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleInputChange('is_active', !formData.is_active)}
                    className={cn(
                      'w-12 h-6 rounded-full transition-colors relative',
                      formData.is_active ? 'bg-emerald-500' : 'bg-gray-300'
                    )}
                  >
                    <span
                      className={cn(
                        'absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform',
                        formData.is_active ? 'left-6' : 'left-0.5'
                      )}
                    />
                  </button>
                </div>

                {/* Rule Summary (if available) */}
                {formData.dsl && formData.policy_type === 'logical' && (
                  <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center gap-2 mb-2">
                      <Icons.info className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium text-foreground">Rule Summary</span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {formData.dsl.conditions.length} condition(s) and {formData.dsl.actions.length} action(s) configured. 
                      Edit rules in the Basic Settings tab using the visual builder.
                    </p>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="gradient"
              onClick={handleSave}
              disabled={!formData.name.trim() || !formData.natural_language.trim() || isSaving}
            >
              {isSaving ? (
                <>
                  <Icons.loader className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Icons.check className="h-4 w-4 mr-2" />
                  {policy ? 'Save Changes' : 'Create Policy'}
                </>
              )}
            </Button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

