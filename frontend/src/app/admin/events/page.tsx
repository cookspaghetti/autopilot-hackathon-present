'use client'

/**
 * Login Events Page
 * 
 * Allows admins to view login events and security monitoring.
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { apiClient } from '@/lib/api-client'

interface LoginEvent {
  time: number | null
  type: string | null
  realmId: string | null
  clientId: string | null
  userId: string | null
  sessionId: string | null
  ipAddress: string | null
  error: string | null
  details: Record<string, string> | null
}

interface EventsSummary {
  period_days: number
  successful_logins: number
  failed_logins: number
  unique_users: number
  unique_ips: number
  top_failed_ips: Array<{ ip: string; count: number }>
}

export default function EventsPage() {
  const { data: session, status } = useSession()
  const router = useRouter()

  const [events, setEvents] = useState<LoginEvent[]>([])
  const [summary, setSummary] = useState<EventsSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Filters
  const [eventType, setEventType] = useState<string>('all')
  const [eventTypes, setEventTypes] = useState<string[]>([])

  const isAdmin = session?.roles?.includes('admin')

  const fetchEvents = useCallback(async () => {
    setIsLoading(true)
    try {
      const params = eventType !== 'all' ? `?event_type=${eventType}&max_results=100` : '?max_results=100'
      const [eventsData, summaryData, typesData] = await Promise.all([
        apiClient.get<LoginEvent[]>(`/api/admin/events${params}`),
        apiClient.get<EventsSummary>('/api/admin/events/summary?days=7'),
        apiClient.get<string[]>('/api/admin/events/types'),
      ])
      setEvents(eventsData)
      setSummary(summaryData)
      setEventTypes(typesData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load events')
    } finally {
      setIsLoading(false)
    }
  }, [eventType])

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
    fetchEvents()
  }, [session, status, isAdmin, router, fetchEvents])

  const formatTime = (timestamp: number | null) => {
    if (!timestamp) return '—'
    return new Date(timestamp).toLocaleString()
  }

  const getEventIcon = (type: string | null) => {
    if (!type) return Icons.info
    if (type.includes('ERROR')) return Icons.alertCircle
    if (type === 'LOGIN') return Icons.check
    if (type === 'LOGOUT') return Icons.logout
    if (type === 'REGISTER') return Icons.userPlus
    return Icons.activity
  }

  const getEventColor = (type: string | null) => {
    if (!type) return 'text-gray-500'
    if (type.includes('ERROR')) return 'text-red-600'
    if (type === 'LOGIN') return 'text-emerald-600'
    if (type === 'LOGOUT') return 'text-amber-600'
    if (type === 'REGISTER') return 'text-blue-600'
    return 'text-gray-600'
  }

  const getEventBgColor = (type: string | null) => {
    if (!type) return 'bg-gray-100'
    if (type.includes('ERROR')) return 'bg-red-100'
    if (type === 'LOGIN') return 'bg-emerald-100'
    if (type === 'LOGOUT') return 'bg-amber-100'
    if (type === 'REGISTER') return 'bg-blue-100'
    return 'bg-gray-100'
  }

  if (status === 'loading' || (isLoading && events.length === 0)) {
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
        <span className='text-gray-900 font-medium'>Login Events</span>
      </div>

      {/* Header */}
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-2xl font-semibold text-gray-900'>Login Events</h1>
          <p className='text-gray-500 mt-1'>
            Security monitoring and login activity
          </p>
        </div>
        <Button onClick={() => fetchEvents()} variant='outline' className='gap-2'>
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

      {/* Summary Cards */}
      {summary && (
        <div className='grid gap-4 md:grid-cols-4'>
          <Card className='relative overflow-hidden'>
            <CardWatermark />
            <CardHeader className='pb-2'>
              <CardTitle className='text-sm font-medium text-gray-500'>
                Successful Logins (7d)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className='text-3xl font-bold text-emerald-600'>
                {summary.successful_logins}
              </div>
            </CardContent>
          </Card>
          <Card className='relative overflow-hidden border-red-100'>
            <CardWatermark />
            <CardHeader className='pb-2'>
              <CardTitle className='text-sm font-medium text-gray-500'>
                Failed Logins (7d)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className='text-3xl font-bold text-red-600'>
                {summary.failed_logins}
              </div>
            </CardContent>
          </Card>
          <Card className='relative overflow-hidden'>
            <CardWatermark />
            <CardHeader className='pb-2'>
              <CardTitle className='text-sm font-medium text-gray-500'>
                Unique Users
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className='text-3xl font-bold'>{summary.unique_users}</div>
            </CardContent>
          </Card>
          <Card className='relative overflow-hidden'>
            <CardWatermark />
            <CardHeader className='pb-2'>
              <CardTitle className='text-sm font-medium text-gray-500'>
                Unique IPs
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className='text-3xl font-bold'>{summary.unique_ips}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Top Failed IPs Warning */}
      {summary && summary.top_failed_ips.length > 0 && summary.failed_logins > 5 && (
        <Card className='border-amber-200 bg-amber-50'>
          <CardHeader className='pb-2'>
            <CardTitle className='text-sm font-medium text-amber-800 flex items-center gap-2'>
              <Icons.alertTriangle className='h-4 w-4' />
              Top IPs with Failed Login Attempts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className='flex flex-wrap gap-3'>
              {summary.top_failed_ips.slice(0, 5).map((item) => (
                <div
                  key={item.ip}
                  className='inline-flex items-center gap-2 rounded-full bg-amber-100 px-3 py-1 text-sm text-amber-800'
                >
                  <Icons.globe className='h-3 w-3' />
                  <span className='font-mono'>{item.ip}</span>
                  <span className='font-semibold'>({item.count})</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filter */}
      <div className='flex items-center gap-4'>
        <div className='w-64'>
          <Select value={eventType} onValueChange={setEventType}>
            <SelectTrigger>
              <SelectValue placeholder='Filter by event type' />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='all'>All Events</SelectItem>
              {eventTypes.map((type) => (
                <SelectItem key={type} value={type}>
                  {type.replace(/_/g, ' ')}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {isLoading && (
          <Icons.loader className='h-4 w-4 animate-spin text-gray-400' />
        )}
      </div>

      {/* Events List */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Events</CardTitle>
          <CardDescription>
            Latest 100 login/security events
          </CardDescription>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <div className='flex flex-col items-center justify-center py-12 text-gray-500'>
              <Icons.activity className='h-12 w-12 mb-4 text-gray-300' />
              <p>No events found</p>
              <p className='text-sm'>Events will appear when users interact with the system</p>
            </div>
          ) : (
            <div className='space-y-2'>
              <AnimatePresence mode='popLayout'>
                {events.map((event, index) => {
                  const Icon = getEventIcon(event.type)
                  return (
                    <motion.div
                      key={`${event.time}-${event.sessionId}-${index}`}
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: -10 }}
                      className='flex items-start gap-4 p-3 rounded-lg hover:bg-gray-50 border border-transparent hover:border-gray-100'
                    >
                      <div className={`p-2 rounded-full ${getEventBgColor(event.type)}`}>
                        <Icon className={`h-4 w-4 ${getEventColor(event.type)}`} />
                      </div>
                      <div className='flex-1 min-w-0'>
                        <div className='flex items-center gap-2'>
                          <span className={`font-medium ${getEventColor(event.type)}`}>
                            {event.type?.replace(/_/g, ' ') || 'Unknown'}
                          </span>
                          {event.error && (
                            <span className='text-xs text-red-600 bg-red-100 px-2 py-0.5 rounded'>
                              {event.error}
                            </span>
                          )}
                        </div>
                        <div className='flex items-center gap-4 mt-1 text-sm text-gray-500'>
                          {event.ipAddress && (
                            <span className='inline-flex items-center gap-1'>
                              <Icons.globe className='h-3 w-3' />
                              <span className='font-mono text-xs'>{event.ipAddress}</span>
                            </span>
                          )}
                          {event.userId && (
                            <span className='inline-flex items-center gap-1'>
                              <Icons.user className='h-3 w-3' />
                              <span className='text-xs truncate max-w-[200px]'>{event.userId}</span>
                            </span>
                          )}
                          {event.details?.username && (
                            <span className='text-xs'>
                              {event.details.username}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className='text-sm text-gray-400 whitespace-nowrap'>
                        {formatTime(event.time)}
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

