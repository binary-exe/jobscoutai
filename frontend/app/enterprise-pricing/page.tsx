import type { Metadata } from 'next';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { PRODUCT_NAME, SUPPORT_EMAIL, lastUpdatedISO } from '@/lib/legal';

export const metadata: Metadata = {
  title: `Enterprise & Custom Pricing | ${PRODUCT_NAME}`,
  description:
    `Pricing ranges and guidelines for ${PRODUCT_NAME} custom and enterprise plans, available as a document for procurement on request.`,
};

export default function EnterprisePricingPage() {
  return (
    <>
      <Header />
      <main className="flex-1">
        <div className="container mx-auto max-w-3xl px-4 py-12">
          <h1 className="text-3xl font-bold tracking-tight mb-2">Enterprise &amp; Custom Pricing</h1>
          <p className="text-sm text-muted-foreground mb-8">Last updated: {lastUpdatedISO}</p>

          <div className="space-y-6">
            <p className="text-muted-foreground">
              This page provides <strong>guidelines and pricing ranges</strong> for custom and enterprise plans for {PRODUCT_NAME}.
              Final pricing depends on seats, usage volume (Apply Packs), and any custom requirements.
            </p>

            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="text-lg font-semibold mb-4">Typical plan ranges</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-muted-foreground">
                    <tr className="border-b border-border">
                      <th className="py-2 pr-4 font-medium">Plan type</th>
                      <th className="py-2 pr-4 font-medium">Typical price range</th>
                      <th className="py-2 font-medium">Includes</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-border/60">
                      <td className="py-3 pr-4 font-medium">Team</td>
                      <td className="py-3 pr-4">$99–$299 / month</td>
                      <td className="py-3">
                        Shared workspace, higher Apply Pack limits, team-level tracking, and consolidated billing.
                      </td>
                    </tr>
                    <tr className="border-b border-border/60">
                      <td className="py-3 pr-4 font-medium">Enterprise</td>
                      <td className="py-3 pr-4">$499+ / month</td>
                      <td className="py-3">
                        Custom usage limits, priority support, optional SLAs, and procurement-friendly invoicing (where available).
                      </td>
                    </tr>
                    <tr>
                      <td className="py-3 pr-4 font-medium">Custom add-ons</td>
                      <td className="py-3 pr-4">Varies</td>
                      <td className="py-3">
                        Additional Apply Packs, tailored onboarding, and plan customization based on requirements.
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="mt-4 text-xs text-muted-foreground">
                These ranges are guidelines for review/procurement and are not a binding offer.
              </p>
            </div>

            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="text-lg font-semibold mb-2">Downloadable pricing sheet</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Need a document to share internally? You can download a copy of this pricing sheet.
              </p>
              <div className="flex flex-wrap gap-3">
                <a
                  href="/enterprise-pricing-sheet.html"
                  className="rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background hover:bg-foreground/90"
                >
                  Download pricing sheet (HTML)
                </a>
                <a
                  href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent('Enterprise pricing request')}`}
                  className="rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Request PDF by email
                </a>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                If you need a PDF, email us and we can provide a PDF copy on request.
              </p>
            </div>

            <p className="text-sm text-muted-foreground">
              Back to <Link href="/pricing" className="text-primary underline">Pricing</Link> or contact us at{' '}
              <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary underline">{SUPPORT_EMAIL}</a>.
            </p>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}

