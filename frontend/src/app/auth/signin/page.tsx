'use client'

import { signIn } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'
import { Suspense, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { Logomark } from '@/components/brand'

function SignInContent() {
  const searchParams = useSearchParams()
  const callbackUrl = searchParams.get('callbackUrl') || '/'

  // Auto-sign-in: immediately authenticate as Dev User
  useEffect(() => {
    signIn('autopilot-dev', { callbackUrl, redirect: true })
  }, [callbackUrl])

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95, y: 20 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
      className='w-full max-w-md'
    >
      <Card className='relative overflow-hidden bg-white shadow-float-lg'>
        <CardWatermark opacity={4} scale={1} />
        <CardHeader className='relative z-10 space-y-4 pb-8 text-center'>
          <motion.div
            className='mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-brand-navy shadow-xl'
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{
              delay: 0.2,
              type: 'spring',
              stiffness: 200,
              damping: 15,
            }}
          >
            <Logomark variant='light' size={48} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
          >
            <CardTitle className='text-display-5 font-bold text-brand-navy'>
              AutoPilot
            </CardTitle>
            <p className='mt-2 text-muted-foreground'>
              Signing you in...
            </p>
          </motion.div>
        </CardHeader>
        <CardContent className='relative z-10 space-y-4 px-8 pb-8'>
          {/* Loading spinner while auto-signing in */}
          <div className='flex justify-center py-4'>
            <div className='h-8 w-8 animate-spin rounded-full border-4 border-brand-navy border-t-transparent' />
          </div>
          
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.4 }}
          >
            <Button
              onClick={() => signIn('autopilot-dev', { callbackUrl, redirect: true })}
              variant='gradient'
              size='lg'
              className='group w-full py-6 text-base'
            >
              Enter Command Center
              <Icons.arrowRight className='ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1' />
            </Button>
          </motion.div>

          <motion.p
            className='text-center text-xs text-muted-foreground'
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5, duration: 0.4 }}
          >
            Dev mode — no credentials required
          </motion.p>
        </CardContent>
      </Card>
    </motion.div>
  )
}

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <div className='flex min-h-screen items-center justify-center bg-background'>
          <div className='h-8 w-8 animate-spin rounded-full border-4 border-brand-navy border-t-transparent' />
        </div>
      }
    >
      <SignInContent />
    </Suspense>
  )
}
