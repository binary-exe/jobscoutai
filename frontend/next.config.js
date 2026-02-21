/** @type {import('next').NextConfig} */
const path = require('path')

const nextConfig = {
  output: 'standalone',
  // Proxy API to backend so browser uses same origin (no CORS / no 502 preflight)
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'https://jobscout-api.fly.dev/api/v1/:path*',
      },
    ]
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL
      || (process.env.VERCEL ? 'https://jobiqueue.com/api/v1' : 'http://localhost:8000/api/v1'),
  },
  webpack: (config) => {
    config.resolve = config.resolve || {}
    config.resolve.alias = config.resolve.alias || {}

    // Make "@/..." resolve to the frontend project root
    config.resolve.alias['@'] = path.resolve(__dirname)

    return config
  },
}

module.exports = nextConfig