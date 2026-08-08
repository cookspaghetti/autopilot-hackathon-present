'use client'

import { useState } from 'react'
import { useSession } from 'next-auth/react'
import { motion } from 'framer-motion'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Avatar } from '@/components/ui/avatar'
import { Icons } from '@/components/ui/icons'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
}

// Settings sections
const settingsSections = [
  {
    id: 'notifications',
    title: 'Notifications',
    description: 'Manage how you receive notifications',
    icon: Icons.bell,
  },
  {
    id: 'security',
    title: 'Security',
    description: 'Password, 2FA, and session management',
    icon: Icons.eye,
  },
  {
    id: 'integrations',
    title: 'Integrations',
    description: 'Connected apps and services',
    icon: Icons.share,
  },
  {
    id: 'preferences',
    title: 'Preferences',
    description: 'Language, timezone, and display settings',
    icon: Icons.settings,
  },
]

function SettingToggle({
  id,
  label,
  description,
  defaultChecked = false,
}: {
  id: string
  label: string
  description: string
  defaultChecked?: boolean
}) {
  const [checked, setChecked] = useState(defaultChecked)

  return (
    <div className='flex items-center justify-between py-3'>
      <div className='space-y-0.5'>
        <Label htmlFor={id} className='text-sm font-medium text-foreground cursor-pointer'>
          {label}
        </Label>
        <p className='text-xs text-muted-foreground'>{description}</p>
      </div>
      <Switch
        id={id}
        checked={checked}
        onCheckedChange={setChecked}
      />
    </div>
  )
}

export default function SettingsPage() {
  const { data: session } = useSession()

  return (
    <motion.div
      className='space-y-8'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      {/* Header */}
      <motion.div variants={itemVariants}>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>
          Settings
        </h1>
        <p className='mt-2 text-lg text-muted-foreground'>
          Manage your account and application preferences.
        </p>
      </motion.div>

      {/* Profile Section */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>Your personal information</CardDescription>
          </CardHeader>
          <CardContent>
            <div className='flex items-center gap-6'>
              <Avatar
                src={session?.user?.image}
                fallback={session?.user?.name || session?.user?.email || '?'}
                size='lg'
                showRing
              />
              <div className='flex-1'>
                <h3 className='text-lg font-semibold text-foreground'>
                  {session?.user?.name || 'User'}
                </h3>
                <p className='text-sm text-muted-foreground'>
                  {session?.user?.email}
                </p>
                <p className='mt-1 text-xs text-muted-foreground'>
                  AutoPilot Developer
                </p>
              </div>
              <Button variant='outline'>
                <Icons.externalLink className='mr-2 h-4 w-4' />
                Edit Profile
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Settings Grid */}
      <div className='grid gap-6 md:grid-cols-2'>
        {settingsSections.map((section) => {
          const Icon = section.icon
          return (
            <motion.div key={section.id} variants={itemVariants}>
              <Card className='h-full'>
                <CardHeader>
                  <div className='flex items-center gap-3'>
                    <div className='flex h-10 w-10 items-center justify-center rounded-lg bg-brand-cornflower/10'>
                      <Icon
                        className='h-5 w-5 text-brand-cornflower'
                        strokeWidth={1.5}
                      />
                    </div>
                    <div>
                      <CardTitle className='text-base'>
                        {section.title}
                      </CardTitle>
                      <CardDescription className='text-xs'>
                        {section.description}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <Button variant='ghost' className='w-full justify-between'>
                    Configure
                    <Icons.chevronRight className='h-4 w-4' />
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          )
        })}
      </div>

      {/* Quick Settings */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>Quick Settings</CardTitle>
            <CardDescription>
              Common settings you can toggle quickly
            </CardDescription>
          </CardHeader>
          <CardContent className='divide-y divide-border'>
            <SettingToggle
              id='email-notifications'
              label='Email Notifications'
              description='Receive email notifications for important updates'
              defaultChecked={true}
            />
            <SettingToggle
              id='desktop-notifications'
              label='Desktop Notifications'
              description='Show desktop notifications when the app is open'
              defaultChecked={true}
            />
            <SettingToggle
              id='weekly-digest'
              label='Weekly Digest'
              description='Receive a weekly summary of your activity'
              defaultChecked={false}
            />
            <SettingToggle
              id='marketing-emails'
              label='Marketing Emails'
              description='Receive product updates and announcements'
              defaultChecked={false}
            />
          </CardContent>
        </Card>
      </motion.div>

      {/* Danger Zone */}
      <motion.div variants={itemVariants}>
        <Card className='border-red-200'>
          <CardHeader>
            <CardTitle className='text-red-600'>Danger Zone</CardTitle>
            <CardDescription>Irreversible actions</CardDescription>
          </CardHeader>
          <CardContent className='flex items-center justify-between'>
            <div>
              <p className='text-sm font-medium text-foreground'>
                Delete Account
              </p>
              <p className='text-xs text-muted-foreground'>
                Permanently delete your account and all associated data
              </p>
            </div>
            <Button
              variant='outline'
              className='border-red-200 text-red-600 hover:bg-red-50'
            >
              Delete Account
            </Button>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  )
}
