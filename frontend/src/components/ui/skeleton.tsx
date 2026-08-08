import { cn } from '@/lib/utils'

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'text' | 'circular' | 'rectangular'
}

function Skeleton({ className, variant = 'default', ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        // Base shimmer effect
        'relative overflow-hidden',
        'bg-gradient-to-r from-muted via-muted/50 to-muted',
        'bg-[length:200%_100%]',
        'animate-shimmer',
        // Variants
        {
          'rounded-lg': variant === 'default' || variant === 'rectangular',
          'rounded-full': variant === 'circular',
          'h-4 rounded-md': variant === 'text',
        },
        className
      )}
      {...props}
    />
  )
}

// Pre-built skeleton variants for common use cases

function SkeletonText({
  lines = 3,
  className,
}: {
  lines?: number
  className?: string
}) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          variant='text'
          className={cn(
            'h-4',
            // Last line is shorter for natural look
            i === lines - 1 && 'w-3/4'
          )}
        />
      ))}
    </div>
  )
}

function SkeletonCard({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'space-y-4 rounded-2xl border border-border/50 bg-card p-6',
        className
      )}
    >
      {/* Header */}
      <div className='flex items-center justify-between'>
        <Skeleton variant='text' className='h-4 w-24' />
        <Skeleton variant='circular' className='h-10 w-10' />
      </div>
      {/* Value */}
      <Skeleton className='h-10 w-32' />
      {/* Footer */}
      <Skeleton variant='text' className='h-3 w-16' />
    </div>
  )
}

function SkeletonAvatar({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'h-8 w-8',
    md: 'h-10 w-10',
    lg: 'h-14 w-14',
  }

  return <Skeleton variant='circular' className={sizeClasses[size]} />
}

function SkeletonChart({ className }: { className?: string }) {
  return (
    <div className={cn('space-y-4', className)}>
      {/* Chart area */}
      <Skeleton className='h-[200px] w-full' />
      {/* Legend */}
      <div className='flex gap-4'>
        <Skeleton variant='text' className='h-3 w-16' />
        <Skeleton variant='text' className='h-3 w-16' />
        <Skeleton variant='text' className='h-3 w-16' />
      </div>
    </div>
  )
}

function SkeletonTable({
  rows = 5,
  cols = 4,
}: {
  rows?: number
  cols?: number
}) {
  return (
    <div className='space-y-3'>
      {/* Header */}
      <div className='flex gap-4 border-b border-border/50 pb-2'>
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} variant='text' className='h-4 flex-1' />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className='flex gap-4'>
          {Array.from({ length: cols }).map((_, colIndex) => (
            <Skeleton
              key={colIndex}
              variant='text'
              className={cn(
                'h-4 flex-1',
                // Vary widths for natural look
                colIndex === 0 && 'max-w-[120px]'
              )}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

export {
  Skeleton,
  SkeletonText,
  SkeletonCard,
  SkeletonAvatar,
  SkeletonChart,
  SkeletonTable,
}
