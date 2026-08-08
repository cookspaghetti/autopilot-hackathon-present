'use client'

/**
 * Audit Logs Page
 * 
 * Displays all audit logs (both middleware-generated and custom).
 * 
 * Features:
 * - Filterable by category, action, actor, date range
 * - Filterable by middleware-specific fields (HTTP method, status code)
 * - Export to CSV or Excel
 * - Real-time stats dashboard
 * 
 * Middleware logs are auto-generated for every API request.
 * Custom logs are added manually for business-critical actions.
 */

import { useCallback, useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface AuditLog {
  id: number
  timestamp: string
  actor_id: string | null
  actor_email: string | null
  actor_ip: string | null
  actor_user_agent: string | null
  action: string
  category: string
  severity: string
  resource_type: string | null
  resource_id: string | null
  resource_name: string | null
  description: string
  extra_data: Record<string, unknown> | null
  success: string
  error_message: string | null
  endpoint: string | null
  request_id: string | null
  session_id: string | null
  // Middleware-specific fields
  http_method: string | null
  request_body: string | null
  query_params: string | null
  response_status: number | null
  response_time_ms: number | null
  is_middleware: boolean
}

interface AuditStats {
  total_events: number
  events_today: number
  events_this_week: number
  by_category: Record<string, number>
  by_action: Record<string, number>
  recent_errors: number
  // Middleware-specific stats
  by_http_method: Record<string, number> | null
  by_status_code: Record<string, number> | null
  avg_response_time_ms: number | null
  middleware_logs: number
  custom_logs: number
}

const categoryColors: Record<string, string> = {
  auth: 'bg-purple-100 text-purple-700',
  user_management: 'bg-blue-100 text-blue-700',
  admin: 'bg-indigo-100 text-indigo-700',
  settings: 'bg-green-100 text-green-700',
  data: 'bg-cyan-100 text-cyan-700',
  security: 'bg-red-100 text-red-700',
  system: 'bg-gray-100 text-gray-700',
  api: 'bg-orange-100 text-orange-700',
  error: 'bg-red-100 text-red-700',
}

const methodColors: Record<string, string> = {
  GET: 'bg-green-100 text-green-700',
  POST: 'bg-blue-100 text-blue-700',
  PUT: 'bg-amber-100 text-amber-700',
  PATCH: 'bg-orange-100 text-orange-700',
  DELETE: 'bg-red-100 text-red-700',
}

export default function AuditLogsPage() {
  const { data: session, status: sessionStatus } = useSession()
  const router = useRouter()
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [stats, setStats] = useState<AuditStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isExporting, setIsExporting] = useState(false)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  
  // Filters
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [actionFilter, setActionFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [httpMethodFilter, setHttpMethodFilter] = useState<string>('')
  const [sourceFilter, setSourceFilter] = useState<string>('') // 'middleware', 'custom', or ''
  
  // Expanded detail view
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null)

  const isAdmin = session?.roles?.includes('admin')

  const fetchLogs = useCallback(async () => {
    try {
      setIsLoading(true)
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: '25',
      })
      if (categoryFilter) params.append('category', categoryFilter)
      if (actionFilter) params.append('action', actionFilter)
      if (searchQuery) params.append('search', searchQuery)
      if (httpMethodFilter) params.append('http_method', httpMethodFilter)
      if (sourceFilter === 'middleware') params.append('is_middleware', 'true')
      if (sourceFilter === 'custom') params.append('is_middleware', 'false')

      const data = await apiClient.get(`/api/admin/audit?${params}`) as {
        logs: AuditLog[]
        total: number
        page: number
        total_pages: number
      }
      setLogs(data.logs)
      setTotal(data.total)
      setTotalPages(data.total_pages)
    } catch (error) {
      console.error('Failed to fetch audit logs:', error)
    } finally {
      setIsLoading(false)
    }
  }, [page, categoryFilter, actionFilter, searchQuery, httpMethodFilter, sourceFilter])

  const handleExport = async (format: 'csv' | 'xlsx') => {
    try {
      setIsExporting(true)
      const params = new URLSearchParams()
      params.append('format', format)
      if (categoryFilter) params.append('category', categoryFilter)
      if (searchQuery) params.append('search', searchQuery)
      if (httpMethodFilter) params.append('http_method', httpMethodFilter)
      if (sourceFilter === 'middleware') params.append('is_middleware', 'true')
      if (sourceFilter === 'custom') params.append('is_middleware', 'false')
      params.append('limit', '10000')

      // Use fetch directly for file download
      // Construct URL with API_URL and BASE_PATH for proper routing
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''
      const response = await fetch(`${apiUrl}${basePath}/api/admin/audit/export?${params}`, {
        headers: {
          'Authorization': `Bearer ${(session as { accessToken?: string })?.accessToken}`,
        },
      })
      
      if (!response.ok) throw new Error('Export failed')
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit_logs.${format}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      a.remove()
    } catch (error) {
      console.error('Failed to export:', error)
    } finally {
      setIsExporting(false)
    }
  }

  const fetchStats = useCallback(async () => {
    try {
      const data = await apiClient.get('/api/admin/audit/stats') as AuditStats
      setStats(data)
    } catch (error) {
      console.error('Failed to fetch stats:', error)
    }
  }, [])

  useEffect(() => {
    if (sessionStatus === 'loading') return
    if (sessionStatus === 'unauthenticated' || !isAdmin) {
      router.push('/')
      return
    }
    fetchLogs()
    fetchStats()
  }, [sessionStatus, isAdmin, router, fetchLogs, fetchStats])

  const handleSearch = () => {
    setPage(1)
    fetchLogs()
  }

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts)
    return date.toLocaleString()
  }

  if (sessionStatus === 'loading' || !isAdmin) {
    return (
      <div className='flex h-96 items-center justify-center'>
        <Icons.loader className='h-8 w-8 animate-spin text-brand-cornflower' />
      </div>
    )
  }

  return (
    <div className='space-y-6 p-6'>
      {/* Header */}
      <div>
        <h1 className='text-2xl font-bold text-brand-navy'>Audit Logs</h1>
        <p className='text-gray-500'>View and search all system activity</p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className='grid grid-cols-2 gap-4 md:grid-cols-6'>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className='rounded-xl border border-gray-100 bg-white p-4 shadow-sm'
          >
            <p className='text-sm text-gray-500'>Total Events</p>
            <p className='text-2xl font-bold text-brand-navy'>{stats.total_events.toLocaleString()}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className='rounded-xl border border-gray-100 bg-white p-4 shadow-sm'
          >
            <p className='text-sm text-gray-500'>Today</p>
            <p className='text-2xl font-bold text-green-600'>{stats.events_today.toLocaleString()}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className='rounded-xl border border-gray-100 bg-white p-4 shadow-sm'
          >
            <p className='text-sm text-gray-500'>This Week</p>
            <p className='text-2xl font-bold text-blue-600'>{stats.events_this_week.toLocaleString()}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className='rounded-xl border border-gray-100 bg-white p-4 shadow-sm'
          >
            <p className='text-sm text-gray-500'>Errors</p>
            <p className='text-2xl font-bold text-red-600'>{stats.recent_errors}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className='rounded-xl border border-gray-100 bg-white p-4 shadow-sm'
          >
            <p className='text-sm text-gray-500'>Auto (API)</p>
            <p className='text-2xl font-bold text-orange-600'>{stats.middleware_logs.toLocaleString()}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className='rounded-xl border border-gray-100 bg-white p-4 shadow-sm'
          >
            <p className='text-sm text-gray-500'>Avg Response</p>
            <p className='text-2xl font-bold text-purple-600'>
              {stats.avg_response_time_ms ? `${stats.avg_response_time_ms.toFixed(0)}ms` : '-'}
            </p>
          </motion.div>
        </div>
      )}

      {/* Filters */}
      <div className='flex flex-wrap items-center gap-3 rounded-xl border border-gray-100 bg-white p-4'>
        <div className='flex-1 min-w-[200px]'>
          <Input
            type='text'
            placeholder='Search in description...'
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <Select value={categoryFilter || 'all'} onValueChange={(v) => { setCategoryFilter(v === 'all' ? '' : v); setPage(1) }}>
          <SelectTrigger className='w-[160px]'>
            <SelectValue placeholder='All Categories' />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value='all'>All Categories</SelectItem>
            <SelectItem value='auth'>Auth</SelectItem>
            <SelectItem value='user_management'>User Management</SelectItem>
            <SelectItem value='admin'>Admin</SelectItem>
            <SelectItem value='settings'>Settings</SelectItem>
            <SelectItem value='api'>API</SelectItem>
            <SelectItem value='security'>Security</SelectItem>
          </SelectContent>
        </Select>
        <Select value={httpMethodFilter || 'all'} onValueChange={(v) => { setHttpMethodFilter(v === 'all' ? '' : v); setPage(1) }}>
          <SelectTrigger className='w-[130px]'>
            <SelectValue placeholder='All Methods' />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value='all'>All Methods</SelectItem>
            <SelectItem value='GET'>GET</SelectItem>
            <SelectItem value='POST'>POST</SelectItem>
            <SelectItem value='PUT'>PUT</SelectItem>
            <SelectItem value='PATCH'>PATCH</SelectItem>
            <SelectItem value='DELETE'>DELETE</SelectItem>
          </SelectContent>
        </Select>
        <Select value={sourceFilter || 'all'} onValueChange={(v) => { setSourceFilter(v === 'all' ? '' : v); setPage(1) }}>
          <SelectTrigger className='w-[140px]'>
            <SelectValue placeholder='All Sources' />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value='all'>All Sources</SelectItem>
            <SelectItem value='middleware'>Auto (API)</SelectItem>
            <SelectItem value='custom'>Custom</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={handleSearch} variant='outline' size='sm'>
          <Icons.search className='mr-2 h-4 w-4' />
          Search
        </Button>
        <Button
          onClick={() => {
            setCategoryFilter('')
            setActionFilter('')
            setSearchQuery('')
            setHttpMethodFilter('')
            setSourceFilter('')
            setPage(1)
            fetchLogs()
          }}
          variant='ghost'
          size='sm'
        >
          Clear
        </Button>
        
        {/* Export Buttons */}
        <div className='ml-auto flex gap-2'>
          <Button
            onClick={() => handleExport('csv')}
            variant='outline'
            size='sm'
            disabled={isExporting}
          >
            {isExporting ? (
              <Icons.loader className='mr-2 h-4 w-4 animate-spin' />
            ) : (
              <Icons.download className='mr-2 h-4 w-4' />
            )}
            CSV
          </Button>
          <Button
            onClick={() => handleExport('xlsx')}
            variant='outline'
            size='sm'
            disabled={isExporting}
          >
            {isExporting ? (
              <Icons.loader className='mr-2 h-4 w-4 animate-spin' />
            ) : (
              <Icons.download className='mr-2 h-4 w-4' />
            )}
            Excel
          </Button>
        </div>
      </div>

      {/* Logs Table */}
      <div className='overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm'>
        {isLoading ? (
          <div className='flex h-64 items-center justify-center'>
            <Icons.loader className='h-8 w-8 animate-spin text-brand-cornflower' />
          </div>
        ) : logs.length === 0 ? (
          <div className='flex h-64 flex-col items-center justify-center text-gray-500'>
            <Icons.fileText className='mb-4 h-12 w-12 text-gray-300' />
            <p>No audit logs found</p>
          </div>
        ) : (
          <div className='overflow-x-auto'>
            <table className='w-full text-left text-sm'>
              <thead className='border-b border-gray-100 bg-gray-50'>
                <tr>
                  <th className='px-3 py-3 font-medium text-gray-600'>Time</th>
                  <th className='px-3 py-3 font-medium text-gray-600'>Actor</th>
                  <th className='px-3 py-3 font-medium text-gray-600'>Method</th>
                  <th className='px-3 py-3 font-medium text-gray-600'>Action</th>
                  <th className='px-3 py-3 font-medium text-gray-600'>Category</th>
                  <th className='px-3 py-3 font-medium text-gray-600'>Description</th>
                  <th className='px-3 py-3 font-medium text-gray-600'>Status</th>
                  <th className='px-3 py-3 font-medium text-gray-600'>Time</th>
                  <th className='px-3 py-3 font-medium text-gray-600'>Source</th>
                </tr>
              </thead>
              <tbody className='divide-y divide-gray-50'>
                {logs.map((log) => (
                  <motion.tr
                    key={log.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    onClick={() => setSelectedLog(log)}
                    className='cursor-pointer hover:bg-gray-50 transition-colors'
                  >
                    <td className='whitespace-nowrap px-3 py-3 text-xs text-gray-500'>
                      {formatTimestamp(log.timestamp)}
                    </td>
                    <td className='px-3 py-3'>
                      <div className='text-sm font-medium text-gray-900'>
                        {log.actor_email || 'anonymous'}
                      </div>
                      {log.actor_ip && (
                        <div className='text-xs text-gray-400'>{log.actor_ip}</div>
                      )}
                    </td>
                    <td className='px-3 py-3'>
                      {log.http_method && (
                        <span
                          className={`inline-flex rounded px-1.5 py-0.5 text-xs font-medium ${
                            methodColors[log.http_method] || 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {log.http_method}
                        </span>
                      )}
                    </td>
                    <td className='px-3 py-3'>
                      <span className='font-mono text-xs text-gray-700'>
                        {log.action}
                      </span>
                    </td>
                    <td className='px-3 py-3'>
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          categoryColors[log.category] || 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {log.category.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className='max-w-[200px] truncate px-3 py-3 text-sm text-gray-600' title={log.description}>
                      {log.description}
                    </td>
                    <td className='px-3 py-3'>
                      {log.response_status ? (
                        <span
                          className={`inline-flex rounded px-1.5 py-0.5 text-xs font-medium ${
                            log.response_status >= 500
                              ? 'bg-red-100 text-red-700'
                              : log.response_status >= 400
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-green-100 text-green-700'
                          }`}
                        >
                          {log.response_status}
                        </span>
                      ) : log.success === 'true' ? (
                        <span className='inline-flex items-center gap-1 text-xs text-green-600'>
                          <Icons.check className='h-3 w-3' />
                        </span>
                      ) : (
                        <span className='inline-flex items-center gap-1 text-xs text-red-600'>
                          <Icons.alertCircle className='h-3 w-3' />
                        </span>
                      )}
                    </td>
                    <td className='px-3 py-3 text-xs text-gray-500'>
                      {log.response_time_ms ? `${log.response_time_ms.toFixed(0)}ms` : '-'}
                    </td>
                    <td className='px-3 py-3'>
                      <span
                        className={`inline-flex rounded px-1.5 py-0.5 text-xs ${
                          log.is_middleware
                            ? 'bg-orange-50 text-orange-600'
                            : 'bg-indigo-50 text-indigo-600'
                        }`}
                      >
                        {log.is_middleware ? 'Auto' : 'Custom'}
                      </span>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className='flex items-center justify-between border-t border-gray-100 px-4 py-3'>
            <p className='text-sm text-gray-500'>
              Showing {(page - 1) * 25 + 1} to {Math.min(page * 25, total)} of {total} entries
            </p>
            <div className='flex items-center gap-2'>
              <Button
                variant='outline'
                size='sm'
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                <Icons.chevronLeft className='h-4 w-4' />
              </Button>
              <span className='text-sm text-gray-600'>
                Page {page} of {totalPages}
              </span>
              <Button
                variant='outline'
                size='sm'
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                <Icons.chevronRight className='h-4 w-4' />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Detail Slide-over Panel */}
      {selectedLog && (
        <div className='fixed inset-0 z-[10000] overflow-hidden'>
          {/* Backdrop */}
          <div 
            className='absolute inset-0 bg-black/40 transition-opacity'
            onClick={() => setSelectedLog(null)}
          />
          
          {/* Panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className='absolute right-0 top-0 h-full w-full max-w-2xl bg-white shadow-2xl'
          >
            {/* Header */}
            <div className='flex items-center justify-between border-b border-gray-200 px-6 py-4'>
              <div>
                <h2 className='text-lg font-semibold text-brand-navy'>Audit Log Details</h2>
                <p className='text-sm text-gray-500'>ID: {selectedLog.id}</p>
              </div>
              <Button variant='ghost' size='sm' onClick={() => setSelectedLog(null)}>
                <Icons.close className='h-5 w-5' />
              </Button>
            </div>
            
            {/* Content */}
            <div className='h-[calc(100vh-80px)] overflow-y-auto p-6'>
              <div className='space-y-6'>
                {/* Summary */}
                <div className='flex flex-wrap items-center gap-2'>
                  {selectedLog.http_method && (
                    <span className={`rounded px-2 py-1 text-sm font-medium ${methodColors[selectedLog.http_method] || 'bg-gray-100'}`}>
                      {selectedLog.http_method}
                    </span>
                  )}
                  <span className={`rounded-full px-2 py-1 text-xs font-medium ${categoryColors[selectedLog.category] || 'bg-gray-100'}`}>
                    {selectedLog.category.replace(/_/g, ' ')}
                  </span>
                  {selectedLog.response_status && (
                    <span className={`rounded px-2 py-1 text-sm font-medium ${
                      selectedLog.response_status >= 500 ? 'bg-red-100 text-red-700' :
                      selectedLog.response_status >= 400 ? 'bg-amber-100 text-amber-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {selectedLog.response_status}
                    </span>
                  )}
                  <span className={`rounded px-1.5 py-0.5 text-xs ${
                    selectedLog.is_middleware ? 'bg-orange-50 text-orange-600' : 'bg-indigo-50 text-indigo-600'
                  }`}>
                    {selectedLog.is_middleware ? 'Auto' : 'Custom'}
                  </span>
                </div>

                {/* Actor Information */}
                <div className='rounded-lg border border-gray-200 p-4'>
                  <h3 className='mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700'>
                    <Icons.user className='h-4 w-4' />
                    Actor Information
                  </h3>
                  <dl className='grid grid-cols-2 gap-3 text-sm'>
                    <div>
                      <dt className='text-gray-500'>Email</dt>
                      <dd className='font-medium text-gray-900'>{selectedLog.actor_email || 'Anonymous'}</dd>
                    </div>
                    <div>
                      <dt className='text-gray-500'>User ID</dt>
                      <dd className='font-mono text-xs text-gray-900'>{selectedLog.actor_id || '-'}</dd>
                    </div>
                    <div>
                      <dt className='text-gray-500'>IP Address</dt>
                      <dd className='font-mono text-gray-900'>{selectedLog.actor_ip || '-'}</dd>
                    </div>
                    <div>
                      <dt className='text-gray-500'>Session ID</dt>
                      <dd className='font-mono text-xs text-gray-900 truncate' title={selectedLog.session_id || ''}>
                        {selectedLog.session_id || '-'}
                      </dd>
                    </div>
                    {selectedLog.actor_user_agent && (
                      <div className='col-span-2'>
                        <dt className='text-gray-500'>User Agent</dt>
                        <dd className='text-xs text-gray-700 break-all'>{selectedLog.actor_user_agent}</dd>
                      </div>
                    )}
                  </dl>
                </div>

                {/* Request Details */}
                <div className='rounded-lg border border-gray-200 p-4'>
                  <h3 className='mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700'>
                    <Icons.fileText className='h-4 w-4' />
                    Request Details
                  </h3>
                  <dl className='space-y-3 text-sm'>
                    <div>
                      <dt className='text-gray-500'>Timestamp</dt>
                      <dd className='font-medium text-gray-900'>{formatTimestamp(selectedLog.timestamp)}</dd>
                    </div>
                    <div>
                      <dt className='text-gray-500'>Action</dt>
                      <dd className='font-mono text-sm text-gray-900'>{selectedLog.action}</dd>
                    </div>
                    <div>
                      <dt className='text-gray-500'>Endpoint</dt>
                      <dd className='font-mono text-sm text-gray-900'>{selectedLog.endpoint || '-'}</dd>
                    </div>
                    {selectedLog.query_params && (
                      <div>
                        <dt className='text-gray-500'>Query Parameters</dt>
                        <dd className='font-mono text-xs bg-gray-50 p-2 rounded'>{selectedLog.query_params}</dd>
                      </div>
                    )}
                    <div>
                      <dt className='text-gray-500'>Description</dt>
                      <dd className='text-gray-900'>{selectedLog.description}</dd>
                    </div>
                    {selectedLog.request_body && (
                      <div>
                        <dt className='text-gray-500'>Request Body</dt>
                        <dd className='font-mono text-xs bg-gray-50 p-2 rounded overflow-x-auto max-h-48 overflow-y-auto'>
                          <pre className='whitespace-pre-wrap'>{selectedLog.request_body}</pre>
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>

                {/* Resource Details (if applicable) */}
                {(selectedLog.resource_type || selectedLog.resource_id) && (
                  <div className='rounded-lg border border-gray-200 p-4'>
                    <h3 className='mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700'>
                      <Icons.folder className='h-4 w-4' />
                      Resource Details
                    </h3>
                    <dl className='grid grid-cols-3 gap-3 text-sm'>
                      <div>
                        <dt className='text-gray-500'>Type</dt>
                        <dd className='font-medium text-gray-900'>{selectedLog.resource_type || '-'}</dd>
                      </div>
                      <div>
                        <dt className='text-gray-500'>ID</dt>
                        <dd className='font-mono text-xs text-gray-900'>{selectedLog.resource_id || '-'}</dd>
                      </div>
                      <div>
                        <dt className='text-gray-500'>Name</dt>
                        <dd className='text-gray-900'>{selectedLog.resource_name || '-'}</dd>
                      </div>
                    </dl>
                  </div>
                )}

                {/* Response Details */}
                <div className='rounded-lg border border-gray-200 p-4'>
                  <h3 className='mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700'>
                    <Icons.check className='h-4 w-4' />
                    Response Details
                  </h3>
                  <dl className='grid grid-cols-3 gap-3 text-sm'>
                    <div>
                      <dt className='text-gray-500'>Status</dt>
                      <dd className={`font-medium ${selectedLog.success === 'true' ? 'text-green-600' : 'text-red-600'}`}>
                        {selectedLog.success === 'true' ? 'Success' : 'Failed'}
                      </dd>
                    </div>
                    <div>
                      <dt className='text-gray-500'>Status Code</dt>
                      <dd className='font-mono text-gray-900'>{selectedLog.response_status || '-'}</dd>
                    </div>
                    <div>
                      <dt className='text-gray-500'>Response Time</dt>
                      <dd className='font-medium text-gray-900'>
                        {selectedLog.response_time_ms ? `${selectedLog.response_time_ms.toFixed(0)}ms` : '-'}
                      </dd>
                    </div>
                    {selectedLog.error_message && (
                      <div className='col-span-3'>
                        <dt className='text-gray-500'>Error Message</dt>
                        <dd className='text-red-600 bg-red-50 p-2 rounded text-sm'>{selectedLog.error_message}</dd>
                      </div>
                    )}
                  </dl>
                </div>

                {/* Extra Data (if any) */}
                {selectedLog.extra_data && Object.keys(selectedLog.extra_data).length > 0 && (
                  <div className='rounded-lg border border-gray-200 p-4'>
                    <h3 className='mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700'>
                      <Icons.activity className='h-4 w-4' />
                      Additional Data
                    </h3>
                    <pre className='text-xs bg-gray-50 p-3 rounded overflow-x-auto'>
                      {JSON.stringify(selectedLog.extra_data, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Technical Details */}
                <div className='rounded-lg border border-gray-100 bg-gray-50 p-4'>
                  <h3 className='mb-3 text-xs font-semibold text-gray-500 uppercase tracking-wide'>
                    Technical Details
                  </h3>
                  <dl className='grid grid-cols-2 gap-2 text-xs'>
                    <div>
                      <dt className='text-gray-400'>Log ID</dt>
                      <dd className='font-mono text-gray-600'>{selectedLog.id}</dd>
                    </div>
                    <div>
                      <dt className='text-gray-400'>Request ID</dt>
                      <dd className='font-mono text-gray-600'>{selectedLog.request_id || '-'}</dd>
                    </div>
                    <div>
                      <dt className='text-gray-400'>Severity</dt>
                      <dd className='text-gray-600'>{selectedLog.severity}</dd>
                    </div>
                    <div>
                      <dt className='text-gray-400'>Source</dt>
                      <dd className='text-gray-600'>{selectedLog.is_middleware ? 'Middleware (Auto)' : 'Custom'}</dd>
                    </div>
                  </dl>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}

