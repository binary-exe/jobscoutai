'use client';

import { useEffect, useState } from 'react';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Check, Sparkles, Zap } from 'lucide-react';
import Link from 'next/link';
import { trackUpgradePromptViewed, trackUpgradeClicked } from '@/lib/analytics';
import { SUPPORT_EMAIL } from '@/lib/legal';

export default function PricingPage() {
  // Track pricing page view
  useEffect(() => {
    trackUpgradePromptViewed('pricing_page');
  }, []);

  const [billingCycle, setBillingCycle] = useState<'weekly' | 'monthly'>('monthly');
  const isWeekly = billingCycle === 'weekly';

  const standardPrice = isWeekly ? 4 : 19;
  const standardPeriod = isWeekly ? 'per week' : 'per month';
  const standardPacks = isWeekly ? 20 : 120;
  const standardTrackerCap = standardPacks;
  const standardPlanKey = isWeekly ? 'weekly_standard' : 'monthly_standard';

  const proPrice = isWeekly ? 9 : 39;
  const proPeriod = isWeekly ? 'per week' : 'per month';
  const proPacks = isWeekly ? 50 : 250;
  const proTrackerCap = proPacks;
  const proPlanKey = isWeekly ? 'weekly_pro' : 'monthly_pro';

  return (
    <>
      <Header />
      
      <main className="flex-1">
        <div className="container mx-auto max-w-6xl px-4 py-16">
          <div className="text-center mb-12">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Simple, Transparent Pricing
            </div>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl mb-4">
              Choose Your Plan
            </h1>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              JobScoutAI helps you land remote jobs with AI-tailored resumes and cover letters, application tracking, and trust/scam analysis so you can apply with confidence. Start with a free tier, upgrade when you need more. All plans include Trust Reports and job browsing.
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              <strong>1 Apply Pack</strong> = tailored cover letter + resume tweaks + trust report + saved to tracker
            </p>
            <p className="mt-4 text-sm text-muted-foreground max-w-xl mx-auto">
              Paid plans are <strong>billed weekly or monthly</strong>. Subscriptions <strong>renew automatically until you cancel</strong>. You may <strong>cancel anytime</strong>; cancellation stops future charges.
            </p>
            <div className="mt-6 inline-flex items-center rounded-full border border-border bg-card p-1">
              <button
                type="button"
                onClick={() => setBillingCycle('weekly')}
                className={`rounded-full px-4 py-1 text-sm font-medium transition-colors ${
                  billingCycle === 'weekly'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Weekly
              </button>
              <button
                type="button"
                onClick={() => setBillingCycle('monthly')}
                className={`rounded-full px-4 py-1 text-sm font-medium transition-colors ${
                  billingCycle === 'monthly'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Monthly
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto">
            {/* Free Plan */}
            <div className="rounded-xl border border-border bg-card p-6">
              <h3 className="text-xl font-bold mb-2">Free</h3>
              <p className="text-3xl font-bold mb-1">$0</p>
              <p className="text-sm text-muted-foreground mb-6">Forever</p>
              
              <ul className="space-y-3 mb-8 text-sm">
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>2 Apply Packs / month</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>Trust Report included</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>Limited application tracker</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>DOCX exports (up to 6 / month)</span>
                </li>
              </ul>
              
              <Link
                href="/login?next=/apply"
                className="block w-full text-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
              >
                Get Started Free
              </Link>
            </div>

            {/* Standard */}
            <div className="rounded-xl border border-border bg-card p-6">
              <h3 className="text-xl font-bold mb-2">Standard</h3>
              <p className="text-3xl font-bold mb-1">${standardPrice}</p>
              <p className="text-sm text-muted-foreground mb-6">{standardPeriod}</p>

              <ul className="space-y-3 mb-8 text-sm">
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>
                    <strong>{standardPacks}</strong> Apply Packs / {isWeekly ? 'week' : 'month'}
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>Trust Report included</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>
                    Track up to <strong>{standardTrackerCap}</strong> active applications
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>DOCX export</span>
                </li>
              </ul>

              <Link
                href={`/login?next=/account?plan=${standardPlanKey}`}
                onClick={() => trackUpgradeClicked(standardPlanKey, 'pricing_page')}
                className="block w-full text-center rounded-lg border border-primary text-primary px-4 py-2 text-sm font-medium hover:bg-primary/10 transition-colors"
              >
                Choose Standard
              </Link>
            </div>

            {/* Pro */}
            <div className="rounded-xl border-2 border-primary bg-card p-6 relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="bg-primary text-primary-foreground px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1">
                  <Zap className="h-3 w-3" />
                  Popular
                </span>
              </div>

              <h3 className="text-xl font-bold mb-2">Pro</h3>
              <p className="text-3xl font-bold mb-1">${proPrice}</p>
              <p className="text-sm text-muted-foreground mb-6">{proPeriod}</p>

              <ul className="space-y-3 mb-8 text-sm">
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>
                    <strong>{proPacks}</strong> Apply Packs / {isWeekly ? 'week' : 'month'}
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>Trust Report included</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>
                    Track up to <strong>{proTrackerCap}</strong> active applications
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>DOCX export</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>Higher Premium AI limits</span>
                </li>
              </ul>

              <Link
                href={`/login?next=/account?plan=${proPlanKey}`}
                onClick={() => trackUpgradeClicked(proPlanKey, 'pricing_page')}
                className="block w-full text-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Choose Pro
              </Link>
            </div>

          </div>

          {/* Pack Top-ups */}
          <div className="mt-12 text-center">
            <div className="inline-block rounded-xl border border-border bg-card p-6 max-w-md">
              <h3 className="font-semibold mb-2">Need more packs?</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Add extra Apply Packs anytime without changing your plan.
              </p>
              <div className="flex items-center justify-center gap-4">
                <span className="text-2xl font-bold">+20 packs</span>
                <span className="text-muted-foreground">for</span>
                <span className="text-2xl font-bold text-primary">$10</span>
              </div>
              <p className="text-xs text-muted-foreground mt-2">One-time purchase, never expires</p>
            </div>
          </div>

          {/* Key features / deliverables (Paddle: clearly state what is included with purchase) */}
          <div className="mt-16 text-center">
            <h2 className="text-xl font-semibold mb-2">Key features and deliverables included with your purchase</h2>
            <p className="text-sm text-muted-foreground max-w-2xl mx-auto mb-6">
              Depending on your plan, your purchase includes: AI-tailored cover letters and resume tweaks per job (Apply Packs), Trust Reports (scam and risk analysis for job listings), application tracking and history, DOCX export of tailored documents, access to aggregated remote job listings and search, and optional pack top-ups. Plan limits (e.g. Apply Packs per month) are shown above.
            </p>
          </div>

          {/* Value Proposition */}
          <div className="mt-12 text-center">
            <h2 className="text-xl font-semibold mb-4">Why JobScout?</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
              <div className="p-4">
                <div className="text-3xl mb-2">⏱️</div>
                <h3 className="font-medium mb-1">Save 45+ mins per app</h3>
                <p className="text-sm text-muted-foreground">
                  No more manual tailoring. AI generates personalized content in seconds.
                </p>
              </div>
              <div className="p-4">
                <div className="text-3xl mb-2">🛡️</div>
                <h3 className="font-medium mb-1">Avoid scams & ghosts</h3>
                <p className="text-sm text-muted-foreground">
                  Trust Reports flag suspicious listings before you apply.
                </p>
              </div>
              <div className="p-4">
                <div className="text-3xl mb-2">📈</div>
                <h3 className="font-medium mb-1">Track & improve</h3>
                <p className="text-sm text-muted-foreground">
                  Track applications and get better with each submission.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-12 text-center space-y-2">
            <p className="text-sm text-muted-foreground">
              Questions? Contact us at <a href={`mailto:${SUPPORT_EMAIL}`} className="text-primary underline">{SUPPORT_EMAIL}</a>
            </p>
            <p className="text-xs text-muted-foreground">
              Custom or enterprise pricing? See our{' '}
              <Link href="/enterprise-pricing" className="text-primary underline">
                Enterprise pricing sheet
              </Link>{' '}
              (and we can provide a PDF copy on request).
            </p>
          </div>
        </div>
      </main>
      
      <Footer />
    </>
  );
}
