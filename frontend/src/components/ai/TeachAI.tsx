'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { RuleBuilderModal, type RuleFormData } from './policies/RuleBuilderModal'

interface TeachAIProps {
  /** Context identifier (e.g., invoice ID, record ID) */
  contextId?: string
  /** Entity name for INSTRUCTION rules (e.g., vendor name) */
  entityName?: string
  /** Callback when a rule is successfully created */
  onRuleCreated?: (rule: RuleFormData & { refined_instruction: string }) => void
  /** Optional pre-filled rule description */
  initialDescription?: string
  /** Custom trigger button */
  trigger?: React.ReactNode
  /** Compact mode for inline usage */
  compact?: boolean
}

/**
 * TeachAI Component - In-context learning for the AI system
 * 
 * Allows users to teach the AI new rules directly from their current context.
 * Useful when the AI makes mistakes or when users want to add custom logic.
 * 
 * @example
 * <TeachAI
 *   entityName="Acme Corp"
 *   contextId="INV-12345"
 *   onRuleCreated={(rule) => console.log('New rule:', rule)}
 * />
 */
export function TeachAI({
  contextId,
  entityName,
  onRuleCreated,
  initialDescription,
  trigger,
  compact = false,
}: TeachAIProps) {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [prefilledData, setPrefilledData] = useState<Partial<RuleFormData>>({})
  
  const handleOpenModal = () => {
    // Generate a unique code for the feedback rule
    const timestamp = new Date().toISOString().slice(0, 19).replace(/\-/g, '').replace(/:/g, '').replace(/T/g, '')
    
    setPrefilledData({
      name: contextId 
        ? `Feedback Rule for ${entityName || 'Entity'} (${contextId})`
        : `Custom Rule ${timestamp}`,
      naturalLanguage: initialDescription || '',
      policyType: entityName ? 'INSTRUCTION' : 'BASE',
      entityName: entityName,
      tags: ['feedback', contextId ? `context:${contextId}` : ''].filter(Boolean),
    })
    
    setIsModalOpen(true)
  }
  
  const handleSaveRule = async (data: RuleFormData & { refined_instruction: string; conflict_resolution?: { deactivate_ids: string[] } }) => {
    try {
      await apiClient.post('/api/ai/policies', {
        name: data.name,
        description: data.description,
        natural_language: data.naturalLanguage,
        policy_type: data.policyType,
        entity_name: data.entityName,
        priority: data.priority,
        tags: data.tags,
        refined_instruction: data.refined_instruction,
      })
      
      // Handle conflict resolution if needed
      if (data.conflict_resolution?.deactivate_ids.length) {
        for (const id of data.conflict_resolution.deactivate_ids) {
          await apiClient.patch(`/api/ai/policies/${id}`, { is_active: false })
        }
      }
      
      onRuleCreated?.(data)
      
    } catch (error) {
      throw error
    }
  }
  
  // Custom trigger button
  if (trigger) {
    return (
      <>
        <div onClick={handleOpenModal}>{trigger}</div>
        <RuleBuilderModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSave={handleSaveRule}
          initialData={prefilledData}
          entityName={entityName}
        />
      </>
    )
  }
  
  // Compact mode - just a button
  if (compact) {
    return (
      <>
        <Button
          variant="outline"
          size="sm"
          onClick={handleOpenModal}
          className="gap-2"
        >
          <Icons.brain className="h-4 w-4 text-brand-cornflower" strokeWidth={1.5} />
          Teach AI
        </Button>
        <RuleBuilderModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSave={handleSaveRule}
          initialData={prefilledData}
          entityName={entityName}
        />
      </>
    )
  }
  
  // Full card mode
  return (
    <>
      <div className={cn(
        'rounded-xl border border-border/50 bg-white/50 p-4',
        'backdrop-blur-sm'
      )}>
        <div className="flex items-start gap-4">
          <div className={cn(
            'flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl',
            'bg-gradient-to-br from-brand-navy/10 to-brand-purple/10'
          )}>
            <Icons.brain className="h-6 w-6 text-brand-cornflower" strokeWidth={1.5} />
          </div>
          
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-foreground">AI Feedback & Training</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Is the AI making a mistake? Teach it the correct logic.
              {entityName && (
                <>
                  {' '}Your new rule will be used for all future items from{' '}
                  <strong className="text-foreground">{entityName}</strong>.
                </>
              )}
            </p>
            
            <Button
              variant="default"
              size="sm"
              onClick={handleOpenModal}
              className="mt-3"
            >
              <Icons.brain className="mr-2 h-4 w-4" strokeWidth={1.5} />
              Teach the AI a New Rule
            </Button>
          </div>
        </div>
      </div>
      
      <RuleBuilderModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveRule}
        initialData={prefilledData}
        entityName={entityName}
      />
    </>
  )
}

