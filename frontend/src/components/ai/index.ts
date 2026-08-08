/**
 * AI Components - Export all AI-related components
 */

// Main AI Manager
export { AIManager } from './AIManager'
export { ChatMessage } from './ChatMessage'
export { ChatInput } from './ChatInput'
export { CapabilityBubbles } from './CapabilityBubbles'
export { TeachAI } from './TeachAI'

// Policy Components - New
export { PolicyCard } from './policies/PolicyCard'
export type { Policy, PolicyDSL, PolicyCondition, PolicyAction } from './policies/PolicyCard'
export { PolicyDetailModal } from './policies/PolicyDetailModal'
export { PolicyEditModal } from './policies/PolicyEditModal'
export { CreateWithAI } from './policies/CreateWithAI'
export { StructuredBuilder } from './policies/StructuredBuilder'
export { PermissionMatrixTab } from './policies/PermissionMatrixTab'

// Policy Components - Legacy (used by TeachAI)
export { RuleBuilderModal } from './policies/RuleBuilderModal'
export type { RuleFormData, RuleAnalysis, RuleConflict, RuleOverride } from './policies/RuleBuilderModal'

// Insight Components
export { InsightCard } from './insights/InsightCard'
export { PatternCluster } from './insights/PatternCluster'
export { ActionCard } from './insights/ActionCard'

// Types and utilities
export type { Insight, InsightSeverity, InsightType } from './insights/InsightCard'
export { getSeverityConfig } from './insights/InsightCard'
export type { Pattern } from './insights/PatternCluster'
export type { ActionItem } from './insights/ActionCard'

