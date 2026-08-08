'use client'

/**
 * Group Management Page
 * 
 * Allows admins to view, create, and manage groups.
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

interface Group {
  id: string
  name: string
  path: string | null
  subGroups: Group[]
  memberCount: number
  roles: string[]
}

export default function GroupsPage() {
  const { data: session, status } = useSession()
  const router = useRouter()

  const [groups, setGroups] = useState<Group[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null)
  const [formData, setFormData] = useState({ name: '' })
  const [actionLoading, setActionLoading] = useState(false)

  const isAdmin = session?.roles?.includes('admin')

  const fetchGroups = useCallback(async () => {
    try {
      const data = await apiClient.get<Group[]>('/api/admin/groups')
      setGroups(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load groups')
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
    fetchGroups()
  }, [session, status, isAdmin, router, fetchGroups])

  const handleCreate = async () => {
    if (!formData.name.trim()) return
    setActionLoading(true)
    try {
      await apiClient.post('/api/admin/groups', { name: formData.name.trim() })
      setCreateDialogOpen(false)
      setFormData({ name: '' })
      await fetchGroups()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create group')
    } finally {
      setActionLoading(false)
    }
  }

  const handleEdit = async () => {
    if (!selectedGroup || !formData.name.trim()) return
    setActionLoading(true)
    try {
      await apiClient.put(`/api/admin/groups/${selectedGroup.id}`, { name: formData.name.trim() })
      setEditDialogOpen(false)
      setSelectedGroup(null)
      setFormData({ name: '' })
      await fetchGroups()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update group')
    } finally {
      setActionLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!selectedGroup) return
    setActionLoading(true)
    try {
      await apiClient.delete(`/api/admin/groups/${selectedGroup.id}`)
      setDeleteDialogOpen(false)
      setSelectedGroup(null)
      await fetchGroups()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete group')
    } finally {
      setActionLoading(false)
    }
  }

  const openEditDialog = (group: Group) => {
    setSelectedGroup(group)
    setFormData({ name: group.name })
    setEditDialogOpen(true)
  }

  const openDeleteDialog = (group: Group) => {
    setSelectedGroup(group)
    setDeleteDialogOpen(true)
  }

  // Flatten groups for display (including subgroups with indentation)
  const flattenGroups = (groups: Group[], depth = 0): Array<{ group: Group; depth: number }> => {
    const result: Array<{ group: Group; depth: number }> = []
    for (const group of groups) {
      result.push({ group, depth })
      if (group.subGroups && group.subGroups.length > 0) {
        result.push(...flattenGroups(group.subGroups, depth + 1))
      }
    }
    return result
  }

  const flatGroups = flattenGroups(groups)
  const totalMembers = flatGroups.reduce((sum, { group }) => sum + group.memberCount, 0)

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
        <span className='text-gray-900 font-medium'>Groups</span>
      </div>

      {/* Header */}
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-2xl font-semibold text-gray-900'>Group Management</h1>
          <p className='text-gray-500 mt-1'>
            Manage groups and their members
          </p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)} className='gap-2'>
          <Icons.plus className='h-4 w-4' />
          Create Group
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
            <CardTitle className='text-sm font-medium text-gray-500'>Total Groups</CardTitle>
          </CardHeader>
          <CardContent>
            <div className='text-3xl font-bold'>{flatGroups.length}</div>
          </CardContent>
        </Card>
        <Card className='relative overflow-hidden'>
          <CardWatermark />
          <CardHeader className='pb-2'>
            <CardTitle className='text-sm font-medium text-gray-500'>Total Members</CardTitle>
          </CardHeader>
          <CardContent>
            <div className='text-3xl font-bold'>{totalMembers}</div>
          </CardContent>
        </Card>
        <Card className='relative overflow-hidden'>
          <CardWatermark />
          <CardHeader className='pb-2'>
            <CardTitle className='text-sm font-medium text-gray-500'>Groups with Roles</CardTitle>
          </CardHeader>
          <CardContent>
            <div className='text-3xl font-bold'>
              {flatGroups.filter(({ group }) => group.roles.length > 0).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Groups Table */}
      <Card>
        <CardHeader>
          <CardTitle>All Groups</CardTitle>
          <CardDescription>
            Click on a group to manage its members and roles
          </CardDescription>
        </CardHeader>
        <CardContent>
          {flatGroups.length === 0 ? (
            <div className='flex flex-col items-center justify-center py-12 text-gray-500'>
              <Icons.network className='h-12 w-12 mb-4 text-gray-300' />
              <p>No groups found</p>
              <p className='text-sm'>Create a group to organize users</p>
            </div>
          ) : (
            <div className='overflow-x-auto'>
              <table className='w-full'>
                <thead>
                  <tr className='border-b text-left text-sm text-gray-500'>
                    <th className='pb-3 font-medium'>Group Name</th>
                    <th className='pb-3 font-medium'>Path</th>
                    <th className='pb-3 font-medium'>Members</th>
                    <th className='pb-3 font-medium'>Roles</th>
                    <th className='pb-3 font-medium text-right'>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence mode='popLayout'>
                    {flatGroups.map(({ group, depth }) => (
                      <motion.tr
                        key={group.id}
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, x: -10 }}
                        className='border-b last:border-0 hover:bg-gray-50'
                      >
                        <td className='py-4'>
                          <div 
                            className='flex items-center gap-2'
                            style={{ paddingLeft: `${depth * 24}px` }}
                          >
                            {depth > 0 && (
                              <Icons.arrowRight className='h-3 w-3 text-gray-400' />
                            )}
                            <Icons.network className='h-4 w-4 text-blue-600' />
                            <span className='font-medium'>{group.name}</span>
                          </div>
                        </td>
                        <td className='py-4 text-sm text-gray-500'>
                          {group.path || '/'}
                        </td>
                        <td className='py-4'>
                          <span className='inline-flex items-center gap-1 text-sm'>
                            <Icons.users className='h-3 w-3' />
                            {group.memberCount}
                          </span>
                        </td>
                        <td className='py-4'>
                          <div className='flex flex-wrap gap-1'>
                            {group.roles.length > 0 ? (
                              group.roles.map((role) => (
                                <span
                                  key={role}
                                  className='inline-flex items-center rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700'
                                >
                                  {role}
                                </span>
                              ))
                            ) : (
                              <span className='text-sm text-gray-400'>—</span>
                            )}
                          </div>
                        </td>
                        <td className='py-4 text-right'>
                          <div className='flex items-center justify-end gap-2'>
                            <Button
                              size='sm'
                              variant='ghost'
                              onClick={() => openEditDialog(group)}
                            >
                              <Icons.edit className='h-4 w-4' />
                            </Button>
                            <Button
                              size='sm'
                              variant='ghost'
                              onClick={() => openDeleteDialog(group)}
                              className='text-red-600 hover:text-red-700'
                            >
                              <Icons.trash className='h-4 w-4' />
                            </Button>
                          </div>
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

      {/* Create Group Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Group</DialogTitle>
            <DialogDescription>
              Create a new group to organize users
            </DialogDescription>
          </DialogHeader>
          <div className='space-y-4 py-4'>
            <div className='space-y-2'>
              <Label htmlFor='group-name'>Group Name</Label>
              <Input
                id='group-name'
                placeholder='Enter group name'
                value={formData.name}
                onChange={(e) => setFormData({ name: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={actionLoading || !formData.name.trim()}>
              {actionLoading ? (
                <>
                  <Icons.loader className='mr-2 h-4 w-4 animate-spin' />
                  Creating...
                </>
              ) : (
                'Create Group'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Group Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Group</DialogTitle>
            <DialogDescription>
              Update group name
            </DialogDescription>
          </DialogHeader>
          <div className='space-y-4 py-4'>
            <div className='space-y-2'>
              <Label htmlFor='edit-group-name'>Group Name</Label>
              <Input
                id='edit-group-name'
                placeholder='Enter group name'
                value={formData.name}
                onChange={(e) => setFormData({ name: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEdit} disabled={actionLoading || !formData.name.trim()}>
              {actionLoading ? (
                <>
                  <Icons.loader className='mr-2 h-4 w-4 animate-spin' />
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Group</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the group &quot;{selectedGroup?.name}&quot;?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className='bg-red-600 hover:bg-red-700'
            >
              {actionLoading ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

