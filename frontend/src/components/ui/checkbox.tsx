'use client'

import * as React from 'react'
import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import { cn } from '@/lib/utils'
import { Icons } from './icons'

const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      'peer h-4 w-4 shrink-0 rounded border border-gray-300 ring-offset-background',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cornflower focus-visible:ring-offset-2',
      'disabled:cursor-not-allowed disabled:opacity-50',
      'data-[state=checked]:bg-brand-navy data-[state=checked]:border-brand-navy data-[state=checked]:text-white',
      className
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator
      className={cn('flex items-center justify-center text-current')}
    >
      <Icons.check className='h-3.5 w-3.5' />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
))
Checkbox.displayName = CheckboxPrimitive.Root.displayName

export { Checkbox }

