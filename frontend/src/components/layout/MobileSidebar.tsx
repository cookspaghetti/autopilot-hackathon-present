'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Logomark } from '@/components/brand'
import { Icons } from '@/components/ui/icons'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'

// Navigation items configuration
const navItems = [
  {
    title: 'Platform',
    items: [
      { href: '/', label: 'Dashboard', icon: Icons.dashboard },
      { href: '/workbench', label: 'Workbench', icon: Icons.workbench },
    ],
  },
  {
    title: 'System',
    items: [
      { href: '/settings', label: 'Settings', icon: Icons.settings },
    ],
  },
]

interface NavLinkProps {
  href: string
  icon: React.ElementType
  children: React.ReactNode
  onClick?: () => void
}

function NavLink({ href, icon: Icon, children, onClick }: NavLinkProps) {
  const pathname = usePathname()
  const isActive = pathname === href

  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        'flex items-center gap-3 rounded-xl px-4 py-3',
        'text-base font-medium transition-all duration-200',
        isActive
          ? 'bg-brand-navy text-white'
          : 'text-brand-muted hover:bg-black/[0.04] hover:text-brand-navy'
      )}
    >
      <Icon
        strokeWidth={1.5}
        className={cn(
          'h-5 w-5 shrink-0',
          isActive ? 'text-white' : 'text-brand-muted'
        )}
      />
      <span>{children}</span>
    </Link>
  )
}

interface MobileSidebarProps {
  isOpen: boolean
  onClose: () => void
}

export function MobileSidebar({ isOpen, onClose }: MobileSidebarProps) {
  return (
    <Sheet open={isOpen} onOpenChange={onClose}>
      <SheetContent side='left' className='w-72 p-0 md:hidden'>
        {/* Header */}
        <SheetHeader className='flex h-20 flex-row items-center justify-between border-b border-black/[0.04] px-4'>
          <Link
            href='/'
            className='flex items-center gap-3'
            onClick={onClose}
          >
            <div className='flex h-10 w-10 items-center justify-center rounded-xl bg-brand-navy shadow-soft'>
              <Logomark variant='light' size={24} />
            </div>
            <div className='flex flex-col'>
              <SheetTitle className='font-display text-lg font-bold tracking-tight text-brand-navy'>
                AutoPilot
              </SheetTitle>
              <span className='text-[10px] font-medium uppercase tracking-widest text-brand-muted'>
                Command Center
              </span>
            </div>
          </Link>
        </SheetHeader>

        {/* Navigation */}
        <nav
          className='flex-1 overflow-y-auto p-4'
          aria-label='Mobile navigation'
        >
          {navItems.map((section, sectionIndex) => (
            <div
              key={section.title}
              className={cn(sectionIndex > 0 && 'mt-6')}
            >
              <p className='mb-2 px-4 text-[10px] font-semibold uppercase tracking-widest text-brand-muted/70'>
                {section.title}
              </p>
              <div className='space-y-1'>
                {section.items.map((item) => (
                  <NavLink
                    key={item.href}
                    href={item.href}
                    icon={item.icon}
                    onClick={onClose}
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </SheetContent>
    </Sheet>
  )
}

