import React from 'react'
import Image from 'next/image'
import { cn } from '@/lib/utils'

interface LogomarkProps {
  className?: string
  /**
   * 'dark' uses the navy logomark (for light backgrounds)
   * 'light' uses the white logomark (for dark backgrounds)
   */
  variant?: 'dark' | 'light'
  size?: number
}

/**
 * The AutoPilot "S" logomark.
 * Use `variant="dark"` on light backgrounds, `variant="light"` on dark backgrounds.
 */
export function Logomark({
  className,
  variant = 'dark',
  size = 40,
}: LogomarkProps) {
  const src =
    variant === 'light'
      ? '/logos/logomark-light.svg'
      : '/logos/logomark-dark.svg'

  return (
    <Image
      src={src}
      alt='AutoPilot'
      width={size}
      height={size}
      className={cn('shrink-0', className)}
      priority
    />
  )
}

