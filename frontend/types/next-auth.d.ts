// frontend/types/next-auth.d.ts
import NextAuth from 'next-auth'
import { JWT } from 'next-auth/jwt'

declare module 'next-auth' {
  interface Session {
    accessToken?: string
    idToken?: string
    error?: string
    accessTokenExpires?: number
    roles?: string[]
    sub?: string  // User ID from Keycloak
  }

  interface User {
    id?: string
    sub?: string
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    accessToken?: string
    accessTokenExpires?: number
    refreshToken?: string
    error?: string
    idToken?: string
  }
}
