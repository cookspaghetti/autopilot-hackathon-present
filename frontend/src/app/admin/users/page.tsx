'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { apiClient } from '@/lib/api-client'

interface User {
  id: string
  email: string
  firstName: string | null
  lastName: string | null
  enabled: boolean
  emailVerified: boolean
  createdTimestamp: number | null
  roles: string[]
  status: 'pending' | 'approved' | 'admin' | 'revoked' | 'needs-role' | 'unknown'
}

interface Role {
  id: string
  name: string
  description: string | null
  composite: boolean
  clientRole: boolean
  userCount: number
}

type FilterStatus = 'all' | 'pending' | 'approved' | 'admin' | 'revoked'

// Dropdown menu component using Radix UI
function ActionDropdown({
  user,
  currentUserId,
  onAction,
  isLoading,
}: {
  user: User
  currentUserId: string | undefined
  onAction: (action: string, userId: string) => Promise<void>
  isLoading: boolean
}) {
  const isSelf = currentUserId === user.id

  const actions = []

  // Status-based actions
  if (user.status === 'pending') {
    actions.push({ key: 'approve', label: 'Approve', icon: Icons.check, color: 'text-emerald-600' })
    actions.push({ key: 'reject', label: 'Reject', icon: Icons.close, color: 'text-red-600' })
  }

  if (user.status === 'approved' || user.status === 'needs-role') {
    if (!user.roles.includes('admin')) {
      actions.push({ key: 'make-admin', label: 'Make Admin', icon: Icons.zap, color: 'text-purple-600' })
    }
    actions.push({ key: 'revoke', label: 'Revoke Access', icon: Icons.close, color: 'text-red-600', disabled: isSelf })
  }

  if (user.status === 'admin') {
    actions.push({ key: 'remove-admin', label: 'Remove Admin', icon: Icons.userMinus, color: 'text-amber-600', disabled: isSelf })
    actions.push({ key: 'revoke', label: 'Revoke Access', icon: Icons.close, color: 'text-red-600', disabled: isSelf })
  }

  if (user.status === 'revoked') {
    actions.push({ key: 'restore', label: 'Restore Access', icon: Icons.checkCircle, color: 'text-emerald-600' })
  }

  // Password reset (available for all active users except self)
  if (user.enabled && !isSelf) {
    actions.push({ key: 'reset-password', label: 'Reset Password', icon: Icons.key, color: 'text-blue-600' })
  }

  // Force logout (terminate all sessions)
  if (user.enabled && !isSelf) {
    actions.push({ key: 'logout', label: 'Force Logout', icon: Icons.logout, color: 'text-amber-600' })
  }

  // Manage roles (available for all active users except self)
  if (user.enabled && !isSelf) {
    actions.push({ key: 'manage-roles', label: 'Manage Roles', icon: Icons.shield, color: 'text-indigo-600' })
  }

  // Always available (except for self)
  actions.push({ key: 'delete', label: 'Delete User', icon: Icons.trash, color: 'text-red-600', disabled: isSelf, dangerous: true })

  if (actions.length === 0) {
    return <span className='text-sm text-gray-400'>No actions</span>
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size='sm' variant='outline' disabled={isLoading} className='gap-1'>
          {isLoading ? (
            <Icons.loader className='h-4 w-4 animate-spin' />
          ) : (
            <>
              Actions
              <Icons.chevronDown className='h-3 w-3' />
            </>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align='end' className='w-48'>
        {actions.map((action, idx) => {
          const Icon = action.icon
          const showSeparator = idx > 0 && action.dangerous
          return (
            <div key={action.key}>
              {showSeparator && <DropdownMenuSeparator />}
              <DropdownMenuItem
                onClick={() => onAction(action.key, user.id)}
                disabled={action.disabled}
                destructive={action.dangerous}
                className={action.disabled ? 'opacity-50' : ''}
              >
                <Icon className={`h-4 w-4 ${action.disabled ? 'text-gray-300' : action.color}`} />
                <span>{action.label}</span>
                {action.disabled && isSelf && <span className='ml-auto text-xs text-gray-400'>(you)</span>}
              </DropdownMenuItem>
            </div>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// Create User Modal using Dialog
interface CreatedUserInfo {
  email: string
  password: string
  temporaryPassword: boolean
}

function CreateUserModal({
  isOpen,
  onClose,
  onCreated,
  availableRoles,
}: {
  isOpen: boolean
  onClose: () => void
  onCreated: () => void
  availableRoles: Role[]
}) {
  const [formData, setFormData] = useState({
    email: '',
    firstName: '',
    lastName: '',
    password: '',
    role: 'user',
    temporaryPassword: true,
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [createdUser, setCreatedUser] = useState<CreatedUserInfo | null>(null)
  const [copied, setCopied] = useState(false)

  const resetForm = () => {
    setFormData({ email: '', firstName: '', lastName: '', password: '', role: 'user', temporaryPassword: true })
    setCreatedUser(null)
    setError(null)
    setCopied(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const payload: Record<string, unknown> = {
        email: formData.email,
        firstName: formData.firstName,
        lastName: formData.lastName,
        role: formData.role,
        temporaryPassword: formData.temporaryPassword,
      }
      if (formData.password) {
        payload.password = formData.password
      }
      const response = await apiClient.post('/api/admin/users', payload) as {
        email: string
        temporary_password: string
      }
      
      // Show the password to admin so they can share it
      setCreatedUser({
        email: response.email,
        password: response.temporary_password,
        temporaryPassword: formData.temporaryPassword,
      })
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user')
    } finally {
      setIsLoading(false)
    }
  }

  const copyToClipboard = async () => {
    if (createdUser) {
      const text = `Email: ${createdUser.email}\nPassword: ${createdUser.password}${createdUser.temporaryPassword ? '\n(User must change password on first login)' : ''}`
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  // Show success screen with password
  if (createdUser) {
    return (
      <Dialog open={isOpen} onOpenChange={handleClose}>
        <DialogContent className='sm:max-w-md'>
          <DialogHeader>
            <div className='flex items-center gap-3'>
              <div className='flex h-10 w-10 items-center justify-center rounded-full bg-green-100'>
                <Icons.check className='h-5 w-5 text-green-600' />
              </div>
              <div>
                <DialogTitle>User Created</DialogTitle>
                <DialogDescription>Share these credentials with the user</DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className='rounded-lg border border-gray-200 bg-gray-50 p-4'>
            <div className='mb-3'>
              <Label className='text-xs font-medium uppercase text-gray-500'>Email</Label>
              <p className='font-mono text-sm text-gray-900'>{createdUser.email}</p>
            </div>
            <div className='mb-3'>
              <Label className='text-xs font-medium uppercase text-gray-500'>Password</Label>
              <p className='font-mono text-sm text-gray-900'>{createdUser.password}</p>
            </div>
            {createdUser.temporaryPassword && (
              <div className='rounded bg-amber-50 px-3 py-2 text-xs text-amber-700'>
                ⚠️ User will be required to change password on first login
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant='outline' onClick={copyToClipboard}>
              {copied ? (
                <>
                  <Icons.check className='mr-2 h-4 w-4' />
                  Copied!
                </>
              ) : (
                <>
                  <Icons.copy className='mr-2 h-4 w-4' />
                  Copy Credentials
                </>
              )}
            </Button>
            <Button onClick={handleClose}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>Create New User</DialogTitle>
        </DialogHeader>

        {error && (
          <div className='rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700'>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className='space-y-4'>
          <div className='grid grid-cols-2 gap-4'>
            <div className='space-y-1.5'>
              <Label htmlFor='firstName'>First Name</Label>
              <Input
                id='firstName'
                type='text'
                required
                value={formData.firstName}
                onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
              />
            </div>
            <div className='space-y-1.5'>
              <Label htmlFor='lastName'>Last Name</Label>
              <Input
                id='lastName'
                type='text'
                required
                value={formData.lastName}
                onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
              />
            </div>
          </div>

          <div className='space-y-1.5'>
            <Label htmlFor='email'>Email</Label>
            <Input
              id='email'
              type='email'
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            />
          </div>

          <div className='space-y-1.5'>
            <Label htmlFor='password'>
              Password <span className='text-gray-400 font-normal'>(optional)</span>
            </Label>
            <Input
              id='password'
              type='text'
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className='font-mono'
              placeholder='Leave empty to auto-generate strong password'
            />
            <p className='text-xs text-gray-400'>
              If provided: min 12 chars, uppercase, lowercase, number, special char
            </p>
          </div>

          <div className='flex items-center gap-2'>
            <Checkbox
              id='temporaryPassword'
              checked={formData.temporaryPassword}
              onCheckedChange={(checked) => setFormData({ ...formData, temporaryPassword: checked === true })}
            />
            <Label htmlFor='temporaryPassword' className='text-sm text-gray-700 cursor-pointer'>
              Require password change on first login
            </Label>
          </div>

          <div className='space-y-1.5'>
            <Label>Initial Role</Label>
            <Select
              value={formData.role}
              onValueChange={(value) => setFormData({ ...formData, role: value })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {/* Core system roles first */}
                <SelectItem value='user'>User (Approved)</SelectItem>
                <SelectItem value='admin'>Admin</SelectItem>
                <SelectItem value='pending'>Pending Approval</SelectItem>
                {/* Custom roles */}
                {availableRoles
                  .filter((r) => !['user', 'admin', 'pending'].includes(r.name))
                  .map((role) => (
                    <SelectItem key={role.name} value={role.name}>
                      {role.name}
                      {role.description && ` - ${role.description}`}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          <DialogFooter className='pt-2'>
            <Button type='button' variant='outline' onClick={handleClose}>
              Cancel
            </Button>
            <Button type='submit' disabled={isLoading}>
              {isLoading ? (
                <Icons.loader className='mr-2 h-4 w-4 animate-spin' />
              ) : (
                <Icons.userPlus className='mr-2 h-4 w-4' />
              )}
              Create User
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// Domain Action Dialog
function DomainActionDialog({
  isOpen,
  onClose,
  actionType,
  onConfirm,
  isLoading,
}: {
  isOpen: boolean
  onClose: () => void
  actionType: 'delete' | 'revoke'
  onConfirm: (domain: string) => Promise<void>
  isLoading: boolean
}) {
  const [domain, setDomain] = useState('')

  const handleConfirm = async () => {
    if (!domain.trim()) return
    await onConfirm(domain.trim())
    setDomain('')
    onClose()
  }

  const handleClose = () => {
    setDomain('')
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className='sm:max-w-sm'>
        <DialogHeader>
          <DialogTitle>
            {actionType === 'delete' ? 'Delete Users by Domain' : 'Revoke Access by Domain'}
          </DialogTitle>
          <DialogDescription>
            {actionType === 'delete'
              ? 'All users with emails from this domain will be permanently deleted.'
              : 'All users with emails from this domain will have their access revoked.'}
          </DialogDescription>
        </DialogHeader>

        <Input
          type='text'
          placeholder='example.com'
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
        />

        <DialogFooter>
          <Button variant='outline' onClick={handleClose}>
            Cancel
          </Button>
          <Button
            variant={actionType === 'delete' ? 'destructive' : 'default'}
            onClick={handleConfirm}
            disabled={!domain.trim() || isLoading}
          >
            {isLoading && <Icons.loader className='mr-2 h-4 w-4 animate-spin' />}
            {actionType === 'delete' ? 'Delete Users' : 'Revoke Access'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Reset All Users Confirmation Dialog
function ResetAllDialog({
  isOpen,
  onClose,
  onConfirm,
  isLoading,
}: {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => Promise<void>
  isLoading: boolean
}) {
  const [confirmText, setConfirmText] = useState('')

  const handleConfirm = async () => {
    if (confirmText !== 'RESET') return
    await onConfirm()
    setConfirmText('')
    onClose()
  }

  const handleClose = () => {
    setConfirmText('')
    onClose()
  }

  return (
    <AlertDialog open={isOpen} onOpenChange={handleClose}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className='text-red-600'>⚠️ Danger Zone</AlertDialogTitle>
          <AlertDialogDescription className='space-y-2'>
            <p>This will <strong>permanently delete ALL non-admin users</strong>. This action cannot be undone.</p>
            <p className='text-red-600 font-medium'>Type RESET to confirm:</p>
          </AlertDialogDescription>
        </AlertDialogHeader>

        <Input
          type='text'
          placeholder='Type RESET to confirm'
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          className='focus-visible:ring-red-500'
        />

        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={confirmText !== 'RESET' || isLoading}
            className='bg-red-600 hover:bg-red-700'
          >
            {isLoading && <Icons.loader className='mr-2 h-4 w-4 animate-spin' />}
            Delete All Users
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

// Bulk Actions Dropdown using Radix UI
function BulkActionsDropdown({
  onDeleteByDomain,
  onRevokeByDomain,
  onResetAll,
  isLoading,
}: {
  onDeleteByDomain: () => void
  onRevokeByDomain: () => void
  onResetAll: () => void
  isLoading: boolean
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size='sm' variant='outline' disabled={isLoading} className='gap-1'>
          {isLoading ? (
            <Icons.loader className='h-4 w-4 animate-spin' />
          ) : (
            <>
              Bulk Actions
              <Icons.chevronDown className='h-3 w-3' />
            </>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align='start' className='w-64'>
        <DropdownMenuItem onClick={onDeleteByDomain}>
          <Icons.trash className='h-4 w-4 text-red-500' />
          <span>Delete users by domain...</span>
        </DropdownMenuItem>
        <DropdownMenuItem onClick={onRevokeByDomain}>
          <Icons.close className='h-4 w-4 text-amber-500' />
          <span>Revoke access by domain...</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={onResetAll} destructive>
          <Icons.alertCircle className='h-4 w-4' />
          <span>Reset all users (dangerous)</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

interface PaginatedUsersResponse {
  users: User[]
  total: number
  first: number
  max: number
}

export default function AdminUsersPage() {
  const { data: session, status: sessionStatus } = useSession()
  const router = useRouter()
  const [users, setUsers] = useState<User[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterStatus>('all')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [bulkLoading, setBulkLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)

  // Pagination state
  const [page, setPage] = useState(0)
  const [pageSize] = useState(50)
  const [totalUsers, setTotalUsers] = useState(0)
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  
  // Modal states for bulk actions
  const [domainActionType, setDomainActionType] = useState<'delete' | 'revoke' | null>(null)
  const [showResetDialog, setShowResetDialog] = useState(false)
  
  // Password reset dialog state
  const [passwordResetDialogOpen, setPasswordResetDialogOpen] = useState(false)
  const [passwordResetUser, setPasswordResetUser] = useState<User | null>(null)
  const [passwordResetForm, setPasswordResetForm] = useState({ password: '', temporary: true })
  const [passwordResetLoading, setPasswordResetLoading] = useState(false)
  const [passwordResetError, setPasswordResetError] = useState<string | null>(null)

  // Role management dialog state
  const [roleManageDialogOpen, setRoleManageDialogOpen] = useState(false)
  const [roleManageUser, setRoleManageUser] = useState<User | null>(null)
  const [availableRoles, setAvailableRoles] = useState<Role[]>([])
  const [selectedRoleToAdd, setSelectedRoleToAdd] = useState<string>('')
  const [roleManageLoading, setRoleManageLoading] = useState(false)
  const [roleManageError, setRoleManageError] = useState<string | null>(null)

  const isAdmin = session?.roles?.includes('admin')
  // Get user ID from session
  const currentUserId = session?.sub

  // Debounce search input
  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(searchQuery)
      setPage(0) // Reset to first page on new search
    }, 400)
    return () => { if (debounceTimer.current) clearTimeout(debounceTimer.current) }
  }, [searchQuery])

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
  }, [sessionStatus, isAdmin, router])

  // Re-fetch users when pagination, search, or filter changes
  useEffect(() => {
    if (sessionStatus !== 'authenticated' || !isAdmin) return
    fetchUsers()
  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchUsers is memoized via useCallback, adding it causes infinite re-render
  }, [page, debouncedSearch, sessionStatus, isAdmin])

  const fetchUsers = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        first: String(page * pageSize),
        max: String(pageSize),
      })
      if (debouncedSearch) params.set('search', debouncedSearch)

      const data = await apiClient.get<PaginatedUsersResponse>(`/api/admin/users?${params.toString()}`)
      setUsers(data.users)
      setTotalUsers(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users')
    } finally {
      setIsLoading(false)
    }
  }, [page, pageSize, debouncedSearch])

  const fetchRoles = async () => {
    try {
      const data = await apiClient.get<Role[]>('/api/admin/roles')
      setAvailableRoles(data)
    } catch {
      // Silently handle role fetch failure
    }
  }

  // Client-side status filtering (applied on top of server-side search results)
  const filteredUsers = filter === 'all' ? users : users.filter((u) => u.status === filter)
  const totalPages = Math.ceil(totalUsers / pageSize)

  const handleUserAction = async (action: string, userId: string) => {
    setActionLoading(userId)
    setError(null)

    try {
      switch (action) {
        case 'approve':
          await apiClient.post(`/api/admin/users/${userId}/approve`, {})
          break
        case 'reject':
          if (!window.confirm('Are you sure you want to reject this user?')) return
          await apiClient.post(`/api/admin/users/${userId}/reject`, {})
          break
        case 'revoke':
          if (!window.confirm('Are you sure you want to revoke this user\'s access?')) return
          await apiClient.post(`/api/admin/users/${userId}/revoke`, {})
          break
        case 'restore':
          await apiClient.post(`/api/admin/users/${userId}/restore`, {})
          break
        case 'make-admin':
          if (!window.confirm('Are you sure you want to grant admin privileges to this user?')) return
          await apiClient.post(`/api/admin/users/${userId}/make-admin`, {})
          break
        case 'remove-admin':
          if (!window.confirm('Are you sure you want to remove admin privileges from this user?')) return
          await apiClient.post(`/api/admin/users/${userId}/remove-admin`, {})
          break
        case 'delete':
          if (!window.confirm('⚠️ Are you sure you want to permanently delete this user? This cannot be undone.')) return
          await apiClient.delete(`/api/admin/users/${userId}`)
          break
        case 'reset-password':
          // Open password reset dialog
          const targetUser = users.find(u => u.id === userId)
          if (targetUser) {
            setPasswordResetUser(targetUser)
            setPasswordResetDialogOpen(true)
          }
          return // Don't refresh users list yet
        case 'logout':
          if (!window.confirm('Are you sure you want to force logout this user from all sessions?')) return
          await apiClient.post(`/api/admin/users/${userId}/logout`, {})
          break
        case 'manage-roles':
          // Open role management dialog
          const roleUser = users.find(u => u.id === userId)
          if (roleUser) {
            setRoleManageUser(roleUser)
            setRoleManageDialogOpen(true)
            setRoleManageError(null)
          }
          return // Don't refresh users list yet
      }
      await fetchUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} user`)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDomainAction = async (domain: string) => {
    setBulkLoading(true)
    setError(null)

    try {
      if (domainActionType === 'delete') {
        await apiClient.delete(`/api/admin/users/bulk?domain=${encodeURIComponent(domain)}&confirm=true`)
      } else if (domainActionType === 'revoke') {
        await apiClient.post(`/api/admin/users/bulk/revoke?domain=${encodeURIComponent(domain)}&confirm=true`, {})
      }
      await fetchUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to perform bulk action')
    } finally {
      setBulkLoading(false)
    }
  }

  const handleResetAll = async () => {
    setBulkLoading(true)
    setError(null)

    try {
      await apiClient.delete('/api/admin/users/reset?confirm=true')
      await fetchUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset users')
    } finally {
      setBulkLoading(false)
    }
  }

  const handlePasswordReset = async () => {
    if (!passwordResetUser || !passwordResetForm.password) return
    
    setPasswordResetLoading(true)
    setPasswordResetError(null)

    try {
      await apiClient.post(`/api/admin/users/${passwordResetUser.id}/reset-password`, {
        password: passwordResetForm.password,
        temporary: passwordResetForm.temporary,
      })
      setPasswordResetDialogOpen(false)
      setPasswordResetUser(null)
      setPasswordResetForm({ password: '', temporary: true })
      // Show success message or toast here if you have one
    } catch (err) {
      setPasswordResetError(err instanceof Error ? err.message : 'Failed to reset password')
    } finally {
      setPasswordResetLoading(false)
    }
  }

  const generatePassword = () => {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
    let password = ''
    // Ensure at least one of each type
    password += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[Math.floor(Math.random() * 26)]
    password += 'abcdefghijklmnopqrstuvwxyz'[Math.floor(Math.random() * 26)]
    password += '0123456789'[Math.floor(Math.random() * 10)]
    password += '!@#$%^&*'[Math.floor(Math.random() * 8)]
    // Fill the rest
    for (let i = 0; i < 12; i++) {
      password += chars[Math.floor(Math.random() * chars.length)]
    }
    // Shuffle the password
    password = password.split('').sort(() => Math.random() - 0.5).join('')
    setPasswordResetForm(prev => ({ ...prev, password }))
  }

  const handleAssignRole = async (roleName: string) => {
    if (!roleManageUser) return
    
    setRoleManageLoading(true)
    setRoleManageError(null)

    try {
      await apiClient.post(`/api/admin/users/${roleManageUser.id}/roles`, {
        role_name: roleName,
      })
      // Update the local user state
      const updatedUser = { ...roleManageUser, roles: [...roleManageUser.roles, roleName] }
      setRoleManageUser(updatedUser)
      setSelectedRoleToAdd('')
      await fetchUsers()
    } catch (err) {
      setRoleManageError(err instanceof Error ? err.message : 'Failed to assign role')
    } finally {
      setRoleManageLoading(false)
    }
  }

  const handleRemoveRole = async (roleName: string) => {
    if (!roleManageUser) return
    
    setRoleManageLoading(true)
    setRoleManageError(null)

    try {
      await apiClient.delete(`/api/admin/users/${roleManageUser.id}/roles/${roleName}`)
      // Update the local user state
      const updatedUser = { ...roleManageUser, roles: roleManageUser.roles.filter(r => r !== roleName) }
      setRoleManageUser(updatedUser)
      await fetchUsers()
    } catch (err) {
      setRoleManageError(err instanceof Error ? err.message : 'Failed to remove role')
    } finally {
      setRoleManageLoading(false)
    }
  }

  const getStatusBadge = (status: User['status']) => {
    switch (status) {
      case 'pending':
        return (
          <span className='inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700'>
            <Icons.clock className='mr-1 h-3 w-3' />
            Pending Approval
          </span>
        )
      case 'approved':
        return (
          <span className='inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700'>
            <Icons.checkCircle className='mr-1 h-3 w-3' />
            Approved
          </span>
        )
      case 'admin':
        return (
          <span className='inline-flex items-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-700'>
            <Icons.zap className='mr-1 h-3 w-3' />
            Admin
          </span>
        )
      case 'revoked':
        return (
          <span className='inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700'>
            <Icons.close className='mr-1 h-3 w-3' />
            Access Revoked
          </span>
        )
      case 'needs-role':
        return (
          <span className='inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600'>
            <Icons.alertCircle className='mr-1 h-3 w-3' />
            Needs Role
          </span>
        )
      default:
        return (
          <span className='inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600'>
            Unknown
          </span>
        )
    }
  }

  const formatDate = (timestamp: number | null) => {
    if (!timestamp) return '-'
    return new Date(timestamp).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const pendingCount = users.filter((u) => u.status === 'pending').length
  const displayedFrom = page * pageSize + 1
  const displayedTo = Math.min((page + 1) * pageSize, totalUsers)

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
          <h1 className='text-display-4 font-bold text-brand-navy'>User Management</h1>
          <p className='text-muted-foreground'>
            Manage user registrations, access, and permissions
          </p>
        </div>
        <div className='flex gap-3'>
          <Button onClick={() => setShowCreateModal(true)} variant='default'>
            <Icons.userPlus className='mr-2 h-4 w-4' />
            Create User
          </Button>
          <Button onClick={fetchUsers} variant='outline' size='sm' disabled={isLoading}>
            <Icons.refresh className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className='grid gap-4 md:grid-cols-5'>
        <Card className='relative overflow-hidden'>
          <CardWatermark opacity={2} scale={0.5} />
          <CardContent className='relative z-10 p-4'>
            <div className='flex items-center justify-between'>
              <div>
                <p className='text-sm text-muted-foreground'>Total Users</p>
                <p className='text-2xl font-bold text-brand-navy'>{totalUsers}</p>
              </div>
              <Icons.users className='h-8 w-8 text-brand-cornflower opacity-50' />
            </div>
          </CardContent>
        </Card>
        <Card className='relative overflow-hidden'>
          <CardWatermark opacity={2} scale={0.5} />
          <CardContent className='relative z-10 p-4'>
            <div className='flex items-center justify-between'>
              <div>
                <p className='text-sm text-muted-foreground'>Pending</p>
                <p className='text-2xl font-bold text-amber-600'>{pendingCount}</p>
              </div>
              <Icons.clock className='h-8 w-8 text-amber-500 opacity-50' />
            </div>
          </CardContent>
        </Card>
        <Card className='relative overflow-hidden'>
          <CardWatermark opacity={2} scale={0.5} />
          <CardContent className='relative z-10 p-4'>
            <div className='flex items-center justify-between'>
              <div>
                <p className='text-sm text-muted-foreground'>Approved</p>
                <p className='text-2xl font-bold text-emerald-600'>
                  {users.filter((u) => u.status === 'approved').length}
                </p>
              </div>
              <Icons.checkCircle className='h-8 w-8 text-emerald-500 opacity-50' />
            </div>
          </CardContent>
        </Card>
        <Card className='relative overflow-hidden'>
          <CardWatermark opacity={2} scale={0.5} />
          <CardContent className='relative z-10 p-4'>
            <div className='flex items-center justify-between'>
              <div>
                <p className='text-sm text-muted-foreground'>Admins</p>
                <p className='text-2xl font-bold text-purple-600'>
                  {users.filter((u) => u.status === 'admin').length}
                </p>
              </div>
              <Icons.zap className='h-8 w-8 text-purple-500 opacity-50' />
            </div>
          </CardContent>
        </Card>
        <Card className='relative overflow-hidden'>
          <CardWatermark opacity={2} scale={0.5} />
          <CardContent className='relative z-10 p-4'>
            <div className='flex items-center justify-between'>
              <div>
                <p className='text-sm text-muted-foreground'>Revoked</p>
                <p className='text-2xl font-bold text-red-600'>
                  {users.filter((u) => u.status === 'revoked').length}
                </p>
              </div>
              <Icons.close className='h-8 w-8 text-red-500 opacity-50' />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters & Search */}
      <Card className='relative'>
        <CardWatermark opacity={2} scale={0.8} />
        <CardContent className='relative z-10 p-4'>
          <div className='flex flex-col gap-4 md:flex-row md:items-center md:justify-between'>
            <div className='flex items-center gap-4'>
              {/* Search */}
              <div className='relative flex-1 min-w-[250px]'>
                <Icons.search className='absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
                <Input
                  type='text'
                  placeholder='Search by name or email...'
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className='pl-10'
                />
              </div>

              {/* Bulk Actions */}
              <BulkActionsDropdown
                onDeleteByDomain={() => setDomainActionType('delete')}
                onRevokeByDomain={() => setDomainActionType('revoke')}
                onResetAll={() => setShowResetDialog(true)}
                isLoading={bulkLoading}
              />
            </div>

            {/* Filter Tabs */}
            <div className='flex flex-wrap gap-2'>
              {(['all', 'pending', 'approved', 'admin', 'revoked'] as FilterStatus[]).map((status) => (
                <Button
                  key={status}
                  variant={filter === status ? 'default' : 'outline'}
                  size='sm'
                  onClick={() => setFilter(status)}
                  className='capitalize'
                >
                  {status}
                  {status === 'pending' && pendingCount > 0 && (
                    <span className='ml-1.5 rounded-full bg-amber-500 px-1.5 py-0.5 text-xs text-white'>
                      {pendingCount}
                    </span>
                  )}
                </Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error Message */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className='rounded-lg border border-red-200 bg-red-50 p-4 text-red-700'
        >
          <div className='flex items-center gap-2'>
            <Icons.alertCircle className='h-5 w-5' />
            <p>{error}</p>
            <Button
              variant='ghost'
              size='sm'
              onClick={() => setError(null)}
              className='ml-auto'
            >
              <Icons.close className='h-4 w-4' />
            </Button>
          </div>
        </motion.div>
      )}

      {/* Users Table */}
      <Card className='relative overflow-hidden'>
        <CardWatermark opacity={2} scale={1} />
        <CardHeader className='relative z-10'>
          <CardTitle className='text-lg font-semibold text-brand-navy'>
            {filter === 'all' ? 'All Users' : `${filter.charAt(0).toUpperCase() + filter.slice(1)} Users`}
            <span className='ml-2 text-sm font-normal text-gray-500'>
              {debouncedSearch
                ? `(${filteredUsers.length} of ${totalUsers} matching "${debouncedSearch}")`
                : `(${filteredUsers.length} on this page · ${totalUsers} total)`
              }
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className='relative z-10 p-0'>
          {isLoading ? (
            <div className='flex h-48 items-center justify-center'>
              <div className='h-8 w-8 animate-spin rounded-full border-4 border-brand-navy border-t-transparent' />
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className='flex h-48 flex-col items-center justify-center text-muted-foreground'>
              <Icons.users className='mb-2 h-10 w-10 opacity-50' />
              <p>No users found</p>
            </div>
          ) : (
            <div className='overflow-x-auto'>
              <table className='w-full'>
                <thead className='border-b bg-gray-50/50'>
                  <tr>
                    <th className='px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500'>
                      User
                    </th>
                    <th className='px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500'>
                      Status
                    </th>
                    <th className='px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500'>
                      Email Verified
                    </th>
                    <th className='px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500'>
                      Registered
                    </th>
                    <th className='px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500'>
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className='divide-y divide-gray-100'>
                  <AnimatePresence>
                    {filteredUsers.map((user) => (
                      <motion.tr
                        key={user.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className='hover:bg-gray-50/50 transition-colors'
                      >
                        <td className='whitespace-nowrap px-6 py-4'>
                          <div className='flex items-center gap-3'>
                            <div className='flex h-10 w-10 items-center justify-center rounded-full bg-brand-navy text-white'>
                              {user.firstName?.[0] || user.email[0].toUpperCase()}
                            </div>
                            <div>
                              <p className='font-medium text-gray-900'>
                                {user.firstName && user.lastName
                                  ? `${user.firstName} ${user.lastName}`
                                  : user.email.split('@')[0]}
                              </p>
                              <p className='text-sm text-muted-foreground'>{user.email}</p>
                            </div>
                          </div>
                        </td>
                        <td className='whitespace-nowrap px-6 py-4'>
                          {getStatusBadge(user.status)}
                        </td>
                        <td className='whitespace-nowrap px-6 py-4'>
                          {user.emailVerified ? (
                            <span className='inline-flex items-center text-sm text-emerald-600'>
                              <Icons.checkCircle className='mr-1 h-4 w-4' />
                              Verified
                            </span>
                          ) : (
                            <span className='inline-flex items-center text-sm text-gray-500'>
                              <Icons.alertCircle className='mr-1 h-4 w-4' />
                              Pending
                            </span>
                          )}
                        </td>
                        <td className='whitespace-nowrap px-6 py-4 text-sm text-gray-600'>
                          {formatDate(user.createdTimestamp)}
                        </td>
                        <td className='whitespace-nowrap px-6 py-4 text-right'>
                          <ActionDropdown
                            user={user}
                            currentUserId={currentUserId}
                            onAction={handleUserAction}
                            isLoading={actionLoading === user.id}
                          />
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination Controls */}
          {totalUsers > pageSize && (
            <div className='flex items-center justify-between border-t px-6 py-4'>
              <p className='text-sm text-muted-foreground'>
                Showing {displayedFrom}–{displayedTo} of {totalUsers} users
              </p>
              <div className='flex items-center gap-2'>
                <Button
                  size='sm'
                  variant='outline'
                  disabled={page === 0}
                  onClick={() => setPage(0)}
                >
                  <Icons.arrowLeft className='h-4 w-4' />
                  <Icons.arrowLeft className='h-4 w-4 -ml-2' />
                </Button>
                <Button
                  size='sm'
                  variant='outline'
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  <Icons.arrowLeft className='h-4 w-4' />
                  Prev
                </Button>
                <span className='px-3 text-sm font-medium text-brand-navy'>
                  Page {page + 1} of {totalPages}
                </span>
                <Button
                  size='sm'
                  variant='outline'
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                  <Icons.arrowRight className='h-4 w-4' />
                </Button>
                <Button
                  size='sm'
                  variant='outline'
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage(totalPages - 1)}
                >
                  <Icons.arrowRight className='h-4 w-4' />
                  <Icons.arrowRight className='h-4 w-4 -ml-2' />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create User Modal */}
      <CreateUserModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={fetchUsers}
        availableRoles={availableRoles}
      />

      {/* Domain Action Dialog */}
      <DomainActionDialog
        isOpen={domainActionType !== null}
        onClose={() => setDomainActionType(null)}
        actionType={domainActionType || 'delete'}
        onConfirm={handleDomainAction}
        isLoading={bulkLoading}
      />

      {/* Reset All Dialog */}
      <ResetAllDialog
        isOpen={showResetDialog}
        onClose={() => setShowResetDialog(false)}
        onConfirm={handleResetAll}
        isLoading={bulkLoading}
      />

      {/* Password Reset Dialog */}
      <Dialog 
        open={passwordResetDialogOpen} 
        onOpenChange={(open) => {
          if (!open) {
            setPasswordResetDialogOpen(false)
            setPasswordResetUser(null)
            setPasswordResetForm({ password: '', temporary: true })
            setPasswordResetError(null)
          }
        }}
      >
        <DialogContent className='sm:max-w-md'>
          <DialogHeader>
            <DialogTitle className='flex items-center gap-2'>
              <Icons.key className='h-5 w-5 text-blue-600' />
              Reset Password
            </DialogTitle>
            <DialogDescription>
              Set a new password for <strong>{passwordResetUser?.email}</strong>
            </DialogDescription>
          </DialogHeader>

          <div className='space-y-4 py-4'>
            {passwordResetError && (
              <div className='rounded-md bg-red-50 p-3 text-sm text-red-600'>
                {passwordResetError}
              </div>
            )}

            <div className='space-y-2'>
              <Label htmlFor='new-password'>New Password</Label>
              <div className='flex gap-2'>
                <Input
                  id='new-password'
                  type='text'
                  placeholder='Enter new password'
                  value={passwordResetForm.password}
                  onChange={(e) => setPasswordResetForm(prev => ({ ...prev, password: e.target.value }))}
                />
                <Button
                  type='button'
                  variant='outline'
                  onClick={generatePassword}
                  className='shrink-0'
                >
                  <Icons.zap className='h-4 w-4' />
                </Button>
              </div>
              <p className='text-xs text-gray-500'>
                Password must be at least 12 characters long.
              </p>
            </div>

            <div className='flex items-center gap-2'>
              <Checkbox
                id='temporary-password'
                checked={passwordResetForm.temporary}
                onCheckedChange={(checked) => 
                  setPasswordResetForm(prev => ({ ...prev, temporary: checked === true }))
                }
              />
              <Label htmlFor='temporary-password' className='text-sm font-normal'>
                Require password change on next login
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant='outline'
              onClick={() => setPasswordResetDialogOpen(false)}
              disabled={passwordResetLoading}
            >
              Cancel
            </Button>
            <Button
              onClick={handlePasswordReset}
              disabled={passwordResetLoading || passwordResetForm.password.length < 12}
            >
              {passwordResetLoading ? (
                <>
                  <Icons.loader className='mr-2 h-4 w-4 animate-spin' />
                  Resetting...
                </>
              ) : (
                'Reset Password'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Role Management Dialog */}
      <Dialog 
        open={roleManageDialogOpen} 
        onOpenChange={(open) => {
          if (!open) {
            setRoleManageDialogOpen(false)
            setRoleManageUser(null)
            setSelectedRoleToAdd('')
            setRoleManageError(null)
          }
        }}
      >
        <DialogContent className='sm:max-w-lg'>
          <DialogHeader>
            <DialogTitle className='flex items-center gap-2'>
              <Icons.shield className='h-5 w-5 text-indigo-600' />
              Manage Roles
            </DialogTitle>
            <DialogDescription>
              Manage roles for <strong>{roleManageUser?.email}</strong>
            </DialogDescription>
          </DialogHeader>

          <div className='space-y-4 py-4'>
            {roleManageError && (
              <div className='rounded-md bg-red-50 p-3 text-sm text-red-600'>
                {roleManageError}
              </div>
            )}

            {/* Current Roles */}
            <div className='space-y-2'>
              <Label className='text-sm font-medium'>Current Roles</Label>
              {roleManageUser?.roles && roleManageUser.roles.length > 0 ? (
                <div className='flex flex-wrap gap-2'>
                  {roleManageUser.roles.map((role) => (
                    <span
                      key={role}
                      className='inline-flex items-center gap-1.5 rounded-full bg-indigo-100 px-3 py-1 text-sm font-medium text-indigo-700'
                    >
                      {role}
                      <button
                        onClick={() => handleRemoveRole(role)}
                        disabled={roleManageLoading}
                        className='ml-1 rounded-full p-0.5 hover:bg-indigo-200 disabled:opacity-50'
                        title={`Remove ${role} role`}
                      >
                        <Icons.close className='h-3 w-3' />
                      </button>
                    </span>
                  ))}
                </div>
              ) : (
                <p className='text-sm text-gray-500'>No roles assigned</p>
              )}
            </div>

            {/* Add Role */}
            <div className='space-y-2'>
              <Label className='text-sm font-medium'>Add Role</Label>
              <div className='flex gap-2'>
                <Select
                  value={selectedRoleToAdd}
                  onValueChange={setSelectedRoleToAdd}
                >
                  <SelectTrigger className='flex-1'>
                    <SelectValue placeholder='Select a role to add...' />
                  </SelectTrigger>
                  <SelectContent>
                    {availableRoles
                      .filter((r) => !roleManageUser?.roles.includes(r.name))
                      .map((role) => (
                        <SelectItem key={role.name} value={role.name}>
                          <div className='flex items-center gap-2'>
                            <span>{role.name}</span>
                            {role.description && (
                              <span className='text-xs text-gray-400'>- {role.description}</span>
                            )}
                          </div>
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
                <Button
                  onClick={() => selectedRoleToAdd && handleAssignRole(selectedRoleToAdd)}
                  disabled={!selectedRoleToAdd || roleManageLoading}
                >
                  {roleManageLoading ? (
                    <Icons.loader className='h-4 w-4 animate-spin' />
                  ) : (
                    <Icons.plus className='h-4 w-4' />
                  )}
                </Button>
              </div>
            </div>

            {/* Available Roles Info */}
            <div className='rounded-md bg-gray-50 p-3 text-xs text-gray-600'>
              <p className='font-medium mb-1'>System Roles:</p>
              <ul className='list-disc list-inside space-y-0.5'>
                <li><strong>admin</strong> - Full administrative access</li>
                <li><strong>user</strong> - Standard approved user access</li>
                <li><strong>pending</strong> - Awaiting admin approval</li>
              </ul>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant='outline'
              onClick={() => setRoleManageDialogOpen(false)}
            >
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
