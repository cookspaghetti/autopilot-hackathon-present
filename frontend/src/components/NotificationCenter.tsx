'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

// Notification types
type NotificationType = 'info' | 'success' | 'warning' | 'error'

interface Notification {
  id: string
  type: NotificationType
  title: string
  message: string
  timestamp: Date
  read: boolean
}

// Mock notifications - in real app, this would come from a store/API
const mockNotifications: Notification[] = [
  {
    id: '1',
    type: 'success',
    title: 'Diagnostics Complete',
    message: 'All systems are running normally.',
    timestamp: new Date(Date.now() - 5 * 60 * 1000), // 5 min ago
    read: false,
  },
  {
    id: '2',
    type: 'info',
    title: 'New Feature Available',
    message: 'Check out the new workbench improvements.',
    timestamp: new Date(Date.now() - 30 * 60 * 1000), // 30 min ago
    read: false,
  },
  {
    id: '3',
    type: 'warning',
    title: 'Token Expiring Soon',
    message: 'Your access token will expire in 24 hours.',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), // 2 hours ago
    read: true,
  },
]

const typeConfig: Record<
  NotificationType,
  { icon: React.ElementType; color: string; bg: string }
> = {
  info: { icon: Icons.info, color: 'text-blue-500', bg: 'bg-blue-500/10' },
  success: {
    icon: Icons.checkCircle,
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
  },
  warning: {
    icon: Icons.alertTriangle,
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
  },
  error: {
    icon: Icons.alertCircle,
    color: 'text-red-500',
    bg: 'bg-red-500/10',
  },
}

function formatRelativeTime(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

interface NotificationItemProps {
  notification: Notification
  onMarkAsRead: (id: string) => void
}

function NotificationItem({
  notification,
  onMarkAsRead,
}: NotificationItemProps) {
  const config = typeConfig[notification.type]
  const Icon = config.icon

  return (
    <div
      className={cn(
        'flex cursor-pointer gap-3 rounded-xl p-3',
        'transition-all duration-200 ease-out',
        'hover:scale-[1.02] active:scale-[0.98]',
        notification.read
          ? 'opacity-60 hover:opacity-100'
          : 'hover:bg-brand-cornflower/5 hover:shadow-sm'
      )}
      onClick={() => onMarkAsRead(notification.id)}
    >
      <div
        className={cn(
          'flex-shrink-0 rounded-lg p-2 transition-transform duration-200',
          config.bg,
          'group-hover:scale-110'
        )}
      >
        <Icon className={cn('h-4 w-4', config.color)} strokeWidth={1.5} />
      </div>
      <div className='min-w-0 flex-1'>
        <div className='flex items-start justify-between gap-2'>
          <p className='truncate text-sm font-medium text-foreground'>
            {notification.title}
          </p>
          {!notification.read && (
            <span className='mt-1.5 h-2 w-2 shrink-0 animate-pulse rounded-full bg-brand-cornflower' />
          )}
        </div>
        <p className='mt-0.5 line-clamp-2 text-xs text-muted-foreground'>
          {notification.message}
        </p>
        <p className='mt-1 text-[10px] text-muted-foreground/60'>
          {formatRelativeTime(notification.timestamp)}
        </p>
      </div>
    </div>
  )
}

export function NotificationCenter() {
  const [notifications, setNotifications] = React.useState(mockNotifications)

  const unreadCount = notifications.filter((n) => !n.read).length

  const markAsRead = (id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    )
  }

  const markAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant='ghost'
          size='icon'
          className='relative rounded-full text-muted-foreground hover:text-foreground'
        >
          <Icons.bell className='h-5 w-5' strokeWidth={1.5} />
          {unreadCount > 0 && (
            <span
              className={cn(
                'absolute -right-0.5 -top-0.5',
                'flex h-4 min-w-4 items-center justify-center',
                'rounded-full bg-destructive px-1',
                'text-[10px] font-semibold text-white',
                'animate-badge-bounce'
              )}
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align='end' className='w-80 p-0'>
        {/* Header */}
        <div className='flex items-center justify-between border-b border-border/50 px-4 py-3'>
          <h3 className='font-display font-semibold text-foreground'>
            Notifications
          </h3>
          {unreadCount > 0 && (
            <Button
              variant='link'
              size='sm'
              onClick={markAllAsRead}
              className='h-auto p-0 text-xs text-brand-cornflower'
            >
              Mark all as read
            </Button>
          )}
        </div>

        {/* Notification list */}
        <div className='max-h-[300px] overflow-y-auto p-2'>
          {notifications.length === 0 ? (
            <div className='py-8 text-center'>
              <div className='mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted/50'>
                <Icons.checkCircle className='h-6 w-6 text-muted-foreground' />
              </div>
              <p className='text-sm font-medium text-foreground'>
                All caught up!
              </p>
              <p className='mt-1 text-xs text-muted-foreground'>
                No new notifications
              </p>
            </div>
          ) : (
            <div className='space-y-1'>
              {notifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onMarkAsRead={markAsRead}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        {notifications.length > 0 && (
          <div className='border-t border-border/50 p-2'>
            <Button
              variant='ghost'
              className='w-full text-brand-navy'
            >
              View all notifications
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}

