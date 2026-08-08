'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Logomark } from '@/components/brand'

interface FormData {
  email: string
  password: string
  confirmPassword: string
  firstName: string
  lastName: string
}

interface FormErrors {
  email?: string
  password?: string
  confirmPassword?: string
  firstName?: string
  lastName?: string
  general?: string
}

export default function RegisterPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')
  const [requiresApproval, setRequiresApproval] = useState(false)
  const [formData, setFormData] = useState<FormData>({
    email: '',
    password: '',
    confirmPassword: '',
    firstName: '',
    lastName: '',
  })
  const [errors, setErrors] = useState<FormErrors>({})

  const validatePassword = (password: string): string | null => {
    if (!password) return 'Password is required'
    if (password.length < 12) return 'Password must be at least 12 characters'
    if (!/[A-Z]/.test(password)) return 'Password must contain at least one uppercase letter'
    if (!/[a-z]/.test(password)) return 'Password must contain at least one lowercase letter'
    if (!/[0-9]/.test(password)) return 'Password must contain at least one digit'
    if (!/[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password)) {
      return 'Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)'
    }
    return null
  }

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {}

    // Email validation
    if (!formData.email) {
      newErrors.email = 'Email is required'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address'
    }

    // Password validation
    const passwordError = validatePassword(formData.password)
    if (passwordError) {
      newErrors.password = passwordError
    }

    // Confirm password validation
    if (!formData.confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password'
    } else if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match'
    }

    // Name validation
    if (!formData.firstName.trim()) {
      newErrors.firstName = 'First name is required'
    }
    if (!formData.lastName.trim()) {
      newErrors.lastName = 'Last name is required'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) {
      return
    }

    setIsLoading(true)
    setErrors({})

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''
      const response = await fetch(`${apiUrl}${basePath}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: formData.email,
          password: formData.password,
          first_name: formData.firstName,
          last_name: formData.lastName,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Registration failed')
      }

      setIsSuccess(true)
      setSuccessMessage(data.message)
      setRequiresApproval(data.requires_approval)
    } catch (error) {
      setErrors({
        general: error instanceof Error ? error.message : 'Registration failed. Please try again.',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    // Clear error when user starts typing
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }))
    }
  }

  // Success state
  if (isSuccess) {
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
              className='mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-emerald-500 shadow-xl'
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{
                delay: 0.2,
                type: 'spring',
                stiffness: 200,
                damping: 15,
              }}
            >
              <Icons.check className='h-10 w-10 text-white' />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.4 }}
            >
              <CardTitle className='text-display-5 font-bold text-brand-navy'>
                Registration Complete!
              </CardTitle>
            </motion.div>
          </CardHeader>
          <CardContent className='relative z-10 space-y-6 px-8 pb-8'>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.4 }}
              className='space-y-4'
            >
              <div className='rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center'>
                <Icons.check className='mx-auto mb-3 h-8 w-8 text-emerald-600' />
                <p className='text-sm text-emerald-800'>{successMessage}</p>
              </div>

              {requiresApproval && (
                <div className='rounded-xl border border-amber-200 bg-amber-50 p-4 text-center'>
                  <Icons.clock className='mx-auto mb-3 h-8 w-8 text-amber-600' />
                  <p className='text-sm font-medium text-amber-800'>Admin Approval Required</p>
                  <p className='mt-1 text-xs text-amber-700'>
                    Your email domain requires manual approval. An admin will review your request shortly.
                  </p>
                </div>
              )}

              <Button
                onClick={() => router.push('/auth/signin')}
                variant='gradient'
                size='lg'
                className='group w-full py-6 text-base'
              >
                Continue to Sign In
                <Icons.arrowRight className='ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1' />
              </Button>
            </motion.div>
          </CardContent>
        </Card>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95, y: 20 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
      className='w-full max-w-md'
    >
      <Card className='relative overflow-hidden bg-white shadow-float-lg transition-shadow duration-500 hover:shadow-accent'>
          <CardWatermark opacity={4} scale={1} />
          <CardHeader className='relative z-10 space-y-4 pb-6 text-center'>
            <motion.div
              className='mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-navy shadow-xl'
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{
                delay: 0.2,
                type: 'spring',
                stiffness: 200,
                damping: 15,
              }}
            >
              <Logomark variant='light' size={36} />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.4 }}
            >
              <CardTitle className='text-display-5 font-bold text-brand-navy'>
                Create Account
              </CardTitle>
              <p className='mt-2 text-sm text-muted-foreground'>
                Join the AutoPilot Command Center
              </p>
            </motion.div>
          </CardHeader>
          <CardContent className='relative z-10 px-8 pb-8'>
            <form onSubmit={handleSubmit} className='space-y-4'>
              {/* General Error */}
              {errors.general && (
                <motion.div
                  className='rounded-lg border border-red-200 bg-red-50 p-3 text-center text-sm text-red-700'
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <p>{errors.general}</p>
                </motion.div>
              )}

              {/* Name Fields */}
              <div className='grid grid-cols-2 gap-3'>
                <div className='space-y-1.5'>
                  <Label htmlFor='firstName' className='text-xs'>First Name</Label>
                  <Input
                    type='text'
                    id='firstName'
                    name='firstName'
                    value={formData.firstName}
                    onChange={handleChange}
                    className={errors.firstName ? 'border-red-300' : ''}
                    placeholder='John'
                  />
                  {errors.firstName && (
                    <p className='text-xs text-red-500'>{errors.firstName}</p>
                  )}
                </div>
                <div className='space-y-1.5'>
                  <Label htmlFor='lastName' className='text-xs'>Last Name</Label>
                  <Input
                    type='text'
                    id='lastName'
                    name='lastName'
                    value={formData.lastName}
                    onChange={handleChange}
                    className={errors.lastName ? 'border-red-300' : ''}
                    placeholder='Doe'
                  />
                  {errors.lastName && (
                    <p className='text-xs text-red-500'>{errors.lastName}</p>
                  )}
                </div>
              </div>

              {/* Email Field */}
              <div className='space-y-1.5'>
                <Label htmlFor='email' className='text-xs'>Email Address</Label>
                <Input
                  type='email'
                  id='email'
                  name='email'
                  value={formData.email}
                  onChange={handleChange}
                  className={errors.email ? 'border-red-300' : ''}
                  placeholder='you@company.com'
                />
                {errors.email && (
                  <p className='text-xs text-red-500'>{errors.email}</p>
                )}
              </div>

              {/* Password Fields */}
              <div className='space-y-1.5'>
                <Label htmlFor='password' className='text-xs'>Password</Label>
                <Input
                  type='password'
                  id='password'
                  name='password'
                  value={formData.password}
                  onChange={handleChange}
                  className={errors.password ? 'border-red-300' : ''}
                  placeholder='Create a strong password'
                />
                {errors.password ? (
                  <p className='text-xs text-red-500'>{errors.password}</p>
                ) : (
                  <p className='text-xs text-gray-400'>
                    Min 12 chars with uppercase, lowercase, number, and special character
                  </p>
                )}
              </div>

              <div className='space-y-1.5'>
                <Label htmlFor='confirmPassword' className='text-xs'>Confirm Password</Label>
                <Input
                  type='password'
                  id='confirmPassword'
                  name='confirmPassword'
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  className={errors.confirmPassword ? 'border-red-300' : ''}
                  placeholder='Re-enter your password'
                />
                {errors.confirmPassword && (
                  <p className='text-xs text-red-500'>{errors.confirmPassword}</p>
                )}
              </div>

              {/* Info box */}
              <div className='rounded-lg border border-blue-100 bg-blue-50 p-3 text-xs text-blue-700'>
                <p>
                  <strong>Note:</strong> Users from approved domains get instant access. 
                  Others will require admin approval.
                </p>
              </div>

              {/* Submit Button */}
              <Button
                type='submit'
                variant='gradient'
                size='lg'
                className='group w-full py-5 text-base'
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <div className='mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent' />
                    Creating Account...
                  </>
                ) : (
                  <>
                    Create Account
                    <Icons.arrowRight className='ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1' />
                  </>
                )}
              </Button>

              {/* Sign In Link */}
              <p className='text-center text-sm text-muted-foreground'>
                Already have an account?{' '}
                <a
                  href={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/auth/signin`}
                  className='font-medium text-brand-cornflower hover:text-brand-navy transition-colors'
                >
                  Sign in here
                </a>
              </p>
            </form>
          </CardContent>
      </Card>
    </motion.div>
  )
}

