import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
})

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: 'JobScout - Find Your Perfect Remote Job',
  description: 'AI-powered job aggregator for remote work opportunities. Find automation, engineering, and tech jobs from top companies.',
  keywords: ['remote jobs', 'automation engineer', 'job search', 'tech jobs', 'AI jobs'],
  icons: {
    icon: [
      { url: '/favicon.ico' },
      { url: '/icon.svg', type: 'image/svg+xml' },
    ],
  },
  openGraph: {
    title: 'JobScout - Find Your Perfect Remote Job',
    description: 'AI-powered job aggregator for remote work opportunities.',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'JobScout',
    description: 'AI-powered job aggregator for remote work opportunities.',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen flex flex-col">
        {children}
      </body>
    </html>
  )
}
