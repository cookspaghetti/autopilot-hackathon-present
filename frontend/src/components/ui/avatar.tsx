'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string | null
  alt?: string
  fallback?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  showStatus?: boolean
  status?: 'online' | 'offline' | 'away' | 'busy'
  showRing?: boolean
}

const sizeClasses = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-14 w-14 text-lg',
  xl: 'h-20 w-20 text-xl',
}

const statusSizeClasses = {
  sm: 'h-2.5 w-2.5 border-[1.5px]',
  md: 'h-3 w-3 border-2',
  lg: 'h-4 w-4 border-2',
  xl: 'h-5 w-5 border-[3px]',
}

const statusColors = {
  online: 'bg-emerald-500',
  offline: 'bg-gray-400',
  away: 'bg-amber-500',
  busy: 'bg-red-500',
}

function getInitials(name: string): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) {
    return parts[0].substring(0, 2).toUpperCase()
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  (
    {
      className,
      src,
      alt = '',
      fallback,
      size = 'md',
      showStatus = false,
      status = 'offline',
      showRing = false,
      ...props
    },
    ref
  ) => {
    const [hasError, setHasError] = React.useState(false)
    const initials = fallback ? getInitials(fallback) : '?'

    return (
      <div
        ref={ref}
        className={cn('relative inline-flex shrink-0', className)}
        {...props}
      >
        {/* Ring container */}
        <div
          className={cn(
            'rounded-full',
            showRing && [
              'p-[2px]',
              'bg-gradient-to-br from-brand-navy via-brand-purple to-brand-cornflower',
            ]
          )}
        >
          {/* Avatar container */}
          <div
            className={cn(
              'relative flex items-center justify-center overflow-hidden rounded-full',
              'bg-gradient-to-br from-brand-navy to-brand-purple',
              'font-medium text-white',
              sizeClasses[size],
              showRing && 'ring-2 ring-white'
            )}
          >
            {src && !hasError ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={src}
                alt={alt}
                className='h-full w-full object-cover'
                onError={() => setHasError(true)}
              />
            ) : (
              <span className='select-none'>{initials}</span>
            )}
          </div>
        </div>

        {/* Status indicator */}
        {showStatus && (
          <span
            className={cn(
              'absolute bottom-0 right-0 rounded-full border-white',
              statusSizeClasses[size],
              statusColors[status],
              // Pulse animation for online status
              status === 'online' &&
                'after:absolute after:inset-0 after:animate-pulse-ring after:rounded-full after:bg-emerald-500'
            )}
          />
        )}
      </div>
    )
  }
)
Avatar.displayName = 'Avatar'

// Avatar group for showing multiple avatars stacked
interface AvatarGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  max?: number
  size?: 'sm' | 'md' | 'lg'
}

const AvatarGroup = React.forwardRef<HTMLDivElement, AvatarGroupProps>(
  ({ className, children, max = 4, size = 'md', ...props }, ref) => {
    const childArray = React.Children.toArray(children)
    const visibleAvatars = childArray.slice(0, max)
    const remainingCount = childArray.length - max

    return (
      <div ref={ref} className={cn('flex -space-x-2', className)} {...props}>
        {visibleAvatars.map((child, index) => (
          <div key={index} className='relative' style={{ zIndex: max - index }}>
            {child}
          </div>
        ))}
        {remainingCount > 0 && (
          <div
            className={cn(
              'relative flex items-center justify-center rounded-full',
              'bg-muted font-medium text-muted-foreground',
              'border-2 border-white',
              sizeClasses[size]
            )}
            style={{ zIndex: 0 }}
          >
            +{remainingCount}
          </div>
        )}
      </div>
    )
  }
)
AvatarGroup.displayName = 'AvatarGroup'

export { Avatar, AvatarGroup }
