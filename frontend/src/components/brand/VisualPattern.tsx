'use client'

import React from 'react'
import { cn } from '@/lib/utils'

interface VisualPatternProps {
  className?: string
  variant?: 'default' | 'subtle' | 'hero'
}

/**
 * Ambient light blobs for the "Luminous" aesthetic.
 * Refined for light mode with soft pastels and gentle movement.
 */
export function VisualPattern({
  className,
  variant = 'default',
}: VisualPatternProps) {
  const opacityClass = {
    default: 'opacity-20',
    subtle: 'opacity-10',
    hero: 'opacity-30',
  }[variant]

  return (
    <div
      className={cn(
        'pointer-events-none fixed inset-0 -z-10 overflow-hidden',
        className
      )}
      aria-hidden='true'
    >
      <div className={cn('relative h-full w-full', opacityClass)}>
        {/* 
          BLOB 1: Top Right - Soft Cornflower
          Creates ambient "skylight" effect
        */}
        <div
          className={cn(
            'absolute -right-[10%] -top-[20%]',
            'h-[600px] w-[600px] lg:h-[800px] lg:w-[800px]',
            'rounded-full',
            'bg-brand-cornflower/50',
            'blur-[150px]',
            'animate-blob'
          )}
        />

        {/* 
          BLOB 2: Bottom Left - Soft Purple
          Creates depth and warmth
        */}
        <div
          className={cn(
            'absolute -bottom-[20%] -left-[10%]',
            'h-[500px] w-[500px] lg:h-[700px] lg:w-[700px]',
            'rounded-full',
            'bg-brand-purple/30',
            'blur-[150px]',
            'animate-blob-delayed'
          )}
        />

        {/* 
          BLOB 3: Center - Very subtle accent
          Adds subtle vibrancy to center of screen
        */}
        <div
          className={cn(
            'absolute left-[40%] top-[30%]',
            'h-[400px] w-[400px]',
            'rounded-full',
            'bg-brand-cornflower/20',
            'blur-[120px]',
            'animate-float'
          )}
        />
      </div>
    </div>
  )
}

