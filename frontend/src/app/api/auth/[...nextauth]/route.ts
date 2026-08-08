// frontend/src/app/api/auth/[...nextauth]/route.ts
// AutoPilot Template — Auth bypass mode
// All users are auto-authenticated as "Dev User".

import NextAuth, { AuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'

const authOptions: AuthOptions = {
  providers: [
    CredentialsProvider({
      id: 'autopilot-dev',
      name: 'AutoPilot Dev',
      credentials: {},
      async authorize() {
        // Auto-authenticate as Dev User — no real credentials needed
        return {
          id: 'dev-user-001',
          name: 'Dev User',
          email: 'dev@autopilot.local',
        }
      },
    }),
  ],
  pages: {
    signIn: '/auth/signin',
  },
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  callbacks: {
    async jwt({ token }) {
      // Inject admin roles so all pages are accessible
      token.roles = ['admin', 'user']
      return token
    },
    async session({ session, token }) {
      session.roles = (token.roles as string[]) || ['admin', 'user']
      return session
    },
    async redirect({ url, baseUrl }) {
      if (url.startsWith('/')) return `${baseUrl}${url}`
      if (new URL(url).origin === baseUrl) return url
      return baseUrl
    },
  },
  secret: process.env.NEXTAUTH_SECRET || 'dev-secret-change-me',
  debug: false,
}

const handler = NextAuth(authOptions)
export { handler as GET, handler as POST }
