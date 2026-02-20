import type { Metadata } from 'next';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { PRODUCT_NAME, SUPPORT_EMAIL, lastUpdatedISO } from '@/lib/legal';

export const metadata: Metadata = {
  title: `Refund Policy | ${PRODUCT_NAME}`,
  description: `Refund policy for ${PRODUCT_NAME}. How to request a refund and how cancellations work.`,
};

export default function RefundsPage() {
  return (
    <>
      <Header />
      <main className="flex-1">
        <div className="container mx-auto max-w-3xl px-4 py-12">
          <h1 className="text-3xl font-bold tracking-tight mb-2">Refund Policy</h1>
          <p className="text-sm text-muted-foreground mb-8">Last updated: {lastUpdatedISO}</p>

          <div className="prose prose-neutral dark:prose-invert max-w-none space-y-8 text-sm">
            <section>
              <h2 className="text-lg font-semibold mb-2">Refund eligibility</h2>
              <p>
                Refunds for first-time purchases requested within 14 days of the charge are eligible for a full refund. After 14 days, or for renewals, refunds are handled case-by-case (e.g. technical issues or billing errors). We aim to be fair and will work with you and our payment partner to resolve valid requests.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">How to request a refund</h2>
              <p>
                Contact us at <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary underline">{SUPPORT_EMAIL}</a> with your account email and the transaction or order details. You may also contact Paddle directly, as Paddle is the Merchant of Record and processes payments and handles returns. We will coordinate with Paddle where needed to process eligible refunds.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Cancellations</h2>
              <p>
                Cancelling your subscription stops future renewals. You will not be charged again after cancellation, but you will not receive a refund for the current billing period already paid. Access continues until the end of that period.
              </p>
            </section>

            <section>
              <p className="text-muted-foreground">
                For more on billing and payments, see our <Link href="/terms" className="text-primary underline">Terms &amp; Conditions</Link>. For general questions, visit our <Link href="/contact" className="text-primary underline">Contact</Link> page.
              </p>
            </section>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
