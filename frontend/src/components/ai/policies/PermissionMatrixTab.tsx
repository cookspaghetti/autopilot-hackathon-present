'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { Checkbox } from '@/components/ui/checkbox'

// Define roles and permissions
const roles = [
  { id: 'admin', label: 'Admin', description: 'Full system access' },
  { id: 'manager', label: 'Manager', description: 'Team oversight' },
  { id: 'analyst', label: 'Analyst', description: 'Data analysis' },
  { id: 'operator', label: 'Operator', description: 'Daily operations' },
  { id: 'viewer', label: 'Viewer', description: 'Read-only access' },
]

const permissions = [
  { id: 'view_dashboard', label: 'View Dashboard', category: 'General' },
  { id: 'view_reports', label: 'View Reports', category: 'General' },
  { id: 'export_data', label: 'Export Data', category: 'General' },
  { id: 'create_policies', label: 'Create Policies', category: 'AI Policies' },
  { id: 'edit_policies', label: 'Edit Policies', category: 'AI Policies' },
  { id: 'delete_policies', label: 'Delete Policies', category: 'AI Policies' },
  { id: 'view_insights', label: 'View Insights', category: 'AI Insights' },
  { id: 'trigger_analysis', label: 'Trigger Analysis', category: 'AI Insights' },
  { id: 'manage_users', label: 'Manage Users', category: 'Administration' },
  { id: 'manage_roles', label: 'Manage Roles', category: 'Administration' },
  { id: 'view_audit_logs', label: 'View Audit Logs', category: 'Administration' },
  { id: 'system_settings', label: 'System Settings', category: 'Administration' },
]

// Default permission matrix
const defaultMatrix: Record<string, string[]> = {
  admin: permissions.map(p => p.id),
  manager: ['view_dashboard', 'view_reports', 'export_data', 'create_policies', 'edit_policies', 'view_insights', 'trigger_analysis', 'manage_users'],
  analyst: ['view_dashboard', 'view_reports', 'export_data', 'view_insights', 'trigger_analysis'],
  operator: ['view_dashboard', 'view_reports', 'create_policies', 'edit_policies', 'view_insights'],
  viewer: ['view_dashboard', 'view_reports'],
}

export function PermissionMatrixTab() {
  const [matrix, setMatrix] = useState<Record<string, string[]>>(defaultMatrix)
  const [hasChanges, setHasChanges] = useState(false)

  const togglePermission = (roleId: string, permissionId: string) => {
    setMatrix(prev => {
      const rolePermissions = prev[roleId] || []
      const newPermissions = rolePermissions.includes(permissionId)
        ? rolePermissions.filter(p => p !== permissionId)
        : [...rolePermissions, permissionId]
      
      return { ...prev, [roleId]: newPermissions }
    })
    setHasChanges(true)
  }

  const hasPermission = (roleId: string, permissionId: string) => {
    return matrix[roleId]?.includes(permissionId) || false
  }

  const handleSave = () => {
    // TODO: Call API to save permission matrix
    // await savePermissionMatrix(matrix)
    void matrix // Suppress unused variable warning
    setHasChanges(false)
  }

  const handleReset = () => {
    setMatrix(defaultMatrix)
    setHasChanges(false)
  }

  // Group permissions by category
  const permissionsByCategory = permissions.reduce((acc, perm) => {
    if (!acc[perm.category]) acc[perm.category] = []
    acc[perm.category].push(perm)
    return acc
  }, {} as Record<string, typeof permissions>)

  return (
    <div className="space-y-6">
      <Card className="relative overflow-hidden">
        <CardWatermark opacity={2} scale={1} />
        <CardHeader className="relative z-10">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Icons.grid className="h-5 w-5 text-brand-purple" strokeWidth={1.5} />
                Permission Matrix
              </CardTitle>
              <CardDescription>
                Define which roles can perform which actions.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {hasChanges && (
                <span className="text-sm text-amber-600">Unsaved changes</span>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleReset}
                disabled={!hasChanges}
              >
                Reset
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={!hasChanges}
              >
                <Icons.check className="mr-1 h-4 w-4" />
                Save
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="relative z-10 overflow-x-auto">
          <table className="w-full min-w-[800px]">
            <thead>
              <tr className="border-b border-border/50">
                <th className="py-3 px-4 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Permission
                </th>
                {roles.map(role => (
                  <th
                    key={role.id}
                    className="py-3 px-4 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span>{role.label}</span>
                      <span className="text-[10px] font-normal normal-case text-muted-foreground/60">
                        {role.description}
                      </span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(permissionsByCategory).map(([category, perms]) => (
                <>
                  {/* Category Header */}
                  <tr key={category}>
                    <td
                      colSpan={roles.length + 1}
                      className="py-2 px-4 bg-muted/30 text-xs font-semibold uppercase tracking-wider text-brand-navy"
                    >
                      {category}
                    </td>
                  </tr>
                  {/* Permissions in Category */}
                  {perms.map((permission, idx) => (
                    <tr
                      key={permission.id}
                      className={cn(
                        'transition-colors hover:bg-muted/20',
                        idx !== perms.length - 1 && 'border-b border-border/30'
                      )}
                    >
                      <td className="py-3 px-4 text-sm text-foreground">
                        {permission.label}
                      </td>
                      {roles.map(role => (
                        <td key={`${role.id}-${permission.id}`} className="py-3 px-4 text-center">
                          <div className="flex justify-center">
                            <Checkbox
                              checked={hasPermission(role.id, permission.id)}
                              onCheckedChange={() => togglePermission(role.id, permission.id)}
                              className={cn(
                                'transition-all duration-200',
                                hasPermission(role.id, permission.id)
                                  ? 'border-brand-cornflower bg-brand-cornflower'
                                  : 'border-border'
                              )}
                            />
                          </div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Legend */}
      <Card className="relative overflow-hidden border-dashed">
        <CardWatermark opacity={1} scale={0.8} />
        <CardContent className="relative z-10 py-4">
          <div className="flex items-start gap-4">
            <div className="rounded-lg bg-brand-cornflower/10 p-2">
              <Icons.info className="h-5 w-5 text-brand-cornflower" />
            </div>
            <div>
              <h3 className="font-medium text-brand-navy">How Permission Matrix Works</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Changes to this matrix will affect all users with the corresponding roles.
                The matrix is applied in real-time after saving. Admin role always retains full access.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

