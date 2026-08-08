'use client'

import { useState, useCallback } from 'react'
import { motion, AnimatePresence, Reorder } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'

// ============================================================================
// Types
// ============================================================================

export interface Condition {
  id: string
  field: string
  operator: string
  value: string
}

export interface Action {
  id: string
  type: string
  value?: string
}

export interface PolicyDSL {
  conditions: Condition[]
  actions: Action[]
  match_mode: 'all' | 'any'
}

interface StructuredBuilderProps {
  initialDSL?: PolicyDSL | null
  onChange?: (dsl: PolicyDSL) => void
  readOnly?: boolean
}

// ============================================================================
// Constants
// ============================================================================

const OPERATORS = [
  { value: 'eq', symbol: '=', label: 'equals' },
  { value: 'neq', symbol: '≠', label: 'not equals' },
  { value: 'gt', symbol: '>', label: 'greater than' },
  { value: 'lt', symbol: '<', label: 'less than' },
  { value: 'gte', symbol: '≥', label: 'at least' },
  { value: 'lte', symbol: '≤', label: 'at most' },
  { value: 'in', symbol: '∈', label: 'in list' },
  { value: 'not_in', symbol: '∉', label: 'not in list' },
  { value: 'contains', symbol: '⊃', label: 'contains' },
]

const COMMON_FIELDS = [
  { value: 'amount', label: 'Amount' },
  { value: 'status', label: 'Status' },
  { value: 'type', label: 'Type' },
  { value: 'category', label: 'Category' },
  { value: 'priority', label: 'Priority' },
  { value: 'user_role', label: 'User Role' },
  { value: 'vendor_status', label: 'Vendor Status' },
  { value: 'customer_tier', label: 'Customer Tier' },
  { value: 'days_requested', label: 'Days Requested' },
  { value: 'request_type', label: 'Request Type' },
]

const COMMON_ACTIONS = [
  { value: 'auto_approve', label: 'Auto Approve', icon: 'check' },
  { value: 'auto_reject', label: 'Auto Reject', icon: 'close' },
  { value: 'flag_review', label: 'Flag for Review', icon: 'flag' },
  { value: 'require_approval', label: 'Require Approval', icon: 'userCheck' },
  { value: 'notify', label: 'Send Notification', icon: 'bell' },
  { value: 'notify_admin', label: 'Notify Admin', icon: 'userCog' },
  { value: 'escalate', label: 'Escalate', icon: 'arrowUp' },
  { value: 'add_tag', label: 'Add Tag', icon: 'tag' },
  { value: 'add_note', label: 'Add Note', icon: 'fileText' },
  { value: 'set_priority', label: 'Set Priority', icon: 'layers' },
  { value: 'assign_team', label: 'Assign Team', icon: 'users' },
]

// ============================================================================
// Helper
// ============================================================================

function generateId() {
  return Math.random().toString(36).substr(2, 9)
}

// ============================================================================
// Condition Row Component
// ============================================================================

function ConditionRow({
  condition,
  index,
  onUpdate,
  onRemove,
  readOnly,
}: {
  condition: Condition
  index: number
  onUpdate: (id: string, field: keyof Condition, value: string) => void
  onRemove: (id: string) => void
  readOnly?: boolean
}) {
  const selectedOp = OPERATORS.find(op => op.value === condition.operator) || OPERATORS[0]

  return (
    <Reorder.Item
      value={condition}
      id={condition.id}
      className={cn(
        'flex items-center gap-2 p-3 rounded-lg bg-blue-50 border border-blue-100',
        !readOnly && 'cursor-grab active:cursor-grabbing'
      )}
    >
      {/* Drag Handle */}
      {!readOnly && (
        <div className="text-blue-300 hover:text-blue-500">
          <Icons.gripVertical className="h-4 w-4" />
        </div>
      )}
      
      {/* Index */}
      <span className="w-6 h-6 rounded bg-blue-200 text-blue-700 flex items-center justify-center text-xs font-bold flex-shrink-0">
        {index + 1}
      </span>
      
      {/* Field Select */}
      <select
        value={condition.field}
        onChange={(e) => onUpdate(condition.id, 'field', e.target.value)}
        disabled={readOnly}
        className={cn(
          'px-2 py-1.5 rounded border border-blue-200 bg-white text-sm font-medium text-blue-900',
          'focus:outline-none focus:ring-2 focus:ring-blue-300',
          'min-w-[120px]'
        )}
      >
        {COMMON_FIELDS.map(f => (
          <option key={f.value} value={f.value}>{f.label}</option>
        ))}
        <option value={condition.field}>{condition.field}</option>
      </select>
      
      {/* Operator Select */}
      <select
        value={condition.operator}
        onChange={(e) => onUpdate(condition.id, 'operator', e.target.value)}
        disabled={readOnly}
        className={cn(
          'px-3 py-1.5 rounded border border-blue-200 bg-white text-lg font-mono text-blue-600',
          'focus:outline-none focus:ring-2 focus:ring-blue-300',
          'w-16 text-center'
        )}
      >
        {OPERATORS.map(op => (
          <option key={op.value} value={op.value}>{op.symbol}</option>
        ))}
      </select>
      
      {/* Value Input */}
      <input
        type="text"
        value={condition.value}
        onChange={(e) => onUpdate(condition.id, 'value', e.target.value)}
        disabled={readOnly}
        placeholder="value"
        className={cn(
          'flex-1 px-3 py-1.5 rounded border border-blue-200 bg-white text-sm font-mono text-blue-800',
          'focus:outline-none focus:ring-2 focus:ring-blue-300',
          'min-w-[100px]'
        )}
      />
      
      {/* Operator Label */}
      <span className="text-xs text-blue-500 hidden sm:inline">
        ({selectedOp.label})
      </span>
      
      {/* Remove Button */}
      {!readOnly && (
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => onRemove(condition.id)}
          className="text-blue-400 hover:text-red-500 hover:bg-red-50"
        >
          <Icons.close className="h-4 w-4" />
        </Button>
      )}
    </Reorder.Item>
  )
}

// ============================================================================
// Action Chip Component
// ============================================================================

function ActionChip({
  action,
  onUpdate,
  onRemove,
  readOnly,
}: {
  action: Action
  onUpdate: (id: string, value: string) => void
  onRemove: (id: string) => void
  readOnly?: boolean
}) {
  const actionDef = COMMON_ACTIONS.find(a => a.value === action.type)
  const hasValue = ['notify', 'add_tag', 'add_note', 'require_approval', 'set_priority', 'assign_team'].includes(action.type)

  return (
    <div className={cn(
      'inline-flex items-center gap-2 px-3 py-2 rounded-lg',
      'bg-emerald-50 border border-emerald-100'
    )}>
      <Icons.zap className="h-4 w-4 text-emerald-600" />
      <span className="font-medium text-emerald-700">
        {actionDef?.label || action.type}
      </span>
      
      {hasValue && (
        <input
          type="text"
          value={action.value || ''}
          onChange={(e) => onUpdate(action.id, e.target.value)}
          disabled={readOnly}
          placeholder="value..."
          className={cn(
            'px-2 py-0.5 rounded border border-emerald-200 bg-white text-sm text-emerald-800',
            'focus:outline-none focus:ring-2 focus:ring-emerald-300',
            'w-32'
          )}
        />
      )}
      
      {!readOnly && (
        <button
          onClick={() => onRemove(action.id)}
          className="text-emerald-400 hover:text-red-500 ml-1"
        >
          <Icons.close className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export function StructuredBuilder({ initialDSL, onChange, readOnly = false }: StructuredBuilderProps) {
  const [conditions, setConditions] = useState<Condition[]>(
    initialDSL?.conditions?.map((c, i) => ({
      id: `cond-${i}`,
      field: String(c.field || 'amount'),
      operator: String(c.operator || 'eq'),
      value: String(c.value ?? ''),
    })) || []
  )
  
  const [actions, setActions] = useState<Action[]>(
    initialDSL?.actions?.map((a, i) => ({
      id: `action-${i}`,
      type: String(a.type || 'auto_approve'),
      value: a.value ? String(a.value) : undefined,
    })) || []
  )
  
  const [matchMode, setMatchMode] = useState<'all' | 'any'>(initialDSL?.match_mode || 'all')
  const [showActionPicker, setShowActionPicker] = useState(false)

  // Notify parent of changes
  const notifyChange = useCallback((
    newConditions: Condition[],
    newActions: Action[],
    newMatchMode: 'all' | 'any'
  ) => {
    onChange?.({
      conditions: newConditions.map(c => ({
        id: c.id,
        field: c.field,
        operator: c.operator,
        value: c.value,
      })),
      actions: newActions.map(a => ({
        id: a.id,
        type: a.type,
        value: a.value,
      })),
      match_mode: newMatchMode,
    })
  }, [onChange])

  // Condition handlers
  const handleAddCondition = useCallback(() => {
    const newCondition: Condition = {
      id: generateId(),
      field: 'amount',
      operator: 'eq',
      value: '',
    }
    const newConditions = [...conditions, newCondition]
    setConditions(newConditions)
    notifyChange(newConditions, actions, matchMode)
  }, [conditions, actions, matchMode, notifyChange])

  const handleUpdateCondition = useCallback((id: string, field: keyof Condition, value: string) => {
    const newConditions = conditions.map(c => 
      c.id === id ? { ...c, [field]: value } : c
    )
    setConditions(newConditions)
    notifyChange(newConditions, actions, matchMode)
  }, [conditions, actions, matchMode, notifyChange])

  const handleRemoveCondition = useCallback((id: string) => {
    const newConditions = conditions.filter(c => c.id !== id)
    setConditions(newConditions)
    notifyChange(newConditions, actions, matchMode)
  }, [conditions, actions, matchMode, notifyChange])

  const handleReorderConditions = useCallback((newOrder: Condition[]) => {
    setConditions(newOrder)
    notifyChange(newOrder, actions, matchMode)
  }, [actions, matchMode, notifyChange])

  // Action handlers
  const handleAddAction = useCallback((type: string) => {
    const newAction: Action = {
      id: generateId(),
      type,
    }
    const newActions = [...actions, newAction]
    setActions(newActions)
    notifyChange(conditions, newActions, matchMode)
    setShowActionPicker(false)
  }, [actions, conditions, matchMode, notifyChange])

  const handleUpdateAction = useCallback((id: string, value: string) => {
    const newActions = actions.map(a => 
      a.id === id ? { ...a, value } : a
    )
    setActions(newActions)
    notifyChange(conditions, newActions, matchMode)
  }, [actions, conditions, matchMode, notifyChange])

  const handleRemoveAction = useCallback((id: string) => {
    const newActions = actions.filter(a => a.id !== id)
    setActions(newActions)
    notifyChange(conditions, newActions, matchMode)
  }, [actions, conditions, matchMode, notifyChange])

  // Match mode handler
  const handleMatchModeChange = useCallback((mode: 'all' | 'any') => {
    setMatchMode(mode)
    notifyChange(conditions, actions, mode)
  }, [conditions, actions, notifyChange])

  return (
    <div className="space-y-6">
      {/* Conditions Section */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Icons.filter className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-semibold text-blue-700">
              When these conditions are met
            </span>
          </div>
          
          {/* Match Mode Toggle */}
          {!readOnly && (
            <div className="flex items-center gap-1 bg-blue-100 rounded-lg p-0.5">
              <button
                onClick={() => handleMatchModeChange('all')}
                className={cn(
                  'px-3 py-1 text-xs font-semibold rounded-md transition-colors',
                  matchMode === 'all'
                    ? 'bg-white text-blue-700 shadow-sm'
                    : 'text-blue-500 hover:text-blue-700'
                )}
              >
                Match ALL
              </button>
              <button
                onClick={() => handleMatchModeChange('any')}
                className={cn(
                  'px-3 py-1 text-xs font-semibold rounded-md transition-colors',
                  matchMode === 'any'
                    ? 'bg-white text-blue-700 shadow-sm'
                    : 'text-blue-500 hover:text-blue-700'
                )}
              >
                Match ANY
              </button>
            </div>
          )}
        </div>

        <Reorder.Group
          axis="y"
          values={conditions}
          onReorder={handleReorderConditions}
          className="space-y-2"
        >
          <AnimatePresence>
            {conditions.map((condition, idx) => (
              <ConditionRow
                key={condition.id}
                condition={condition}
                index={idx}
                onUpdate={handleUpdateCondition}
                onRemove={handleRemoveCondition}
                readOnly={readOnly}
              />
            ))}
          </AnimatePresence>
        </Reorder.Group>

        {!readOnly && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleAddCondition}
            className="mt-3 border-dashed border-blue-300 text-blue-600 hover:bg-blue-50"
          >
            <Icons.plus className="mr-1.5 h-4 w-4" />
            Add Condition
          </Button>
        )}
      </div>

      {/* Actions Section */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Icons.zap className="h-4 w-4 text-emerald-600" />
          <span className="text-sm font-semibold text-emerald-700">
            Then perform these actions
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {actions.map(action => (
            <ActionChip
              key={action.id}
              action={action}
              onUpdate={handleUpdateAction}
              onRemove={handleRemoveAction}
              readOnly={readOnly}
            />
          ))}
          
          {!readOnly && (
            <div className="relative">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowActionPicker(!showActionPicker)}
                className="border-dashed border-emerald-300 text-emerald-600 hover:bg-emerald-50"
              >
                <Icons.plus className="mr-1.5 h-4 w-4" />
                Add Action
              </Button>
              
              {/* Action Picker Dropdown */}
              <AnimatePresence>
                {showActionPicker && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className={cn(
                      'absolute top-full left-0 mt-2 z-50',
                      'bg-white rounded-lg shadow-lg border border-gray-200',
                      'p-2 min-w-[200px] max-h-[300px] overflow-y-auto'
                    )}
                  >
                    {COMMON_ACTIONS.map(action => (
                      <button
                        key={action.value}
                        onClick={() => handleAddAction(action.value)}
                        className={cn(
                          'w-full flex items-center gap-2 px-3 py-2 rounded-md text-left text-sm',
                          'hover:bg-emerald-50 text-gray-700 hover:text-emerald-700',
                          'transition-colors'
                        )}
                      >
                        <Icons.zap className="h-4 w-4 text-emerald-500" />
                        {action.label}
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

