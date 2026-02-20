import type { Metadata } from 'next';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { PRODUCT_NAME, SUPPORT_EMAIL, lastUpdatedISO } from '@/lib/legal';

export const metadata: Metadata = {
  title: `Privacy Policy | ${PRODUCT_NAME}`,
  description: `Privacy policy for ${PRODUCT_NAME}. What data we collect, how we use it, and your rights.`,
};

export default function PrivacyPage() {
  return (
    <>
      <Header />
      <main className="flex-1">
        <div className="container mx-auto max-w-3xl px-4 py-12">
          <h1 className="text-3xl font-bold tracking-tight mb-2">Privacy Policy</h1>
          <p className="text-sm text-muted-foreground mb-8">Last updated: {lastUpdatedISO}</p>

          <div className="prose prose-neutral dark:prose-invert max-w-none space-y-8 text-sm">
            <section>
              <h2 className="text-lg font-semibold mb-2">What data we collect</h2>
              <p>
                We collect: (1) account information such as email address when you sign up; (2) content you provide, including resume text, job descriptions you submit, and application notes; (3) usage data such as which features you use and how you interact with the site; (4) technical data such as IP address and browser type for security and analytics.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Why we process it</h2>
              <p>
                We process your data to provide the Service (e.g. generating tailored content, storing applications, running trust analysis), to improve our features and reliability, to communicate with you (e.g. support, product updates), and to comply with legal obligations.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Processors and subprocessors</h2>
              <p>
                We use the following services to operate the product. Each processes data in accordance with their own privacy and data processing terms:
              </p>
              <ul className="list-disc pl-6 space-y-1 mt-2">
                <li><strong>Supabase</strong> — authentication and database</li>
                <li><strong>Vercel</strong> — hosting and serverless functions</li>
                <li><strong>PostHog</strong> — product analytics (when enabled)</li>
                <li><strong>OpenAI</strong> — AI/LLM features (e.g. cover letters, summaries)</li>
                <li><strong>Paddle</strong> — payment processing and merchant of record</li>
                <li><strong>Resend</strong> — transactional email (when configured)</li>
              </ul>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Data retention</h2>
              <p>
                We retain your account and application data for as long as your account is active. You may request deletion of your data; we will delete or anonymize it in line with our retention policy and legal obligations.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Your rights</h2>
              <p>
                You have the right to access, correct, and request deletion of your personal data. You may also object to or restrict certain processing where applicable by law. To exercise these rights, contact us at <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary underline">{SUPPORT_EMAIL}</a>.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Security</h2>
              <p>
                We use industry-standard measures to protect your data (e.g. encryption in transit, access controls, secure hosting). No system is completely secure; we will notify you of significant breaches where required by law.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Contact</h2>
              <p>
                For privacy-related questions or requests, contact us at{' '}
                <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary underline">{SUPPORT_EMAIL}</a> or via our <Link href="/contact" className="text-primary underline">Contact</Link> page.
              </p>
            </section>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
