'use client'

import { useSession } from 'next-auth/react'

/**
 * Simple session hook — no refresh logic needed in dev bypass mode.
 * Returns the mock session from providers.tsx.
 */
export function useSessionRefresh() {
  const { data: session, status } = useSession()
  return { session, status }
}
