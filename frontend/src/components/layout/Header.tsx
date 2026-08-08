'use client'

import React from 'react'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Avatar } from '@/components/ui/avatar'
import { Icons } from '@/components/ui/icons'
import { useAI } from '@/context/AIContext'
import { NotificationCenter } from '@/components/NotificationCenter'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

// Breadcrumb helper
function getBreadcrumbs(pathname: string): { label: string; href: string }[] {
  const segments = pathname.split('/').filter(Boolean)

  if (segments.length === 0) {
    return [{ label: 'Dashboard', href: '/' }]
  }

  const breadcrumbs = [{ label: 'Dashboard', href: '/' }]

  let currentPath = ''
  segments.forEach((segment) => {
    currentPath += `/${segment}`
    const label =
      segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, ' ')
    breadcrumbs.push({ label, href: currentPath })
  })

  return breadcrumbs
}

// Search input component
function SearchInput({
  onOpenCommandPalette,
}: {
  onOpenCommandPalette?: () => void
}) {
  return (
    <button
      onClick={onOpenCommandPalette}
      className={cn(
        'group flex h-9 w-64 items-center gap-2 px-3',
        'rounded-full border border-border/50 bg-white/50',
        'text-sm text-muted-foreground',
        'transition-all duration-300 ease-out',
        'hover:border-brand-cornflower/40 hover:bg-white/90 hover:shadow-sm',
        'hover:w-72',
        'focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50'
      )}
    >
      <Icons.search
        className='h-4 w-4 transition-transform duration-200 group-hover:scale-110'
        strokeWidth={1.5}
      />
      <span className='flex-1 text-left'>Search...</span>
      <kbd
        className={cn(
          'hidden h-5 items-center gap-1 rounded px-1.5 sm:inline-flex',
          'text-[10px] font-medium',
          'border border-border/50 bg-muted/50 text-muted-foreground',
          'transition-all duration-200',
          'group-hover:border-brand-cornflower/30 group-hover:bg-brand-cornflower/10 group-hover:text-brand-navy'
        )}
      >
        <Icons.command className='h-3 w-3' />K
      </kbd>
    </button>
  )
}

// AI Manager trigger button - styled as a prominent tag/badge
function AIManagerTrigger() {
  const { openManager, isManagerOpen } = useAI()

  return (
    <TooltipProvider>
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          <button
            onClick={openManager}
            className={cn(
              'relative flex items-center gap-2 px-3 py-1.5',
              'rounded-full',
              'text-sm font-medium',
              'transition-all duration-200',
              'bg-gradient-to-r from-brand-navy to-brand-purple',
              'text-white',
              'shadow-md shadow-brand-navy/20',
              'hover:shadow-lg hover:shadow-brand-purple/30',
              'hover:scale-[1.02]',
              isManagerOpen && 'ring-2 ring-brand-cornflower ring-offset-2',
              'focus:outline-none focus:ring-2 focus:ring-brand-cornflower focus:ring-offset-2'
            )}
            aria-label='Open AI Manager'
          >
            <Icons.sparkles
              className='h-4 w-4 text-white'
              strokeWidth={1.5}
            />
            <span className='hidden sm:inline'>AI Manager</span>
            <kbd className={cn(
              'hidden sm:inline-flex items-center gap-0.5',
              'px-1.5 py-0.5 rounded',
              'bg-white/20 text-white/90',
              'text-[10px] font-medium'
            )}>
              <Icons.command className='h-2.5 w-2.5' />J
            </kbd>
          </button>
        </TooltipTrigger>
        <TooltipContent side='bottom' className='sm:hidden'>
          <span>AI Manager</span>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

// User menu with dropdown
function UserMenu() {
  const user = { name: 'Dev User', email: 'dev@autopilot.local' }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            'group flex items-center gap-1 rounded-full',
            'focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50 focus:ring-offset-2',
            'transition-transform duration-200'
          )}
        >
          <div className='flex items-center gap-3'>
            <div className='hidden flex-col text-right lg:flex'>
              <span className='text-sm font-medium text-foreground'>
                {user.name}
              </span>
              <span className='text-xs text-muted-foreground'>
                {user.email}
              </span>
            </div>
            <Avatar
              fallback={user.name}
              size='md'
              showRing
            />
            <Icons.chevronDown
              className={cn(
                'h-4 w-4 text-muted-foreground transition-transform duration-200',
                'group-data-[state=open]:rotate-180 group-hover:translate-y-0.5'
              )}
            />
          </div>
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align='end' className='w-64'>
        <div className='border-b border-border/50 px-3 py-3'>
          <div className='flex items-center gap-3'>
            <Avatar
              fallback={user.name}
              size='md'
            />
            <div className='min-w-0 flex-1'>
              <p className='truncate text-sm font-medium text-foreground'>
                {user.name}
              </p>
              <p className='truncate text-xs text-muted-foreground'>
                {user.email}
              </p>
            </div>
          </div>
        </div>

        <div className='py-1'>
          <DropdownMenuItem className='gap-3 rounded-lg px-3 py-2.5'>
            <Icons.user className='h-4 w-4 text-muted-foreground' strokeWidth={1.5} />
            <span>Profile</span>
          </DropdownMenuItem>
          <DropdownMenuItem className='gap-3 rounded-lg px-3 py-2.5'>
            <Icons.settings className='h-4 w-4 text-muted-foreground' strokeWidth={1.5} />
            <span>Settings</span>
          </DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

interface HeaderProps {
  onOpenMobileMenu?: () => void
}

export function Header({ onOpenMobileMenu }: HeaderProps) {
  const pathname = usePathname()
  const breadcrumbs = getBreadcrumbs(pathname)

  return (
    <header
      role='banner'
      className={cn(
        // Floating pill positioning
        'fixed right-4 top-4 z-sticky',
        // Adjust left position based on sidebar (hidden on mobile)
        'left-4 md:left-[calc(16rem+1rem)]',
        // Glass pill styling
        'rounded-2xl bg-white/70 backdrop-blur-xl',
        'border border-white/60 ring-1 ring-black/[0.03]',
        'shadow-float',
        // Layout
        'flex items-center justify-between',
        'h-14 px-4 lg:px-6'
      )}
    >
      {/* Left: Mobile menu + Breadcrumb */}
      <div className='flex items-center gap-2'>
        {/* Mobile menu button */}
        <Button
          variant='ghost'
          size='icon-sm'
          onClick={onOpenMobileMenu}
          className='-ml-1 text-muted-foreground hover:text-foreground md:hidden'
          aria-label='Open navigation menu'
        >
          <Icons.menu className='h-5 w-5' strokeWidth={1.5} />
        </Button>

        <Icons.home
          className='hidden h-4 w-4 text-muted-foreground md:block'
          strokeWidth={1.5}
        />
        <nav
          aria-label='Breadcrumb'
          className='hidden items-center gap-1 text-sm sm:flex'
        >
          {breadcrumbs.map((crumb, index) => (
            <React.Fragment key={crumb.href}>
              {index > 0 && (
                <Icons.chevronRight
                  className='h-4 w-4 text-muted-foreground/50'
                  aria-hidden='true'
                />
              )}
              <span
                className={cn(
                  index === breadcrumbs.length - 1
                    ? 'font-medium text-foreground'
                    : 'cursor-pointer text-muted-foreground hover:text-foreground'
                )}
                aria-current={
                  index === breadcrumbs.length - 1 ? 'page' : undefined
                }
              >
                {crumb.label}
              </span>
            </React.Fragment>
          ))}
        </nav>
        {/* Mobile: Just show current page */}
        <span className='text-sm font-medium text-foreground sm:hidden'>
          {breadcrumbs[breadcrumbs.length - 1].label}
        </span>
      </div>

      {/* Right: Actions */}
      <div className='flex items-center gap-1 sm:gap-2'>
        {/* Search */}
        <div className='hidden lg:block'>
          <SearchInput />
        </div>

        {/* Mobile/tablet search button */}
        <Button
          variant='ghost'
          size='icon-sm'
          className='text-muted-foreground hover:text-foreground lg:hidden'
          aria-label='Search'
        >
          <Icons.search className='h-5 w-5' strokeWidth={1.5} />
        </Button>

        {/* AI Manager */}
        <AIManagerTrigger />

        {/* Notifications */}
        <NotificationCenter />

        {/* Divider */}
        <div className='mx-1 hidden h-6 w-px bg-border/60 lg:block' />

        {/* User menu */}
        <UserMenu />
      </div>
    </header>
  )
}
