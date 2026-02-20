import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { AnalyticsProvider } from '@/components/AnalyticsProvider'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
})

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: 'JobScoutAI - Find Remote Jobs & Tailor Applications',
  description: 'JobScoutAI helps you find remote jobs and apply faster with AI-tailored resumes, cover letters, application tracking, and trust/scam analysis.',
  keywords: ['remote jobs', 'automation engineer', 'job search', 'tech jobs', 'AI jobs'],
  icons: {
    icon: [
      { url: '/favicon.ico' },
      { url: '/icon.svg', type: 'image/svg+xml' },
    ],
  },
  openGraph: {
    title: 'JobScoutAI - Find Remote Jobs & Tailor Applications',
    description: 'Find remote jobs and apply faster with AI-tailored resumes and cover letters.',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'JobScoutAI',
    description: 'Find remote jobs and apply faster with AI-tailored resumes and cover letters.',
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
        <AnalyticsProvider>
          {children}
        </AnalyticsProvider>
      </body>
    </html>
  )
}
