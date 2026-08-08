// frontend/src/middleware.ts
// AutoPilot Template — No auth middleware needed in dev mode.
// All requests pass through. Auth is handled by AUTH_BYPASS on the backend.

import { NextResponse } from 'next/server'

export function middleware() {
  // Pass everything through — no authentication required
  return NextResponse.next()
}

export const config = {
  matcher: [
    // Only match app routes (skip static files, images, etc.)
    '/((?!_next/static|_next/image|favicon.ico|.*\\.svg|.*\\.png|.*\\.ico).*)',
  ],
}
