import type { Metadata } from 'next';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import {
  PRODUCT_NAME,
  BRAND_NAME,
  OPERATOR_LEGAL_NAME,
  SUPPORT_EMAIL,
  WEBSITE_URL,
  lastUpdatedISO,
} from '@/lib/legal';

export const metadata: Metadata = {
  title: `Terms & Conditions | ${PRODUCT_NAME}`,
  description: `Terms and conditions of use for ${PRODUCT_NAME}. Service description, accounts, billing, refunds, and legal information.`,
};

export default function TermsPage() {
  return (
    <>
      <Header />
      <main className="flex-1">
        <div className="container mx-auto max-w-3xl px-4 py-12">
          <h1 className="text-3xl font-bold tracking-tight mb-2">Terms & Conditions</h1>
          <p className="text-sm text-muted-foreground mb-8">Last updated: {lastUpdatedISO}</p>

          <div className="prose prose-neutral dark:prose-invert max-w-none space-y-8 text-sm">
            <section>
              <h2 className="text-lg font-semibold mb-2">1. Who we are</h2>
              <p>
                {BRAND_NAME} (&quot;we&quot;, &quot;us&quot;, &quot;the Service&quot;) is operated by {OPERATOR_LEGAL_NAME}, a sole proprietor. These Terms govern your use of the {PRODUCT_NAME} website and services available at {WEBSITE_URL}.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">2. Service description</h2>
              <p>
                {PRODUCT_NAME} is a SaaS that helps job seekers with resume tailoring, AI-generated cover letters, application tracking, and trust/scam analysis of job listings. We aggregate and rank remote job opportunities and provide tools to tailor applications and track submissions. Features and limits depend on your plan (see our <Link href="/pricing" className="text-primary underline">Pricing</Link> page).
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">3. Accounts & acceptable use</h2>
              <p>
                You must provide accurate information when creating an account. You agree not to use the Service for any illegal purpose, to upload illegal or infringing content, to abuse or overload our systems, or to scrape or access sources we prohibit. We may suspend or terminate accounts that violate these terms.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">4. Subscription & billing</h2>
              <p>
                Paid plans are billed in accordance with the cycle you choose (e.g. monthly or annually). Subscriptions renew automatically until you cancel. You may cancel at any time; cancellation stops future renewals but does not refund the current period. Price changes will be communicated in advance where required by law.
              </p>
              <p className="mt-4 font-medium">Payments &amp; Merchant of Record</p>
              <p className="mt-2 rounded-md bg-muted p-3 text-muted-foreground">
                Our order process is conducted by our online reseller Paddle.com. Paddle.com is the Merchant of Record for all our orders. Paddle provides all customer service inquiries and handles returns.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">5. Refunds</h2>
              <p>
                Refund eligibility and process are described on our <Link href="/refunds" className="text-primary underline">Refund Policy</Link> page. Because Paddle is the Merchant of Record, Paddle handles purchase processing and returns; we work with Paddle to resolve refund requests where appropriate.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">6. Intellectual property</h2>
              <p>
                You retain ownership of the content you provide (e.g. resumes, profile information). By using the Service, you grant us a limited license to process, store, and use that content solely to provide and improve the Service. Our brand, product names, and site content are our property and may not be used without permission.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">7. Disclaimers</h2>
              <p>
                Results from our tools (including ATS-style feedback and hiring outcomes) are not guaranteed. Scam and trust analysis is best-effort and may not catch every risky listing. The Service is provided &quot;as is&quot; to the extent permitted by law.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">8. Limitation of liability</h2>
              <p>
                To the maximum extent permitted by applicable law, we and {OPERATOR_LEGAL_NAME} shall not be liable for any indirect, incidental, special, or consequential damages arising from your use of the Service. Our total liability shall not exceed the amount you paid us in the twelve months preceding the claim.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">9. Changes to terms</h2>
              <p>
                We may update these Terms from time to time. We will post the revised Terms on this page and update the &quot;Last updated&quot; date. Continued use of the Service after changes constitutes acceptance. Material changes may be communicated by email or in-app notice where appropriate.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">10. Contact</h2>
              <p>
                For questions about these Terms, contact us at{' '}
                <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary underline">{SUPPORT_EMAIL}</a> or via our <Link href="/contact" className="text-primary underline">Contact</Link> page. Governing law: {OPERATOR_LEGAL_NAME} operates under the laws of Pakistan.
              </p>
            </section>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
