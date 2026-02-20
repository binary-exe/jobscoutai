import type { Metadata } from 'next';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { PRODUCT_NAME, COMPANY_LEGAL_NAME, SUPPORT_EMAIL, WEBSITE_URL } from '@/lib/legal';

export const metadata: Metadata = {
  title: `Custom & Enterprise Pricing | ${PRODUCT_NAME}`,
  description: `Custom and enterprise pricing guidelines and ranges for ${PRODUCT_NAME}. Request a quote or pricing sheet for your team.`,
};

/**
 * Custom/Enterprise pricing page. Content can be shared as a link or exported to PDF
 * and emailed to Paddle (or partners) for domain review / procurement.
 */
export default function EnterprisePricingPage() {
  return (
    <>
      <Header />
      <main className="flex-1">
        <div className="container mx-auto max-w-3xl px-4 py-12">
          <h1 className="text-3xl font-bold tracking-tight mb-2">Custom &amp; Enterprise Pricing</h1>
          <p className="text-muted-foreground mb-8">
            Guidelines and ranges for teams and organizations. Offered by {COMPANY_LEGAL_NAME}.
          </p>

          <div className="prose prose-neutral dark:prose-invert max-w-none space-y-6 text-sm">
            <section>
              <h2 className="text-lg font-semibold mb-2">Who it’s for</h2>
              <p>
                Custom and enterprise plans are for teams, career centers, bootcamps, or organizations that need higher volume, dedicated support, SSO, or custom terms. Standard self-serve plans are on our <Link href="/pricing" className="text-primary underline">Pricing</Link> page.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Pricing guidelines and ranges</h2>
              <ul className="list-disc pl-6 space-y-2">
                <li><strong>Starter team (5–20 users):</strong> Typically from $99–$299/month depending on Apply Pack volume and features.</li>
                <li><strong>Growth (20–100 users):</strong> Custom quote; ranges generally $299–$799/month with volume discounts.</li>
                <li><strong>Enterprise (100+ users, SSO, SLA):</strong> Custom quote; contact us with headcount and requirements.</li>
              </ul>
              <p className="mt-3 text-muted-foreground">
                All custom/enterprise pricing is quoted in USD unless otherwise agreed. Volume discounts and annual commitments can reduce effective per-seat or per-pack cost. Payment terms (e.g. net-30) available for qualified accounts.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">What’s included</h2>
              <p>
                Custom and enterprise plans can include: higher or unlimited Apply Pack quotas, extended application tracking limits, DOCX exports, Trust Reports, optional SSO/SAML, dedicated support channel, and custom contract/DPA. Exact deliverables are defined in the quote or order form.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">How to get a quote or pricing sheet</h2>
              <p>
                Email us at <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary underline">{SUPPORT_EMAIL}</a> with your organization name, approximate number of users or expected Apply Pack volume, and any requirements (SSO, SLA, contract). We will send a formal quote and, on request, a downloadable pricing sheet (e.g. PDF) for your procurement or finance team.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-muted/30 p-4">
              <p className="text-xs text-muted-foreground">
                This page is the official reference for custom and enterprise pricing guidelines. You may share this URL ({WEBSITE_URL}/pricing/enterprise) or export it to PDF and email it to partners or reviewers (e.g. Paddle domain review).
              </p>
            </section>
          </div>

          <div className="mt-10 flex flex-wrap gap-4">
            <Link href="/pricing" className="text-sm font-medium text-primary underline">
              ← Back to Pricing
            </Link>
            <Link href="/contact" className="text-sm font-medium text-primary underline">
              Contact us
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
