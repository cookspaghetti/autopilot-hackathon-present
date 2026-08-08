import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'
import { Icons } from './icons'

const buttonVariants = cva(
  // Base styles with micro-interactions
  [
    'inline-flex items-center justify-center gap-2',
    'whitespace-nowrap rounded-full text-sm font-medium',
    'ring-offset-background transition-all duration-200',
    // Focus ring with brand color
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cornflower/50 focus-visible:ring-offset-2',
    // Disabled state
    'disabled:pointer-events-none disabled:opacity-50',
    // Micro-interaction: tactile press feedback
    'active:scale-[0.98]',
  ],
  {
    variants: {
      variant: {
        default: [
          'bg-brand-navy text-white',
          'hover:bg-brand-navy-light',
          'shadow-soft hover:shadow-medium',
        ],
        destructive: [
          'bg-destructive text-destructive-foreground',
          'hover:bg-destructive/90',
        ],
        outline: [
          'border border-border bg-white',
          'hover:bg-secondary hover:border-brand-cornflower/30',
          'text-foreground',
        ],
        secondary: [
          'bg-secondary text-secondary-foreground',
          'hover:bg-secondary/80',
        ],
        ghost: [
          'hover:bg-black/[0.04]',
          'text-muted-foreground hover:text-foreground',
        ],
        link: ['text-brand-navy underline-offset-4', 'hover:underline'],
        // Gradient: Primary CTA with shimmer effect
        gradient: [
          'bg-gradient-to-r from-brand-navy to-brand-purple text-white',
          'hover:opacity-90 hover:shadow-accent',
          'shadow-medium border-0',
          'relative overflow-hidden',
          // Shimmer overlay on hover
          'before:absolute before:inset-0 before:translate-x-[-100%]',
          'before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent',
          'hover:before:translate-x-[100%] before:transition-transform before:duration-700',
        ],
        // Glass: For secondary actions on light backgrounds
        glass: [
          'bg-white/70 backdrop-blur-sm',
          'border border-white/60 ring-1 ring-black/[0.03]',
          'text-foreground',
          'hover:bg-white/90 hover:ring-brand-cornflower/20',
          'shadow-glass hover:shadow-glass-hover',
        ],
        // Accent: Cornflower blue for highlighted actions
        accent: [
          'bg-brand-cornflower text-brand-navy',
          'hover:bg-brand-cornflower-light',
          'shadow-soft hover:shadow-accent',
        ],
      },
      size: {
        default: 'h-10 px-6 py-2',
        sm: 'h-9 px-4 text-xs',
        lg: 'h-12 px-8 text-base',
        xl: 'h-14 px-10 text-lg',
        icon: 'h-10 w-10 p-0',
        'icon-sm': 'h-8 w-8 p-0',
        'icon-lg': 'h-12 w-12 p-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  loading?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      asChild = false,
      loading = false,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : 'button'

    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? (
          <>
            <Icons.loader className='h-4 w-4 animate-spin' />
            <span className='sr-only'>Loading...</span>
          </>
        ) : (
          children
        )}
      </Comp>
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
