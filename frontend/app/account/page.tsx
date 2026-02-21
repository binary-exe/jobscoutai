'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Check, ExternalLink, Loader2, Gift, Copy, CheckCircle2 } from 'lucide-react';
import { getQuota, type Quota } from '@/lib/apply-api';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import { trackReferralLinkCopied, setUserProperties } from '@/lib/analytics';

interface ReferralStats {
  referral_code: string;
  referral_link: string;
  completed_referrals: number;
  pending_referrals: number;
  total_packs_earned: number;
}

export default function AccountPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [authChecked, setAuthChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [referralStats, setReferralStats] = useState<ReferralStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgradeLoading, setUpgradeLoading] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [autoCheckoutStarted, setAutoCheckoutStarted] = useState(false);

  const planKey = (quota?.plan || 'free').toLowerCase();
  const planLabels: Record<string, string> = {
    free: 'Free',
    weekly_standard: 'Standard Weekly',
    weekly_pro: 'Pro Weekly',
    weekly_sprint: 'Sprint Weekly',
    monthly_standard: 'Standard Monthly',
    monthly_pro: 'Pro Monthly',
    monthly_power: 'Power Monthly',
    annual_pro: 'Annual Pro',
    annual_power: 'Annual Power',
    pro: 'Pro (Legacy)',
    pro_plus: 'Pro+ (Legacy)',
    annual: 'Annual (Legacy)',
    paid: 'Paid (Legacy)',
  };
  const planLabel = planLabels[planKey] || (quota?.plan || 'Free');
  const isPaidPlan = planKey !== 'free';
  const planParam = searchParams.get('plan')?.toLowerCase() || undefined;

  // Auth check
  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (!isSupabaseConfigured()) {
        setAuthChecked(true);
        setIsAuthenticated(true);
        return;
      }

      const { data } = await supabase.auth.getSession();
      if (cancelled) return;

      if (data.session) {
        setIsAuthenticated(true);
        setUserEmail(data.session.user?.email || null);
      } else {
        router.replace('/login?next=/account');
        return;
      }
      setAuthChecked(true);
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

  // Fetch quota and referral stats after auth check
  useEffect(() => {
    if (!authChecked || !isAuthenticated) return;
    fetchQuota();
    fetchReferralStats();
  }, [authChecked, isAuthenticated]);

  const fetchQuota = async () => {
    try {
      const data = await getQuota();
      setQuota(data);
      if (data?.plan) {
        setUserProperties({ plan: data.plan, is_paying_customer: data.plan !== 'free' });
      }
    } catch (err) {
      console.error('Failed to fetch quota:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchReferralStats = async () => {
    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) return;
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/referrals/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (response.ok) {
        const stats = await response.json();
        setReferralStats(stats);
      }
    } catch (err) {
      console.error('Failed to fetch referral stats:', err);
    }
  };

  const copyReferralLink = async () => {
    if (!referralStats?.referral_link) return;
    
    try {
      await navigator.clipboard.writeText(referralStats.referral_link);
      setLinkCopied(true);
      trackReferralLinkCopied();
      setTimeout(() => setLinkCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleUpgrade = useCallback(async (selectedPlan?: string) => {
    setUpgradeLoading(true);
    try {
      // Get auth token from Supabase
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      
      if (!token) {
        alert('Please log in to upgrade');
        router.push('/login?next=/account');
        return;
      }
      
      // Get checkout URL from backend
      const planQuery = selectedPlan ? `?plan=${encodeURIComponent(selectedPlan)}` : '';
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/paddle/checkout-url${planQuery}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      
      if (response.ok) {
        const data = await response.json();
        // Redirect to Paddle checkout
        window.location.href = data.checkout_url;
      } else {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        alert(error.detail || 'Failed to get checkout URL');
      }
    } catch (err) {
      alert('Failed to start checkout');
    } finally {
      setUpgradeLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!authChecked || !isAuthenticated) return;
    if (!planParam || autoCheckoutStarted) return;
    if (planKey !== 'free') return;
    setAutoCheckoutStarted(true);
    handleUpgrade(planParam);
  }, [authChecked, isAuthenticated, planParam, planKey, autoCheckoutStarted, handleUpgrade]);

  // Show loading while checking auth
  if (!authChecked) {
    return (
      <>
        <Header />
        <main className="flex-1">
          <div className="container mx-auto max-w-5xl px-4 py-12">
            <div className="flex flex-col items-center justify-center space-y-4">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-muted-foreground">Checking authentication...</p>
            </div>
          </div>
        </main>
        <Footer />
      </>
    );
  }

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
            {userEmail && (
              <p className="text-sm text-muted-foreground mt-1">
                Signed in as <span className="font-medium text-foreground">{userEmail}</span>
              </p>
            )}
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
                      <span className="text-2xl font-bold">{planLabel}</span>
                      {isPaidPlan && (
                        <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-500">
                          {quota?.subscription_status === 'active' ? 'Active' : quota?.subscription_status || 'Active'}
                        </span>
                      )}
                    </div>
                    {planKey === 'free' ? (
                      <p className="text-sm text-muted-foreground">
                        Upgrade to a paid plan for more apply packs and higher limits.
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Your subscription is active. Manage it in Paddle customer portal.
                      </p>
                    )}
                    {isPaidPlan && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Unused credits roll over while your subscription is active.
                      </p>
                    )}
                  </div>
                  {planKey === 'free' ? (
                    <button
                      onClick={() => handleUpgrade(planParam)}
                      disabled={upgradeLoading}
                      className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                    >
                      {upgradeLoading ? 'Loading...' : 'Upgrade'}
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
                  {/* Credits */}
                  {planKey !== 'free' && quota?.credits_enabled && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Credits</span>
                        <span className="text-sm text-muted-foreground">
                          {quota?.credits_balance} ({quota?.packs_equivalent || 0} packs)
                        </span>
                      </div>
                      {quota?.credits_expires_soon && (
                        <p className="text-xs text-amber-600 mt-1">
                          Some credits expire soon.
                        </p>
                      )}
                    </div>
                  )}
                  {/* Apply Packs */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Apply Packs</span>
                      <span className="text-sm text-muted-foreground">
                        {quota?.credits_enabled
                          ? `Available ${quota?.packs_equivalent || 0}`
                          : `${quota?.apply_packs.used || 0} / ${quota?.apply_packs.limit === null ? 'Unlimited' : quota?.apply_packs.limit || 0}`}
                      </span>
                    </div>
                    {!quota?.credits_enabled && quota?.apply_packs.limit !== null && (
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

                  {/* Tracked Applications */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Active Tracked Applications</span>
                      <span className="text-sm text-muted-foreground">
                        {quota?.tracking?.limit === null ? 'Unlimited' : `${quota?.tracking?.used || 0} / ${quota?.tracking?.limit || 0}`}
                      </span>
                    </div>
                    {quota?.tracking?.limit !== null && (
                      <div className="w-full bg-muted rounded-full h-2">
                        <div
                          className="bg-primary h-2 rounded-full transition-all"
                          style={{
                            width: `${Math.min(100, ((quota?.tracking?.used || 0) / (quota?.tracking?.limit || 1)) * 100)}%`,
                          }}
                        />
                      </div>
                    )}
                    {quota?.tracking && !quota.tracking.allowed && (
                      <p className="text-xs text-red-500 mt-1">
                        Tracking limit reached. Upgrade to increase your tracking limit.
                      </p>
                    )}
                  </div>

                  {/* DOCX Export */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">DOCX Exports</span>
                      <span className="text-sm text-muted-foreground">
                        {quota?.docx_export?.limit === null
                          ? 'Unlimited'
                          : `${quota?.docx_export?.used || 0} / ${quota?.docx_export?.limit || 0}`}
                      </span>
                    </div>
                    {quota?.docx_export?.limit !== null && (
                      <div className="w-full bg-muted rounded-full h-2">
                        <div
                          className="bg-primary h-2 rounded-full transition-all"
                          style={{
                            width: `${Math.min(100, ((quota?.docx_export?.used || 0) / (quota?.docx_export?.limit || 1)) * 100)}%`,
                          }}
                        />
                      </div>
                    )}
                    {quota?.docx_export && !quota.docx_export.allowed && (
                      <p className="text-xs text-red-500 mt-1">
                        DOCX export limit reached. Upgrade for more.
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Referral Program */}
              <div className="rounded-xl border border-primary/30 bg-primary/5 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Gift className="h-5 w-5 text-primary" />
                  <h2 className="text-lg font-semibold">Referral Program</h2>
                </div>
                
                <p className="text-sm text-muted-foreground mb-4">
                  Refer a friend and earn <strong>5 Apply Packs</strong> when they become a paid user.
                </p>
                
                {referralStats ? (
                  <div className="space-y-4">
                    <div>
                      <label className="text-xs text-muted-foreground uppercase tracking-wider">Your referral link</label>
                      <div className="mt-1 flex items-center gap-2">
                        <input
                          type="text"
                          readOnly
                          value={referralStats.referral_link}
                          className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm"
                        />
                        <button
                          onClick={copyReferralLink}
                          className="rounded-lg border border-border bg-background px-3 py-2 text-sm hover:bg-muted flex items-center gap-2"
                        >
                          {linkCopied ? (
                            <>
                              <CheckCircle2 className="h-4 w-4 text-green-500" />
                              Copied!
                            </>
                          ) : (
                            <>
                              <Copy className="h-4 w-4" />
                              Copy
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-4 pt-2">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-primary">{referralStats.completed_referrals}</div>
                        <div className="text-xs text-muted-foreground">Completed</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold">{referralStats.pending_referrals}</div>
                        <div className="text-xs text-muted-foreground">Pending</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-green-500">{referralStats.total_packs_earned}</div>
                        <div className="text-xs text-muted-foreground">Packs Earned</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">Loading referral info...</div>
                )}
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
                        <span>Application tracker</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>DOCX export</span>
                      </li>
                    </ul>
                  </div>
                  <div>
                    <h3 className="font-medium mb-2">Paid Plans</h3>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Standard: $4/week (20 packs) or $19/month (120 packs)</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Pro: $9/week (50 packs) or $39/month (250 packs)</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Trust Reports</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>DOCX export</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Tracking limit matches your Apply Pack limit</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Higher Premium AI limits on Pro</span>
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
