'use client'

import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Icons } from '@/components/ui/icons'

interface Capability {
  icon: React.ElementType
  label: string
  query: string
}

const CAPABILITIES: Capability[] = [
  { icon: Icons.helpCircle, label: 'What can you help me with?', query: 'What can you help me with?' },
  { icon: Icons.activity, label: 'Show recent activity', query: 'Show me recent activity' },
  { icon: Icons.fileText, label: 'Generate a report', query: 'Generate a report' },
  { icon: Icons.brain, label: 'Create a policy', query: 'Help me create a new policy' },
  { icon: Icons.lightbulb, label: 'Show insights', query: 'Show me AI insights' },
  { icon: Icons.info, label: 'Explain this page', query: 'Explain this page to me' },
]

interface CapabilityBubblesProps {
  onSelect: (query: string) => void
}

export function CapabilityBubbles({ onSelect }: CapabilityBubblesProps) {
  return (
    <div className="flex flex-wrap justify-center gap-2 p-2">
      {CAPABILITIES.map((cap, i) => {
        const Icon = cap.icon
        return (
          <motion.button
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06, duration: 0.25, ease: 'easeOut' }}
            onClick={() => onSelect(cap.query)}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-full',
              'bg-white border border-brand-cornflower/20',
              'text-sm text-brand-navy',
              'shadow-sm',
              'transition-all duration-200',
              'hover:bg-brand-cornflower/10 hover:border-brand-cornflower/40 hover:shadow-md',
              'focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50'
            )}
          >
            <Icon className="h-4 w-4 text-brand-cornflower" strokeWidth={1.5} />
            <span className="text-xs sm:text-sm font-medium">{cap.label}</span>
          </motion.button>
        )
      })}
    </div>
  )
}

