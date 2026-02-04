'use client';

import { useEffect, useState } from 'react';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Check, Sparkles, Clock, Users, Gift, ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { trackUpgradePromptViewed, trackUpgradeClicked } from '@/lib/analytics';

export default function FoundersDealPage() {
  const [spotsLeft, setSpotsLeft] = useState(500);
  
  // Track page view
  useEffect(() => {
    trackUpgradePromptViewed('pricing_page');
    
    // Simulate spots decreasing (in real app, fetch from backend)
    const stored = localStorage.getItem('founders_deal_spots');
    if (stored) {
      setSpotsLeft(parseInt(stored));
    }
  }, []);
  
  return (
    <>
      <Header />
      
      <main className="flex-1">
        <div className="container mx-auto max-w-4xl px-4 py-16">
          {/* Hero */}
          <div className="text-center mb-12">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-green-500/10 px-4 py-2 text-sm font-medium text-green-600">
              <Gift className="h-4 w-4" />
              Founder&apos;s Deal - Limited Time Only
            </div>
            
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl mb-4">
              Get JobScout Pro for <span className="text-green-500">€59/year</span>
            </h1>
            
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              Save 45% on Pro features for a full year. Only for the first 500 customers.
            </p>
            
            <div className="mt-6 flex items-center justify-center gap-6 text-sm text-muted-foreground">
              <span className="flex items-center gap-2">
                <Users className="h-4 w-4" />
                <strong className="text-foreground">{spotsLeft}</strong> spots remaining
              </span>
              <span className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                Ends February 15, 2026
              </span>
            </div>
          </div>
          
          {/* Pricing Comparison */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
            {/* Regular Price */}
            <div className="rounded-xl border border-border bg-card p-6 opacity-60">
              <div className="text-center mb-4">
                <span className="text-sm text-muted-foreground">Regular Price</span>
                <div className="text-3xl font-bold line-through text-muted-foreground">€108</div>
                <span className="text-sm text-muted-foreground">per year (€9/month)</span>
              </div>
            </div>
            
            {/* Founder's Deal */}
            <div className="rounded-xl border-2 border-green-500 bg-green-500/5 p-6 relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="bg-green-500 text-white px-4 py-1.5 rounded-full text-sm font-medium">
                  Save €49
                </span>
              </div>
              
              <div className="text-center mb-4">
                <span className="text-sm text-green-600">Founder&apos;s Deal</span>
                <div className="text-4xl font-bold text-green-600">€59</div>
                <span className="text-sm text-muted-foreground">per year (€4.92/month)</span>
              </div>
            </div>
          </div>
          
          {/* Features */}
          <div className="rounded-xl border border-border bg-card p-8 mb-8">
            <h2 className="text-xl font-semibold mb-6 text-center">Everything in Pro, locked in for a year</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[
                '30 Apply Packs every month',
                'AI-tailored cover letters',
                'Trust Reports on every job',
                'Unlimited application tracking',
                'DOCX export for ATS',
                'Priority generation queue',
                'Saved searches & alerts',
                'All future Pro features',
              ].map((feature) => (
                <div key={feature} className="flex items-center gap-3">
                  <Check className="h-5 w-5 text-green-500 shrink-0" />
                  <span>{feature}</span>
                </div>
              ))}
            </div>
          </div>
          
          {/* CTA */}
          <div className="text-center">
            <Link
              href="/login?next=/account&deal=founders"
              onClick={() => trackUpgradeClicked('founders_deal', 'founders_deal_page')}
              className="inline-flex items-center gap-2 rounded-xl bg-green-500 px-8 py-4 text-lg font-medium text-white hover:bg-green-600 transition-colors"
            >
              Claim Your Founder&apos;s Deal
              <ArrowRight className="h-5 w-5" />
            </Link>
            
            <p className="mt-4 text-sm text-muted-foreground">
              30-day money-back guarantee. No questions asked.
            </p>
          </div>
          
          {/* Social Proof / FAQ */}
          <div className="mt-16 space-y-8">
            <div className="text-center">
              <h3 className="text-lg font-semibold mb-4">Why are we offering this?</h3>
              <p className="text-muted-foreground max-w-2xl mx-auto">
                We&apos;re launching JobScout publicly and want early users who will help shape the product. 
                In return, you get lifetime access to Pro features at nearly half the price. 
                This deal will never be offered again.
              </p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
              <div className="p-4">
                <div className="text-3xl mb-2">⏱️</div>
                <h4 className="font-medium">Save 45+ mins per app</h4>
                <p className="text-sm text-muted-foreground mt-1">
                  AI generates personalized content instantly
                </p>
              </div>
              <div className="p-4">
                <div className="text-3xl mb-2">🛡️</div>
                <h4 className="font-medium">Avoid scams & ghosts</h4>
                <p className="text-sm text-muted-foreground mt-1">
                  Trust Reports flag suspicious listings
                </p>
              </div>
              <div className="p-4">
                <div className="text-3xl mb-2">📈</div>
                <h4 className="font-medium">Land interviews faster</h4>
                <p className="text-sm text-muted-foreground mt-1">
                  ATS-optimized applications get noticed
                </p>
              </div>
            </div>
          </div>
          
          {/* Final CTA */}
          <div className="mt-12 text-center">
            <p className="text-muted-foreground mb-4">
              Not ready to commit? Start with the free trial.
            </p>
            <Link
              href="/login?next=/apply"
              className="text-primary hover:underline"
            >
              Try 2 free Apply Packs →
            </Link>
          </div>
        </div>
      </main>
      
      <Footer />
    </>
  );
}
