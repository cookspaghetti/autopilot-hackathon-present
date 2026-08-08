'use client'

import { SessionProvider } from 'next-auth/react'
import { ToastProvider } from '@/components/ui/toast'
import { CommandPalette } from '@/components/CommandPalette'
import { AIProvider } from '@/context/AIContext'
import { AIManager } from '@/components/ai/AIManager'

// Mock session — all components see an authenticated admin user
const mockSession: {
  user: { name: string; email: string }
  roles: string[]
  expires: string
} = {
  user: {
    name: 'Dev User',
    email: 'dev@autopilot.local',
  },
  roles: ['admin', 'user'],
  expires: '2099-12-31T23:59:59.999Z',
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider
      session={mockSession}
      basePath={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/api/auth`}
      refetchInterval={0}
      refetchOnWindowFocus={false}
    >
      <AIProvider>
        {children}
        <AIManager />
        <ToastProvider />
        <CommandPalette />
      </AIProvider>
    </SessionProvider>
  )
}
