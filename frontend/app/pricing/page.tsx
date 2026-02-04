'use client';

import { useEffect } from 'react';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Check, Sparkles, Zap, Crown } from 'lucide-react';
import Link from 'next/link';
import { trackUpgradePromptViewed, trackUpgradeClicked } from '@/lib/analytics';

export default function PricingPage() {
  // Track pricing page view
  useEffect(() => {
    trackUpgradePromptViewed('pricing_page');
  }, []);

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
              Start with a free trial, upgrade when you need more. All plans include Trust Reports and job browsing.
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              <strong>1 Apply Pack</strong> = tailored cover letter + resume tweaks + trust report + saved to tracker
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto">
            {/* Free Plan */}
            <div className="rounded-xl border border-border bg-card p-6">
              <h3 className="text-xl font-bold mb-2">Free</h3>
              <p className="text-3xl font-bold mb-1">€0</p>
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
                  <span>Track 5 applications</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>Copy outputs</span>
                </li>
              </ul>
              
              <Link
                href="/login?next=/apply"
                className="block w-full text-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
              >
                Get Started Free
              </Link>
            </div>

            {/* Pro Plan */}
            <div className="rounded-xl border-2 border-primary bg-card p-6 relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="bg-primary text-primary-foreground px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1">
                  <Zap className="h-3 w-3" />
                  Popular
                </span>
              </div>
              
              <h3 className="text-xl font-bold mb-2">Pro</h3>
              <p className="text-3xl font-bold mb-1">€9</p>
              <p className="text-sm text-muted-foreground mb-6">per month</p>
              
              <ul className="space-y-3 mb-8 text-sm">
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span><strong>30</strong> Apply Packs / month</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>Trust Report included</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span><strong>Unlimited</strong> tracker</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>DOCX export</span>
                </li>
              </ul>
              
              <Link
                href="/login?next=/account"
                onClick={() => trackUpgradeClicked('pro', 'pricing_page')}
                className="block w-full text-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Upgrade to Pro
              </Link>
            </div>

            {/* Pro+ Plan */}
            <div className="rounded-xl border border-border bg-card p-6 relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1">
                  <Crown className="h-3 w-3" />
                  Power
                </span>
              </div>
              
              <h3 className="text-xl font-bold mb-2">Pro+</h3>
              <p className="text-3xl font-bold mb-1">€19</p>
              <p className="text-sm text-muted-foreground mb-6">per month</p>
              
              <ul className="space-y-3 mb-8 text-sm">
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span><strong>100</strong> Apply Packs / month</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>Everything in Pro</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>Priority queue</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>Advanced analytics</span>
                </li>
              </ul>
              
              <Link
                href="/login?next=/account"
                onClick={() => trackUpgradeClicked('pro_plus', 'pricing_page')}
                className="block w-full text-center rounded-lg border border-primary text-primary px-4 py-2 text-sm font-medium hover:bg-primary/10 transition-colors"
              >
                Upgrade to Pro+
              </Link>
            </div>

            {/* Annual Plan */}
            <div className="rounded-xl border border-green-500/50 bg-green-500/5 p-6 relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="bg-green-500 text-white px-3 py-1 rounded-full text-xs font-medium">
                  Save 27%
                </span>
              </div>
              
              <h3 className="text-xl font-bold mb-2">Pro Annual</h3>
              <p className="text-3xl font-bold mb-1">€79</p>
              <p className="text-sm text-muted-foreground mb-6">per year</p>
              
              <ul className="space-y-3 mb-8 text-sm">
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                  <span><strong>30</strong> Apply Packs / month</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                  <span>All Pro features</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                  <span>€29 savings vs monthly</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                  <span>Lock in current price</span>
                </li>
              </ul>
              
              <Link
                href="/login?next=/account"
                onClick={() => trackUpgradeClicked('annual', 'pricing_page')}
                className="block w-full text-center rounded-lg bg-green-500 px-4 py-2 text-sm font-medium text-white hover:bg-green-600 transition-colors"
              >
                Get Annual Plan
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
                <span className="text-2xl font-bold">+25 packs</span>
                <span className="text-muted-foreground">for</span>
                <span className="text-2xl font-bold text-primary">€5</span>
              </div>
              <p className="text-xs text-muted-foreground mt-2">One-time purchase, never expires</p>
            </div>
          </div>

          {/* Value Proposition */}
          <div className="mt-16 text-center">
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

          <div className="mt-12 text-center">
            <p className="text-sm text-muted-foreground">
              Questions? Contact us at support@jobscoutai.com
            </p>
          </div>
        </div>
      </main>
      
      <Footer />
    </>
  );
}
