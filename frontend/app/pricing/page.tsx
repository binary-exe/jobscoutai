import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Check, Sparkles } from 'lucide-react';
import Link from 'next/link';

export default function PricingPage() {
  return (
    <>
      <Header />
      
      <main className="flex-1">
        <div className="container mx-auto max-w-5xl px-4 py-16">
          <div className="text-center mb-12">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Simple, Transparent Pricing
            </div>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl mb-4">
              Choose Your Plan
            </h1>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Start free, upgrade when you need more. All plans include Trust Reports.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {/* Free Plan */}
            <div className="rounded-xl border border-border bg-card p-8">
              <h3 className="text-2xl font-bold mb-2">Free</h3>
              <p className="text-3xl font-bold mb-1">€0</p>
              <p className="text-sm text-muted-foreground mb-6">Forever</p>
              
              <ul className="space-y-3 mb-8">
                <li className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span className="text-sm">2 Apply Packs / month</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span className="text-sm">Trust Report included</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span className="text-sm">Copy outputs</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span className="text-sm">Save up to 5 tracked applications</span>
                </li>
              </ul>
              
              <Link
                href="/apply"
                className="block w-full text-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
              >
                Get Started
              </Link>
            </div>

            {/* Paid Plan */}
            <div className="rounded-xl border-2 border-primary bg-card p-8 relative">
              <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                <span className="bg-primary text-primary-foreground px-3 py-1 rounded-full text-xs font-medium">
                  Popular
                </span>
              </div>
              
              <h3 className="text-2xl font-bold mb-2">Pro</h3>
              <p className="text-3xl font-bold mb-1">€9</p>
              <p className="text-sm text-muted-foreground mb-6">per month</p>
              
              <ul className="space-y-3 mb-8">
                <li className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span className="text-sm">30 Apply Packs / month</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span className="text-sm">Trust Report included</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span className="text-sm">Unlimited tracker</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span className="text-sm">DOCX export</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span className="text-sm">Priority queue</span>
                </li>
              </ul>
              
              <Link
                href="/apply?upgrade=true"
                className="block w-full text-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Upgrade Now
              </Link>
            </div>
          </div>

          <div className="mt-12 text-center">
            <p className="text-sm text-muted-foreground">
              All plans include access to the job board. No credit card required for free plan.
            </p>
          </div>
        </div>
      </main>
      
      <Footer />
    </>
  );
}
