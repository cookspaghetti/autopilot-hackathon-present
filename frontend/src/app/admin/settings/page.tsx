'use client'

import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiClient } from '@/lib/api-client'

interface ApprovedDomainsResponse {
  domains: string[]
  message: string
}

export default function AdminSettingsPage() {
  const { data: session, status: sessionStatus } = useSession()
  const router = useRouter()
  const [domains, setDomains] = useState<string[]>([])
  const [newDomain, setNewDomain] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [originalDomains, setOriginalDomains] = useState<string[]>([])

  const isAdmin = session?.roles?.includes('admin')

  useEffect(() => {
    if (sessionStatus === 'loading') return

    if (sessionStatus === 'unauthenticated') {
      router.push('/auth/signin')
      return
    }

    if (!isAdmin) {
      router.push('/')
      return
    }

    fetchDomains()
  }, [sessionStatus, isAdmin, router])

  useEffect(() => {
    // Check if domains have changed from original
    const changed = JSON.stringify(domains.sort()) !== JSON.stringify(originalDomains.sort())
    setHasChanges(changed)
  }, [domains, originalDomains])

  const fetchDomains = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await apiClient.get<ApprovedDomainsResponse>('/api/admin/settings/approved-domains')
      setDomains(data.domains)
      setOriginalDomains(data.domains)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings')
    } finally {
      setIsLoading(false)
    }
  }

  const handleAddDomain = () => {
    const domain = newDomain.trim().toLowerCase()
    if (!domain) return

    // Basic validation
    if (!domain.includes('.') || domain.includes(' ')) {
      setError('Invalid domain format')
      return
    }

    if (domains.includes(domain)) {
      setError('Domain already exists')
      return
    }

    setDomains([...domains, domain])
    setNewDomain('')
    setError(null)
    setSuccessMessage(null)
  }

  const handleRemoveDomain = (domainToRemove: string) => {
    setDomains(domains.filter((d) => d !== domainToRemove))
    setSuccessMessage(null)
  }

  const handleSave = async () => {
    setIsSaving(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const data = await apiClient.post<ApprovedDomainsResponse>(
        '/api/admin/settings/approved-domains',
        { domains }
      )
      setOriginalDomains(data.domains)
      setSuccessMessage('Settings saved successfully!')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setIsSaving(false)
    }
  }

  const handleReset = () => {
    setDomains([...originalDomains])
    setNewDomain('')
    setError(null)
    setSuccessMessage(null)
  }

  if (sessionStatus === 'loading' || (sessionStatus === 'authenticated' && !isAdmin)) {
    return (
      <div className='flex h-full items-center justify-center'>
        <div className='h-8 w-8 animate-spin rounded-full border-4 border-brand-navy border-t-transparent' />
      </div>
    )
  }

  return (
    <div className='space-y-6'>
      {/* Header */}
      <div>
        <h1 className='text-display-4 font-bold text-brand-navy'>Admin Settings</h1>
        <p className='text-muted-foreground'>
          Configure system-wide settings and access controls
        </p>
      </div>

      {/* Approved Domains Card */}
      <Card className='relative overflow-hidden'>
        <CardWatermark opacity={2} scale={1} />
        <CardHeader className='relative z-10'>
          <CardTitle className='text-lg font-semibold text-brand-navy'>
            Approved Email Domains
          </CardTitle>
          <CardDescription>
            Users who register with email addresses from these domains will automatically 
            receive the <span className='font-medium text-emerald-600'>user</span> role 
            and instant access. Users from other domains will require admin approval.
          </CardDescription>
        </CardHeader>
        <CardContent className='relative z-10 space-y-4'>
          {/* Error Message */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className='flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700'
              >
                <Icons.alertCircle className='h-4 w-4' />
                <span>{error}</span>
                <Button
                  variant='ghost'
                  size='sm'
                  onClick={() => setError(null)}
                  className='ml-auto h-6 w-6 p-0'
                >
                  <Icons.close className='h-3 w-3' />
                </Button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Success Message */}
          <AnimatePresence>
            {successMessage && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className='flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700'
              >
                <Icons.checkCircle className='h-4 w-4' />
                <span>{successMessage}</span>
                <Button
                  variant='ghost'
                  size='sm'
                  onClick={() => setSuccessMessage(null)}
                  className='ml-auto h-6 w-6 p-0'
                >
                  <Icons.close className='h-3 w-3' />
                </Button>
              </motion.div>
            )}
          </AnimatePresence>

          {isLoading ? (
            <div className='flex h-32 items-center justify-center'>
              <div className='h-8 w-8 animate-spin rounded-full border-4 border-brand-navy border-t-transparent' />
            </div>
          ) : (
            <>
              {/* Domain List */}
              <div className='space-y-2'>
                <Label>Current Domains</Label>
                {domains.length === 0 ? (
                  <p className='text-sm text-muted-foreground italic'>
                    No approved domains configured. All registrations will require admin approval.
                  </p>
                ) : (
                  <div className='flex flex-wrap gap-2'>
                    <AnimatePresence>
                      {domains.map((domain) => (
                        <motion.div
                          key={domain}
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.9 }}
                          className='group flex items-center gap-2 rounded-full bg-brand-navy/10 px-3 py-1.5 text-sm text-brand-navy'
                        >
                          <span>@{domain}</span>
                          <button
                            onClick={() => handleRemoveDomain(domain)}
                            className='rounded-full p-0.5 text-brand-navy/60 transition-colors hover:bg-red-100 hover:text-red-600'
                            title='Remove domain'
                          >
                            <Icons.close className='h-3 w-3' />
                          </button>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                )}
              </div>

              {/* Add Domain */}
              <div className='space-y-2'>
                <Label>Add Domain</Label>
                <div className='flex gap-2'>
                  <div className='relative flex-1'>
                    <span className='absolute left-3 top-1/2 -translate-y-1/2 text-gray-400'>@</span>
                    <Input
                      type='text'
                      value={newDomain}
                      onChange={(e) => setNewDomain(e.target.value.toLowerCase())}
                      onKeyDown={(e) => e.key === 'Enter' && handleAddDomain()}
                      placeholder='example.com'
                      className='pl-8'
                    />
                  </div>
                  <Button onClick={handleAddDomain} variant='outline'>
                    <Icons.plus className='mr-1 h-4 w-4' />
                    Add
                  </Button>
                </div>
              </div>

              {/* Save/Reset Buttons */}
              <div className='flex items-center justify-between border-t pt-4'>
                <p className='text-sm text-muted-foreground'>
                  {hasChanges ? (
                    <span className='text-amber-600'>You have unsaved changes</span>
                  ) : (
                    'All changes saved'
                  )}
                </p>
                <div className='flex gap-2'>
                  <Button
                    variant='outline'
                    onClick={handleReset}
                    disabled={!hasChanges || isSaving}
                  >
                    Reset
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={!hasChanges || isSaving}
                  >
                    {isSaving ? (
                      <>
                        <Icons.loader className='mr-2 h-4 w-4 animate-spin' />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Icons.check className='mr-2 h-4 w-4' />
                        Save Changes
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Additional Settings Info */}
      <Card className='relative overflow-hidden border-dashed'>
        <CardWatermark opacity={1} scale={0.8} />
        <CardContent className='relative z-10 py-6'>
          <div className='flex items-start gap-4'>
            <div className='rounded-lg bg-brand-cornflower/10 p-2'>
              <Icons.info className='h-5 w-5 text-brand-cornflower' />
            </div>
            <div>
              <h3 className='font-medium text-brand-navy'>How Domain Approval Works</h3>
              <ul className='mt-2 space-y-1 text-sm text-muted-foreground'>
                <li className='flex items-center gap-2'>
                  <Icons.checkCircle className='h-4 w-4 text-emerald-500' />
                  Users from approved domains get the <span className='font-medium'>user</span> role automatically
                </li>
                <li className='flex items-center gap-2'>
                  <Icons.clock className='h-4 w-4 text-amber-500' />
                  Users from other domains get the <span className='font-medium'>pending</span> role and await approval
                </li>
                <li className='flex items-center gap-2'>
                  <Icons.zap className='h-4 w-4 text-purple-500' />
                  Admins can manually approve, reject, or promote users in the User Management page
                </li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
