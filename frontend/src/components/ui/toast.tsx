'use client'

import { Toaster, toast as hotToast } from 'react-hot-toast'
import { cn } from '@/lib/utils'
import { Icons } from './icons'

// Custom toast styling to match brand
export function ToastProvider() {
  return (
    <Toaster
      position='bottom-right'
      gutter={12}
      containerStyle={{
        bottom: 24,
        right: 24,
      }}
      toastOptions={{
        duration: 4000,
        style: {
          padding: '16px',
          borderRadius: '16px',
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 8px 30px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.03)',
          color: '#141A42',
          fontSize: '14px',
          maxWidth: '400px',
        },
        success: {
          iconTheme: {
            primary: '#10B981',
            secondary: '#FFFFFF',
          },
        },
        error: {
          iconTheme: {
            primary: '#EF4444',
            secondary: '#FFFFFF',
          },
        },
      }}
    />
  )
}

// Custom toast functions with brand styling
export const toast = {
  // Basic toasts
  success: (message: string, options?: { description?: string }) => {
    hotToast.custom(
      (t) => (
        <div
          className={cn(
            'flex items-start gap-3 rounded-2xl p-4',
            'bg-white/95 backdrop-blur-xl',
            'border border-white/60 ring-1 ring-black/[0.03]',
            'shadow-float',
            t.visible ? 'animate-slide-in-right' : 'animate-fade-out'
          )}
        >
          <div className='flex-shrink-0 rounded-lg bg-emerald-500/10 p-1.5'>
            <Icons.checkCircle
              className='h-5 w-5 text-emerald-500'
              strokeWidth={1.5}
            />
          </div>
          <div className='min-w-0 flex-1'>
            <p className='text-sm font-medium text-foreground'>{message}</p>
            {options?.description && (
              <p className='mt-1 text-xs text-muted-foreground'>
                {options.description}
              </p>
            )}
          </div>
          <button
            onClick={() => hotToast.dismiss(t.id)}
            className='flex-shrink-0 rounded-lg p-1 transition-colors hover:bg-black/[0.04]'
          >
            <Icons.close className='h-4 w-4 text-muted-foreground' />
          </button>
        </div>
      ),
      { duration: 4000 }
    )
  },

  error: (message: string, options?: { description?: string }) => {
    hotToast.custom(
      (t) => (
        <div
          className={cn(
            'flex items-start gap-3 rounded-2xl p-4',
            'bg-white/95 backdrop-blur-xl',
            'border border-white/60 ring-1 ring-black/[0.03]',
            'shadow-float',
            t.visible ? 'animate-slide-in-right' : 'animate-fade-out'
          )}
        >
          <div className='flex-shrink-0 rounded-lg bg-red-500/10 p-1.5'>
            <Icons.alertCircle
              className='h-5 w-5 text-red-500'
              strokeWidth={1.5}
            />
          </div>
          <div className='min-w-0 flex-1'>
            <p className='text-sm font-medium text-foreground'>{message}</p>
            {options?.description && (
              <p className='mt-1 text-xs text-muted-foreground'>
                {options.description}
              </p>
            )}
          </div>
          <button
            onClick={() => hotToast.dismiss(t.id)}
            className='flex-shrink-0 rounded-lg p-1 transition-colors hover:bg-black/[0.04]'
          >
            <Icons.close className='h-4 w-4 text-muted-foreground' />
          </button>
        </div>
      ),
      { duration: 5000 }
    )
  },

  warning: (message: string, options?: { description?: string }) => {
    hotToast.custom(
      (t) => (
        <div
          className={cn(
            'flex items-start gap-3 rounded-2xl p-4',
            'bg-white/95 backdrop-blur-xl',
            'border border-white/60 ring-1 ring-black/[0.03]',
            'shadow-float',
            t.visible ? 'animate-slide-in-right' : 'animate-fade-out'
          )}
        >
          <div className='flex-shrink-0 rounded-lg bg-amber-500/10 p-1.5'>
            <Icons.alertTriangle
              className='h-5 w-5 text-amber-500'
              strokeWidth={1.5}
            />
          </div>
          <div className='min-w-0 flex-1'>
            <p className='text-sm font-medium text-foreground'>{message}</p>
            {options?.description && (
              <p className='mt-1 text-xs text-muted-foreground'>
                {options.description}
              </p>
            )}
          </div>
          <button
            onClick={() => hotToast.dismiss(t.id)}
            className='flex-shrink-0 rounded-lg p-1 transition-colors hover:bg-black/[0.04]'
          >
            <Icons.close className='h-4 w-4 text-muted-foreground' />
          </button>
        </div>
      ),
      { duration: 4000 }
    )
  },

  info: (message: string, options?: { description?: string }) => {
    hotToast.custom(
      (t) => (
        <div
          className={cn(
            'flex items-start gap-3 rounded-2xl p-4',
            'bg-white/95 backdrop-blur-xl',
            'border border-white/60 ring-1 ring-black/[0.03]',
            'shadow-float',
            t.visible ? 'animate-slide-in-right' : 'animate-fade-out'
          )}
        >
          <div className='flex-shrink-0 rounded-lg bg-brand-cornflower/20 p-1.5'>
            <Icons.info
              className='h-5 w-5 text-brand-cornflower'
              strokeWidth={1.5}
            />
          </div>
          <div className='min-w-0 flex-1'>
            <p className='text-sm font-medium text-foreground'>{message}</p>
            {options?.description && (
              <p className='mt-1 text-xs text-muted-foreground'>
                {options.description}
              </p>
            )}
          </div>
          <button
            onClick={() => hotToast.dismiss(t.id)}
            className='flex-shrink-0 rounded-lg p-1 transition-colors hover:bg-black/[0.04]'
          >
            <Icons.close className='h-4 w-4 text-muted-foreground' />
          </button>
        </div>
      ),
      { duration: 4000 }
    )
  },

  // Loading toast with promise support
  promise: hotToast.promise,

  // Dismiss
  dismiss: hotToast.dismiss,
}

