import type { NextConfig } from 'next'

// Handle basePath - Next.js requires either empty string or path starting with /
// but NOT just "/" alone
const getBasePath = () => {
  const path = process.env.NEXT_PUBLIC_BASE_PATH || ''
  // "/" is not a valid basePath, treat it as empty
  if (path === '/') return ''
  return path
}

const nextConfig: NextConfig = {
  basePath: getBasePath(),

  // The Command Center uses trusted local brand assets. Avoid invoking the
  // framework image optimizer (and its native Sharp dependency) in production.
  images: {
    unoptimized: true,
  },

  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001',
    INTERNAL_API_URL: process.env.INTERNAL_API_URL || 'http://backend:8000',
  },
  serverExternalPackages: [],

  // Tree-shake heavy icon/component libraries
  experimental: {
    optimizePackageImports: [
      '@radix-ui/react-icons',
      'lucide-react',
      'recharts',
      'framer-motion',
    ],
  },

  // Ensure TypeScript errors fail the build
  typescript: {
    ignoreBuildErrors: false,
  },

  // Disable source maps in production for faster builds
  productionBrowserSourceMaps: false,
}

export default nextConfig
