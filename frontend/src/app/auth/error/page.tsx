'use client'

import { useSearchParams, useRouter } from 'next/navigation'
import { Suspense, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'

// Errors that indicate stale cookies - auto-clear and redirect to sign-in
const AUTO_CLEAR_ERRORS = [
  'OAuthSignin',
  'OAuthCallback',
  'OAuthCreateAccount',
  'OAuthAccountNotLinked',
  'Callback',
]

function clearAuthCookies() {
  const cookiesToClear = [
    'next-auth.session-token',
    '__Secure-next-auth.session-token',
    'next-auth.csrf-token',
    '__Secure-next-auth.csrf-token',
    'next-auth.callback-url',
    '__Secure-next-auth.callback-url',
    'next-auth.pkce.code_verifier',
    '__Secure-next-auth.pkce.code_verifier',
    'next-auth.state',
    '__Secure-next-auth.state',
  ]

  cookiesToClear.forEach((cookieName) => {
    document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
    document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=${window.location.hostname}`
  })

  console.log('[AUTH] Automatically cleared stale auth cookies')
}

function ErrorContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const error = searchParams.get('error')
  const [isClearing, setIsClearing] = useState(false)

  // Auto-clear cookies on OAuth errors and redirect to sign-in
  useEffect(() => {
    if (error && AUTO_CLEAR_ERRORS.includes(error)) {
      setIsClearing(true)
      clearAuthCookies()

      // Redirect to clean sign-in page
      const timer = setTimeout(() => {
        router.replace('/auth/signin')
      }, 500)

      return () => clearTimeout(timer)
    }
  }, [error, router])

  // Show loading state while clearing cookies
  if (isClearing) {
    return (
      <div className='flex min-h-screen flex-col items-center justify-center bg-background gap-4'>
        <div className='h-8 w-8 animate-spin rounded-full border-4 border-brand-navy border-t-transparent' />
        <p className='text-sm text-muted-foreground'>Clearing session...</p>
      </div>
    )
  }

  const getErrorInfo = (errorCode: string | null) => {
    switch (errorCode) {
      case 'Configuration':
        return {
          title: 'Server Configuration Error',
          message: 'There is a problem with the server configuration. Please contact your administrator.',
        }
      case 'AccessDenied':
        return {
          title: 'Access Denied',
          message: 'You do not have permission to access this resource.',
        }
      case 'Verification':
        return {
          title: 'Link Expired',
          message: 'The verification link has expired or has already been used.',
        }
      case 'SessionRequired':
        return {
          title: 'Session Required',
          message: 'Please sign in to access this page.',
        }
      default:
        // OAuth errors are auto-cleared and redirected, so shouldn't reach here
        return {
          title: 'Something Went Wrong',
          message: 'An unexpected error occurred during authentication. Please try again.',
        }
    }
  }

  const errorInfo = getErrorInfo(error)

  return (
    <div className='flex min-h-screen items-center justify-center bg-background p-4'>
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
        className='w-full max-w-md'
      >
        <Card className='relative overflow-hidden bg-white shadow-float-lg'>
          <CardWatermark opacity={4} scale={1} />
          <CardHeader className='relative z-10 space-y-4 pb-6 text-center'>
            <motion.div
              className='mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-red-100'
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{
                delay: 0.2,
                type: 'spring',
                stiffness: 200,
                damping: 15,
              }}
            >
              <Icons.alertCircle className='h-8 w-8 text-red-600' />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.4 }}
            >
              <CardTitle className='text-xl font-bold text-brand-navy'>
                {errorInfo.title}
              </CardTitle>
            </motion.div>
          </CardHeader>
          <CardContent className='relative z-10 space-y-6 px-8 pb-8'>
            <motion.p
              className='text-center text-sm text-muted-foreground'
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4, duration: 0.4 }}
            >
              {errorInfo.message}
            </motion.p>

            <motion.div
              className='space-y-3'
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.4 }}
            >
              <Button
                asChild
                variant='gradient'
                size='lg'
                className='w-full'
              >
                <Link href='/auth/signin'>
                  Back to Sign In
                </Link>
              </Button>
            </motion.div>

            {error && (
              <motion.p
                className='text-center font-mono text-xs text-muted-foreground/60'
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6, duration: 0.4 }}
              >
                Error code: {error}
              </motion.p>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}

export default function AuthErrorPage() {
  return (
    <Suspense
      fallback={
        <div className='flex min-h-screen items-center justify-center bg-background'>
          <div className='h-8 w-8 animate-spin rounded-full border-4 border-brand-navy border-t-transparent' />
        </div>
      }
    >
      <ErrorContent />
    </Suspense>
  )
}

