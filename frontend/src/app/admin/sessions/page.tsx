'use client'

/**
 * User Sessions Page
 * 
 * Allows admins to view and terminate active user sessions.
 */

import { useCallback, useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { apiClient } from '@/lib/api-client'

interface Session {
  id: string
  userId: string | null
  userEmail: string | null
  userName: string | null
  ipAddress: string | null
  start: number | null
  lastAccess: number | null
  clients: Record<string, string> | null
}

interface SessionStats {
  totalActiveSessions: number
  clientStats: Array<{ clientId: string; active: number }>
}

export default function SessionsPage() {
  const { data: session, status } = useSession()
  const router = useRouter()

  const [sessions, setSessions] = useState<Session[]>([])
  const [stats, setStats] = useState<SessionStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Action states
  const [terminateDialogOpen, setTerminateDialogOpen] = useState(false)
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const isAdmin = session?.roles?.includes('admin')

  const fetchSessions = useCallback(async () => {
    try {
      const [sessionsData, statsData] = await Promise.all([
        apiClient.get<Session[]>('/api/admin/sessions'),
        apiClient.get<SessionStats>('/api/admin/sessions/stats'),
      ])
      setSessions(sessionsData)
      setStats(statsData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sessions')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (status === 'loading') return
    if (!session) {
      router.push('/auth/signin')
      return
    }
    if (!isAdmin) {
      router.push('/')
      return
    }
    fetchSessions()
  }, [session, status, isAdmin, router, fetchSessions])

  const handleTerminate = async () => {
    if (!selectedSession) return
    setActionLoading(selectedSession.id)
    try {
      await apiClient.delete(`/api/admin/sessions/${selectedSession.id}`)
      setTerminateDialogOpen(false)
      setSelectedSession(null)
      await fetchSessions()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to terminate session')
    } finally {
      setActionLoading(null)
    }
  }

  const formatTime = (timestamp: number | null) => {
    if (!timestamp) return '—'
    return new Date(timestamp).toLocaleString()
  }

  const getSessionDuration = (start: number | null) => {
    if (!start) return '—'
    const duration = Date.now() - start
    const hours = Math.floor(duration / (1000 * 60 * 60))
    const minutes = Math.floor((duration % (1000 * 60 * 60)) / (1000 * 60))
    if (hours > 0) return `${hours}h ${minutes}m`
    return `${minutes}m`
  }

  // Get unique IPs
  const uniqueIps = new Set(sessions.map(s => s.ipAddress).filter(Boolean)).size

  if (status === 'loading' || isLoading) {
    return (
      <div className='flex min-h-[400px] items-center justify-center'>
        <Icons.loader className='h-8 w-8 animate-spin text-gray-400' />
      </div>
    )
  }

  return (
    <div className='space-y-6'>
      {/* Breadcrumb */}
      <div className='flex items-center gap-2 text-sm text-gray-500'>
        <Icons.home className='h-4 w-4' />
        <span>/</span>
        <span>Admin</span>
        <span>/</span>
        <span className='text-gray-900 font-medium'>Sessions</span>
      </div>

      {/* Header */}
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-2xl font-semibold text-gray-900'>User Sessions</h1>
          <p className='text-gray-500 mt-1'>
            Monitor and manage active user sessions
          </p>
        </div>
        <Button onClick={() => fetchSessions()} variant='outline' className='gap-2'>
          <Icons.refresh className='h-4 w-4' />
          Refresh
        </Button>
      </div>

      {/* Error display */}
      {error && (
        <div className='rounded-lg bg-red-50 p-4 text-red-600'>
          <div className='flex items-center gap-2'>
            <Icons.alertCircle className='h-5 w-5' />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className='grid gap-4 md:grid-cols-3'>
        <Card className='relative overflow-hidden'>
          <CardWatermark />
          <CardHeader className='pb-2'>
            <CardTitle className='text-sm font-medium text-gray-500'>Active Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className='text-3xl font-bold text-emerald-600'>
              {stats?.totalActiveSessions || sessions.length}
            </div>
          </CardContent>
        </Card>
        <Card className='relative overflow-hidden'>
          <CardWatermark />
          <CardHeader className='pb-2'>
            <CardTitle className='text-sm font-medium text-gray-500'>Active Users</CardTitle>
          </CardHeader>
          <CardContent>
            <div className='text-3xl font-bold'>
              {new Set(sessions.map(s => s.userId).filter(Boolean)).size}
            </div>
          </CardContent>
        </Card>
        <Card className='relative overflow-hidden'>
          <CardWatermark />
          <CardHeader className='pb-2'>
            <CardTitle className='text-sm font-medium text-gray-500'>Unique IPs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className='text-3xl font-bold'>{uniqueIps}</div>
          </CardContent>
        </Card>
      </div>

      {/* Sessions Table */}
      <Card>
        <CardHeader>
          <CardTitle>Active Sessions</CardTitle>
          <CardDescription>
            All currently active user sessions
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sessions.length === 0 ? (
            <div className='flex flex-col items-center justify-center py-12 text-gray-500'>
              <Icons.device className='h-12 w-12 mb-4 text-gray-300' />
              <p>No active sessions</p>
              <p className='text-sm'>Sessions will appear when users log in</p>
            </div>
          ) : (
            <div className='overflow-x-auto'>
              <table className='w-full'>
                <thead>
                  <tr className='border-b text-left text-sm text-gray-500'>
                    <th className='pb-3 font-medium'>User</th>
                    <th className='pb-3 font-medium'>IP Address</th>
                    <th className='pb-3 font-medium'>Started</th>
                    <th className='pb-3 font-medium'>Duration</th>
                    <th className='pb-3 font-medium'>Last Access</th>
                    <th className='pb-3 font-medium text-right'>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence mode='popLayout'>
                    {sessions.map((sess) => (
                      <motion.tr
                        key={sess.id}
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, x: -10 }}
                        className='border-b last:border-0 hover:bg-gray-50'
                      >
                        <td className='py-4'>
                          <div className='flex flex-col'>
                            <span className='font-medium'>
                              {sess.userName || 'Unknown'}
                            </span>
                            <span className='text-sm text-gray-500'>
                              {sess.userEmail || sess.userId}
                            </span>
                          </div>
                        </td>
                        <td className='py-4'>
                          <span className='inline-flex items-center gap-1 text-sm font-mono'>
                            <Icons.globe className='h-3 w-3 text-gray-400' />
                            {sess.ipAddress || '—'}
                          </span>
                        </td>
                        <td className='py-4 text-sm text-gray-600'>
                          {formatTime(sess.start)}
                        </td>
                        <td className='py-4'>
                          <span className='inline-flex items-center gap-1 text-sm'>
                            <Icons.clock className='h-3 w-3 text-gray-400' />
                            {getSessionDuration(sess.start)}
                          </span>
                        </td>
                        <td className='py-4 text-sm text-gray-600'>
                          {formatTime(sess.lastAccess)}
                        </td>
                        <td className='py-4 text-right'>
                          <Button
                            size='sm'
                            variant='outline'
                            onClick={() => {
                              setSelectedSession(sess)
                              setTerminateDialogOpen(true)
                            }}
                            disabled={actionLoading === sess.id}
                            className='text-red-600 hover:text-red-700 hover:border-red-300'
                          >
                            {actionLoading === sess.id ? (
                              <Icons.loader className='h-4 w-4 animate-spin' />
                            ) : (
                              <>
                                <Icons.logout className='h-4 w-4 mr-1' />
                                Terminate
                              </>
                            )}
                          </Button>
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Terminate Confirmation */}
      <AlertDialog open={terminateDialogOpen} onOpenChange={setTerminateDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Terminate Session</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to terminate this session for{' '}
              <strong>{selectedSession?.userEmail || selectedSession?.userName}</strong>?
              They will be logged out immediately.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleTerminate}
              className='bg-red-600 hover:bg-red-700'
            >
              Terminate Session
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

