// frontend/src/app/auth/clear-session/route.ts
// This route clears all authentication cookies to resolve OAuth conflicts
// between different environments (local dev, staging, production)

import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''
  const baseUrl = request.nextUrl.origin

  // Redirect to the sign-in page after clearing cookies
  const redirectUrl = `${baseUrl}${basePath}/auth/signin`
  const response = NextResponse.redirect(redirectUrl)

  // List of all NextAuth and auth-related cookies to clear
  const cookiesToClear = [
    'next-auth.session-token',
    '__Secure-next-auth.session-token',
    'next-auth.csrf-token',
    '__Secure-next-auth.csrf-token',
    'next-auth.callback-url',
    '__Secure-next-auth.callback-url',
    'next-auth.pkce.code_verifier',
    '__Secure-next-auth.pkce.code_verifier',
    'next-auth.state',
    '__Secure-next-auth.state',
    // Also try with the base path prefix if set
    `${basePath.replace('/', '')}.next-auth.session-token`,
    `${basePath.replace('/', '')}.__Secure-next-auth.session-token`,
  ]

  // Clear each cookie by setting it to expire immediately
  cookiesToClear.forEach((cookieName) => {
    // Clear for root path
    response.cookies.set(cookieName, '', {
      expires: new Date(0),
      path: '/',
    })

    // Also clear for base path if set
    if (basePath) {
      response.cookies.set(cookieName, '', {
        expires: new Date(0),
        path: basePath,
      })
    }

    // Clear with httpOnly and secure flags (for production cookies)
    response.cookies.set(cookieName, '', {
      expires: new Date(0),
      path: '/',
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
    })
  })

  console.log(
    `[AUTH] Session cleared. Redirecting to: ${redirectUrl}. Cookies cleared: ${cookiesToClear.length}`
  )

  return response
}

