import type { ReactNode } from 'react'

interface PageHeaderProps {
  eyebrow?: string
  title: string
  description: string
  actions?: ReactNode
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: PageHeaderProps) {
  return (
    <div className='flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between'>
      <div className='max-w-3xl'>
        {eyebrow && (
          <p className='text-micro uppercase text-brand-cornflower'>{eyebrow}</p>
        )}
        <h1 className='mt-1 text-display-3 font-bold tracking-tight text-brand-navy'>
          {title}
        </h1>
        <p className='mt-2 text-base text-muted-foreground'>{description}</p>
      </div>
      {actions && <div className='flex flex-wrap gap-2'>{actions}</div>}
    </div>
  )
}
