'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
import { Command } from 'cmdk'
import { cn } from '@/lib/utils'
import { Icons } from '@/components/ui/icons'
import { Dialog, DialogContent } from '@/components/ui/dialog'

interface CommandPaletteProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

// Recent items (would come from localStorage/state in real app)
const recentItems = [
  { id: 'recent-1', label: 'Dashboard', icon: Icons.dashboard, href: '/' },
  {
    id: 'recent-2',
    label: 'Run Diagnostics',
    icon: Icons.activity,
    action: 'diagnostics',
  },
]

// Navigation items
const navigationItems = [
  {
    id: 'dashboard',
    label: 'Go to Dashboard',
    icon: Icons.dashboard,
    href: '/',
  },
  {
    id: 'workbench',
    label: 'Go to Workbench',
    icon: Icons.workbench,
    href: '/workbench',
  },
  {
    id: 'ai-policies',
    label: 'Go to AI Policies',
    icon: Icons.brain,
    href: '/ai/policies',
  },
  {
    id: 'ai-insights',
    label: 'Go to AI Insights',
    icon: Icons.lightbulb,
    href: '/ai/insights',
  },
  {
    id: 'settings',
    label: 'Go to Settings',
    icon: Icons.settings,
    href: '/settings',
  },
  {
    id: 'brand',
    label: 'Go to Brand & Design',
    icon: Icons.palette,
    href: '/brand',
  },
]

// Action items
const actionItems = [
  {
    id: 'new-task',
    label: 'Create New Task',
    icon: Icons.plus,
    action: 'new-task',
  },
  {
    id: 'run-diagnostics',
    label: 'Run Diagnostics',
    icon: Icons.activity,
    action: 'diagnostics',
  },
  {
    id: 'refresh',
    label: 'Refresh Data',
    icon: Icons.refresh,
    action: 'refresh',
  },
]

// Settings items
const settingsItems = [
  {
    id: 'settings',
    label: 'Open Settings',
    icon: Icons.settings,
    href: '/settings',
  },
  { id: 'help', label: 'Help & Support', icon: Icons.help, action: 'help' },
]

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = React.useState<T>(value)

  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(handler)
    }
  }, [value, delay])

  return debouncedValue
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const [isOpen, setIsOpen] = React.useState(false)
  const [search, setSearch] = React.useState('')
  const debouncedSearch = useDebounce(search, 150)
  const router = useRouter()
  const inputRef = React.useRef<HTMLInputElement>(null)

  const controlledOpen = open !== undefined ? open : isOpen
  const setControlledOpen = onOpenChange || setIsOpen

  // Keyboard shortcut handler
  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      // Cmd+K or Ctrl+K to toggle
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setControlledOpen(!controlledOpen)
      }
    }

    document.addEventListener('keydown', down)
    return () => document.removeEventListener('keydown', down)
  }, [controlledOpen, setControlledOpen])

  // Focus input when opened and clear search when closed
  React.useEffect(() => {
    if (controlledOpen) {
      // Small delay to ensure element is rendered
      setTimeout(() => {
        inputRef.current?.focus()
      }, 0)
    } else {
      setSearch('')
    }
  }, [controlledOpen])

  const handleSelect = (item: { href?: string; action?: string }) => {
    setControlledOpen(false)
    setSearch('')

    if (item.href) {
      router.push(item.href)
    } else if (item.action) {
      // Handle actions
      switch (item.action) {
        case 'refresh':
          window.location.reload()
          break
        case 'diagnostics':
          // TODO: Implement diagnostics action
          break
        case 'help':
          // TODO: Implement help action
          break
      }
    }
  }

  return (
    <Dialog open={controlledOpen} onOpenChange={setControlledOpen}>
      <DialogContent className='overflow-hidden p-0 sm:max-w-xl [&>button]:hidden'>
        <Command
          className={cn(
            'rounded-xl',
            'bg-white/95 backdrop-blur-xl',
            'overflow-hidden'
          )}
          loop
        >
          {/* Search Input */}
          <div className='flex items-center border-b border-border/50 px-4'>
            <Icons.search className='h-4 w-4 shrink-0 text-muted-foreground' />
            <Command.Input
              ref={inputRef}
              value={search}
              onValueChange={setSearch}
              placeholder='Type a command or search...'
              className={cn(
                'h-14 flex-1 px-3',
                'bg-transparent text-foreground',
                'placeholder:text-muted-foreground',
                'focus:outline-none'
              )}
            />
            <kbd className='hidden h-6 items-center rounded border border-border/50 bg-muted/50 px-2 text-xs text-muted-foreground sm:inline-flex'>
              ESC
            </kbd>
          </div>

          {/* Results */}
          <Command.List
            className='max-h-[300px] overflow-y-auto p-2'
            aria-live='polite'
          >
            <Command.Empty className='py-6 text-center text-sm text-muted-foreground'>
              No results found.
            </Command.Empty>

            {/* Recent - only show when no search */}
            {!debouncedSearch && (
              <Command.Group
                heading='Recent'
                className='px-2 py-1.5 text-xs font-semibold text-muted-foreground'
              >
                {recentItems.map((item) => (
                  <Command.Item
                    key={item.id}
                    value={`recent-${item.label}`}
                    onSelect={() => handleSelect(item)}
                    className={cn(
                      'flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5',
                      'text-sm text-foreground',
                      'aria-selected:bg-brand-navy aria-selected:text-white',
                      'transition-colors'
                    )}
                  >
                    <Icons.clock
                      className='h-4 w-4 text-muted-foreground'
                      strokeWidth={1.5}
                    />
                    <item.icon className='h-4 w-4' strokeWidth={1.5} />
                    <span>{item.label}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            {/* Navigation */}
            <Command.Group
              heading='Navigation'
              className='px-2 py-1.5 text-xs font-semibold text-muted-foreground'
            >
              {navigationItems.map((item) => (
                <Command.Item
                  key={item.id}
                  value={item.label}
                  onSelect={() => handleSelect(item)}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5',
                    'text-sm text-foreground',
                    'aria-selected:bg-brand-navy aria-selected:text-white',
                    'transition-colors'
                  )}
                >
                  <item.icon className='h-4 w-4' strokeWidth={1.5} />
                  <span>{item.label}</span>
                </Command.Item>
              ))}
            </Command.Group>

            {/* Actions */}
            <Command.Group
              heading='Actions'
              className='px-2 py-1.5 text-xs font-semibold text-muted-foreground'
            >
              {actionItems.map((item) => (
                <Command.Item
                  key={item.id}
                  value={item.label}
                  onSelect={() => handleSelect(item)}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5',
                    'text-sm text-foreground',
                    'aria-selected:bg-brand-navy aria-selected:text-white',
                    'transition-colors'
                  )}
                >
                  <item.icon className='h-4 w-4' strokeWidth={1.5} />
                  <span>{item.label}</span>
                </Command.Item>
              ))}
            </Command.Group>

            {/* Settings */}
            <Command.Group
              heading='Settings'
              className='px-2 py-1.5 text-xs font-semibold text-muted-foreground'
            >
              {settingsItems.map((item) => (
                <Command.Item
                  key={item.id}
                  value={item.label}
                  onSelect={() => handleSelect(item)}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5',
                    'text-sm text-foreground',
                    'aria-selected:bg-brand-navy aria-selected:text-white',
                    'transition-colors'
                  )}
                >
                  <item.icon className='h-4 w-4' strokeWidth={1.5} />
                  <span>{item.label}</span>
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>

          {/* Footer */}
          <div className='flex items-center justify-between border-t border-border/50 px-4 py-2 text-xs text-muted-foreground'>
            <div className='flex items-center gap-4'>
              <span className='flex items-center gap-1'>
                <kbd className='rounded border border-border/50 bg-muted/50 px-1'>
                  ↑↓
                </kbd>
                Navigate
              </span>
              <span className='flex items-center gap-1'>
                <kbd className='rounded border border-border/50 bg-muted/50 px-1'>
                  ↵
                </kbd>
                Select
              </span>
            </div>
            <span className='flex items-center gap-1'>
              <kbd className='rounded border border-border/50 bg-muted/50 px-1'>
                ESC
              </kbd>
              Close
            </span>
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  )
}

