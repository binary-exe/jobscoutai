'use client';

import { useState, useEffect } from 'react';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Check, X, ExternalLink, CreditCard, Calendar, Download } from 'lucide-react';
import { getQuota, type Quota } from '@/lib/apply-api';
import Link from 'next/link';

export default function AccountPage() {
  const [quota, setQuota] = useState<Quota | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchQuota();
  }, []);

  const fetchQuota = async () => {
    try {
      const data = await getQuota();
      setQuota(data);
    } catch (err) {
      console.error('Failed to fetch quota:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async () => {
    try {
      // Get checkout URL from backend
      const userId = localStorage.getItem('jobscout_user_id') || '';
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/paddle/checkout-url`, {
        headers: {
          'X-User-ID': userId,
        },
      });
      
      if (response.ok) {
        const data = await response.json();
        // Redirect to Paddle checkout
        window.location.href = data.checkout_url;
      } else {
        alert('Failed to get checkout URL');
      }
    } catch (err) {
      alert('Failed to start checkout');
    }
  };

  return (
    <>
      <Header />
      
      <main className="flex-1">
        <div className="container mx-auto max-w-5xl px-4 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold tracking-tight mb-2">Account</h1>
            <p className="text-muted-foreground">
              Manage your plan, view usage, and subscription details.
            </p>
          </div>

          {loading ? (
            <div className="space-y-4">
              {[1, 2].map((i) => (
                <div key={i} className="rounded-xl border border-border bg-card p-6 animate-pulse">
                  <div className="h-4 bg-muted w-1/3 mb-2"></div>
                  <div className="h-3 bg-muted w-1/2"></div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-6">
              {/* Plan Status */}
              <div className="rounded-xl border border-border bg-card p-6">
                <h2 className="text-lg font-semibold mb-4">Current Plan</h2>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-2xl font-bold capitalize">{quota?.plan || 'free'}</span>
                      {quota?.plan === 'paid' && (
                        <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-500">
                          Active
                        </span>
                      )}
                    </div>
                    {quota?.plan === 'free' ? (
                      <p className="text-sm text-muted-foreground">
                        Upgrade to Pro for unlimited apply packs and DOCX exports.
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Your subscription is active. Manage it in Paddle customer portal.
                      </p>
                    )}
                  </div>
                  {quota?.plan === 'free' ? (
                    <button
                      onClick={handleUpgrade}
                      className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                    >
                      Upgrade to Pro
                    </button>
                  ) : (
                    <a
                      href="https://vendors.paddle.com"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted"
                    >
                      <ExternalLink className="h-4 w-4" />
                      Manage Subscription
                    </a>
                  )}
                </div>
              </div>

              {/* Usage Stats */}
              <div className="rounded-xl border border-border bg-card p-6">
                <h2 className="text-lg font-semibold mb-4">Usage This Month</h2>
                <div className="space-y-4">
                  {/* Apply Packs */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Apply Packs</span>
                      <span className="text-sm text-muted-foreground">
                        {quota?.apply_packs.used || 0} / {quota?.apply_packs.limit === null ? '∞' : quota?.apply_packs.limit || 0}
                      </span>
                    </div>
                    {quota?.apply_packs.limit !== null && (
                      <div className="w-full bg-muted rounded-full h-2">
                        <div
                          className="bg-primary h-2 rounded-full transition-all"
                          style={{
                            width: `${Math.min(100, ((quota?.apply_packs.used || 0) / (quota?.apply_packs.limit || 1)) * 100)}%`,
                          }}
                        />
                      </div>
                    )}
                    {!quota?.apply_packs.allowed && (
                      <p className="text-xs text-red-500 mt-1">
                        Quota exceeded. Upgrade to continue.
                      </p>
                    )}
                  </div>

                  {/* DOCX Export */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">DOCX Exports</span>
                      <span className="text-sm text-muted-foreground">
                        {quota?.plan === 'paid' ? 'Unlimited' : 'Paid only'}
                      </span>
                    </div>
                    {quota?.plan === 'free' && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Upgrade to Pro to export your apply packs as DOCX files.
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Features Comparison */}
              <div className="rounded-xl border border-border bg-card p-6">
                <h2 className="text-lg font-semibold mb-4">Plan Features</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h3 className="font-medium mb-2">Free</h3>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>2 Apply Packs / month</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Trust Reports</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Copy outputs</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Save up to 5 tracked applications</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <X className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">DOCX export</span>
                      </li>
                    </ul>
                  </div>
                  <div>
                    <h3 className="font-medium mb-2">Pro (€9/month)</h3>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>30 Apply Packs / month</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Trust Reports</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Unlimited tracker</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>DOCX export</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Priority queue</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
      
      <Footer />
    </>
  );
}
