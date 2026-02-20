import type { Metadata } from 'next';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { PRODUCT_NAME, SUPPORT_EMAIL } from '@/lib/legal';

export const metadata: Metadata = {
  title: `Contact | ${PRODUCT_NAME}`,
  description: `Contact ${PRODUCT_NAME} for support, billing, or general inquiries.`,
};

export default function ContactPage() {
  return (
    <>
      <Header />
      <main className="flex-1">
        <div className="container mx-auto max-w-2xl px-4 py-12">
          <h1 className="text-3xl font-bold tracking-tight mb-2">Contact us</h1>
          <p className="text-muted-foreground mb-8">
            Have a question about pricing, refunds, or your account? We typically respond within 24–48 hours.
          </p>

          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold mb-2">Email</h2>
              <p>
                <a
                  href={`mailto:${SUPPORT_EMAIL}`}
                  className="text-primary underline font-medium"
                >
                  {SUPPORT_EMAIL}
                </a>
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                Use this for support, billing questions, refund requests, or to request a custom/enterprise pricing sheet (we can provide a downloadable PDF or document for your procurement team on request).
              </p>
            </div>

            <div className="pt-4 border-t border-border">
              <p className="text-sm text-muted-foreground">
                For pricing and plans, see our <Link href="/pricing" className="text-primary underline">Pricing</Link> page. For refund eligibility and how to request a refund, see our <Link href="/refunds" className="text-primary underline">Refund Policy</Link>.
              </p>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
