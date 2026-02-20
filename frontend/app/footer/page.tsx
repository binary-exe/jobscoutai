import type { Metadata } from 'next';
import Link from 'next/link';
import { Footer } from '@/components/Footer';
import { PRODUCT_NAME, WEBSITE_URL } from '@/lib/legal';

export const metadata: Metadata = {
  title: `Footer verification | ${PRODUCT_NAME}`,
  description: `Verification page for footer navigation. Main site: ${WEBSITE_URL}.`,
  robots: 'index, follow',
};

/**
 * Minimal static page for Paddle (or other reviewers) to verify footer navigation
 * when the homepage is temporarily inaccessible. Alternative URL for "Homepage (footer verification)".
 */
export default function FooterVerificationPage() {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <main className="flex-1 container mx-auto max-w-2xl px-4 py-12">
        <h1 className="text-2xl font-bold tracking-tight mb-2">Footer verification</h1>
        <p className="text-muted-foreground mb-6">
          This page confirms footer navigation and legal links for {PRODUCT_NAME}. Main homepage: <a href={WEBSITE_URL} className="text-primary underline">{WEBSITE_URL}</a>.
        </p>
        <p className="text-sm text-muted-foreground mb-8">
          If you could not access the main site, you can use this URL for footer verification. The footer below is the same as on every page of the site.
        </p>
        <ul className="text-sm space-y-1 mb-8">
          <li><Link href="/pricing" className="text-primary underline">Pricing</Link></li>
          <li><Link href="/terms" className="text-primary underline">Terms &amp; Conditions</Link></li>
          <li><Link href="/privacy" className="text-primary underline">Privacy Policy</Link></li>
          <li><Link href="/refunds" className="text-primary underline">Refund Policy</Link></li>
          <li><Link href="/contact" className="text-primary underline">Contact</Link></li>
        </ul>
      </main>
      <Footer />
    </div>
  );
}
