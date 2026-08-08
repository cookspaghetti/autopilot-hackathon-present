'use client'

/**
 * Role Management Page
 * 
 * Allows admins to view, create, and delete realm roles.
 * System roles (admin, user, pending) cannot be deleted.
 */

import { useCallback, useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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

interface Role {
  id: string | null
  name: string
  description: string | null
  composite: boolean
  clientRole: boolean
  containerId: string | null
  userCount: number
}

// System roles that cannot be deleted
const SYSTEM_ROLES = ['admin', 'user', 'pending', 'offline_access', 'uma_authorization', 'default-roles-autopilot']

export default function RolesPage() {
  const { data: session, status: sessionStatus } = useSession()
  const router = useRouter()
  
  const [roles, setRoles] = useState<Role[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  
  // Create role dialog state
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [newRoleName, setNewRoleName] = useState('')
  const [newRoleDescription, setNewRoleDescription] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  
  // Delete confirmation state
  const [roleToDelete, setRoleToDelete] = useState<Role | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const isAdmin = session?.roles?.includes('admin')

  const fetchRoles = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await apiClient.get<Role[]>('/api/admin/roles')
      // Sort: system roles first, then custom roles alphabetically
      const sorted = data.sort((a, b) => {
        const aSystem = SYSTEM_ROLES.includes(a.name)
        const bSystem = SYSTEM_ROLES.includes(b.name)
        if (aSystem && !bSystem) return -1
        if (!aSystem && bSystem) return 1
        return a.name.localeCompare(b.name)
      })
      setRoles(sorted)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load roles')
    } finally {
      setIsLoading(false)
    }
  }, [])

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

    fetchRoles()
  }, [sessionStatus, isAdmin, router, fetchRoles])

  const handleCreateRole = async () => {
    if (!newRoleName.trim()) {
      setCreateError('Role name is required')
      return
    }

    // Validate role name format
    if (!/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(newRoleName)) {
      setCreateError('Role name must start with a letter and contain only letters, numbers, underscores, and hyphens')
      return
    }

    setIsCreating(true)
    setCreateError(null)

    try {
      await apiClient.post('/api/admin/roles', {
        name: newRoleName.trim(),
        description: newRoleDescription.trim(),
      })

      setSuccessMessage(`Role "${newRoleName}" created successfully`)
      setIsCreateDialogOpen(false)
      setNewRoleName('')
      setNewRoleDescription('')
      fetchRoles()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create role')
    } finally {
      setIsCreating(false)
    }
  }

  const handleDeleteRole = async () => {
    if (!roleToDelete) return

    setIsDeleting(true)

    try {
      await apiClient.delete(`/api/admin/roles/${roleToDelete.name}`)

      setSuccessMessage(`Role "${roleToDelete.name}" deleted successfully`)
      setRoleToDelete(null)
      fetchRoles()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete role')
    } finally {
      setIsDeleting(false)
    }
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
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-display-4 font-bold text-brand-navy'>Role Management</h1>
          <p className='text-muted-foreground'>
            Manage realm roles for access control
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Icons.plus className='mr-2 h-4 w-4' />
          Create Role
        </Button>
      </div>

      {/* Messages */}
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

      {/* Roles Grid */}
      <Card className='relative overflow-hidden'>
        <CardWatermark opacity={2} scale={1} />
        <CardHeader className='relative z-10'>
          <CardTitle className='text-lg font-semibold text-brand-navy'>
            Realm Roles
          </CardTitle>
          <CardDescription>
            Roles control user permissions and access levels. System roles cannot be deleted.
          </CardDescription>
        </CardHeader>
        <CardContent className='relative z-10'>
          {isLoading ? (
            <div className='flex h-40 items-center justify-center'>
              <div className='h-8 w-8 animate-spin rounded-full border-4 border-brand-navy border-t-transparent' />
            </div>
          ) : roles.length === 0 ? (
            <div className='flex h-40 flex-col items-center justify-center text-muted-foreground'>
              <Icons.shield className='h-12 w-12 mb-2 opacity-50' />
              <p>No roles found</p>
            </div>
          ) : (
            <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
              {roles.map((role) => {
                const isSystem = SYSTEM_ROLES.includes(role.name)
                return (
                  <motion.div
                    key={role.name}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`group relative rounded-xl border p-4 transition-all ${
                      isSystem 
                        ? 'border-brand-navy/20 bg-brand-navy/5' 
                        : 'border-border hover:border-brand-cornflower/40 hover:shadow-sm'
                    }`}
                  >
                    {/* Role Icon */}
                    <div className={`mb-3 inline-flex rounded-lg p-2 ${
                      role.name === 'admin' 
                        ? 'bg-red-100 text-red-600'
                        : role.name === 'user'
                        ? 'bg-emerald-100 text-emerald-600'
                        : role.name === 'pending'
                        ? 'bg-amber-100 text-amber-600'
                        : isSystem
                        ? 'bg-gray-100 text-gray-600'
                        : 'bg-brand-cornflower/10 text-brand-cornflower'
                    }`}>
                      {role.name === 'admin' ? (
                        <Icons.settings className='h-5 w-5' />
                      ) : role.name === 'user' ? (
                        <Icons.checkCircle className='h-5 w-5' />
                      ) : role.name === 'pending' ? (
                        <Icons.clock className='h-5 w-5' />
                      ) : (
                        <Icons.shield className='h-5 w-5' />
                      )}
                    </div>

                    {/* Role Info */}
                    <div className='space-y-1'>
                      <div className='flex items-center gap-2'>
                        <h3 className='font-semibold text-brand-navy'>{role.name}</h3>
                        {isSystem && (
                          <span className='rounded-full bg-brand-navy/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-brand-navy'>
                            System
                          </span>
                        )}
                      </div>
                      <p className='text-sm text-muted-foreground line-clamp-2'>
                        {role.description || 'No description'}
                      </p>
                    </div>

                    {/* User Count */}
                    <div className='mt-3 flex items-center gap-1 text-sm text-muted-foreground'>
                      <Icons.users className='h-4 w-4' />
                      <span>{role.userCount} user{role.userCount !== 1 ? 's' : ''}</span>
                    </div>

                    {/* Delete Button (non-system roles only) */}
                    {!isSystem && (
                      <Button
                        variant='ghost'
                        size='sm'
                        onClick={() => setRoleToDelete(role)}
                        className='absolute right-2 top-2 h-8 w-8 p-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:bg-red-100 hover:text-red-600'
                      >
                        <Icons.trash className='h-4 w-4' />
                      </Button>
                    )}
                  </motion.div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card className='relative overflow-hidden border-dashed'>
        <CardWatermark opacity={1} scale={0.8} />
        <CardContent className='relative z-10 py-6'>
          <div className='flex items-start gap-4'>
            <div className='rounded-lg bg-brand-cornflower/10 p-2'>
              <Icons.info className='h-5 w-5 text-brand-cornflower' />
            </div>
            <div>
              <h3 className='font-medium text-brand-navy'>Understanding Roles</h3>
              <ul className='mt-2 space-y-1 text-sm text-muted-foreground'>
                <li className='flex items-center gap-2'>
                  <div className='h-2 w-2 rounded-full bg-red-500' />
                  <span className='font-medium'>admin</span> - Full system access, can manage users and settings
                </li>
                <li className='flex items-center gap-2'>
                  <div className='h-2 w-2 rounded-full bg-emerald-500' />
                  <span className='font-medium'>user</span> - Standard access to application features
                </li>
                <li className='flex items-center gap-2'>
                  <div className='h-2 w-2 rounded-full bg-amber-500' />
                  <span className='font-medium'>pending</span> - Awaiting admin approval, limited access
                </li>
                <li className='flex items-center gap-2'>
                  <div className='h-2 w-2 rounded-full bg-gray-400' />
                  <span className='font-medium'>Custom roles</span> - Define your own roles for fine-grained access control
                </li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Create Role Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Role</DialogTitle>
            <DialogDescription>
              Create a custom role for fine-grained access control.
            </DialogDescription>
          </DialogHeader>

          <div className='space-y-4 py-4'>
            {createError && (
              <div className='flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700'>
                <Icons.alertCircle className='h-4 w-4' />
                <span>{createError}</span>
              </div>
            )}

            <div className='space-y-2'>
              <Label htmlFor='role-name'>Role Name *</Label>
              <Input
                id='role-name'
                value={newRoleName}
                onChange={(e) => setNewRoleName(e.target.value)}
                placeholder='e.g., editor, viewer, manager'
                disabled={isCreating}
              />
              <p className='text-xs text-muted-foreground'>
                Must start with a letter. Only letters, numbers, underscores, and hyphens allowed.
              </p>
            </div>

            <div className='space-y-2'>
              <Label htmlFor='role-description'>Description</Label>
              <Input
                id='role-description'
                value={newRoleDescription}
                onChange={(e) => setNewRoleDescription(e.target.value)}
                placeholder='Brief description of the role'
                disabled={isCreating}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant='outline'
              onClick={() => {
                setIsCreateDialogOpen(false)
                setNewRoleName('')
                setNewRoleDescription('')
                setCreateError(null)
              }}
              disabled={isCreating}
            >
              Cancel
            </Button>
            <Button onClick={handleCreateRole} disabled={isCreating}>
              {isCreating ? (
                <>
                  <Icons.loader className='mr-2 h-4 w-4 animate-spin' />
                  Creating...
                </>
              ) : (
                <>
                  <Icons.plus className='mr-2 h-4 w-4' />
                  Create Role
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!roleToDelete} onOpenChange={() => setRoleToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Role</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the role &quot;{roleToDelete?.name}&quot;?
              {roleToDelete && roleToDelete.userCount > 0 && (
                <span className='mt-2 block font-medium text-amber-600'>
                  Warning: This role is currently assigned to {roleToDelete.userCount} user(s).
                </span>
              )}
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteRole}
              disabled={isDeleting}
              className='bg-red-600 hover:bg-red-700'
            >
              {isDeleting ? (
                <>
                  <Icons.loader className='mr-2 h-4 w-4 animate-spin' />
                  Deleting...
                </>
              ) : (
                'Delete Role'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

