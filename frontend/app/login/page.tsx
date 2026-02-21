'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import { trackSignUp, trackReferralSignup } from '@/lib/analytics';

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nextUrl = useMemo(() => searchParams.get('next') || '/profile', [searchParams]);
  const referralCode = useMemo(() => searchParams.get('ref') || null, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { data } = await supabase.auth.getSession();
      if (!cancelled && data.session) router.replace(nextUrl);
    })();
    return () => {
      cancelled = true;
    };
  }, [router, nextUrl]);

  const handleSendMagicLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (!isSupabaseConfigured()) {
        setError('Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.');
        return;
      }

      // Persist redirect intent locally so the callback URL stays clean.
      // Supabase may append its own query params (code/error) and can mangle pre-existing queries.
      try {
        window.localStorage.setItem('jobiqueue_auth_next', nextUrl);
        if (referralCode) {
          window.localStorage.setItem('jobiqueue_auth_ref', referralCode);
        } else {
          window.localStorage.removeItem('jobiqueue_auth_ref');
        }
      } catch {
        // Best-effort; continue without stored state.
      }

      // Use NEXT_PUBLIC_SITE_URL if set, otherwise fall back to window.location.origin
      const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || window.location.origin;
      const redirectTo = `${siteUrl}/auth/callback`;

      const { error: supaErr } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: redirectTo,
        },
      });

      if (supaErr) throw supaErr;
      setSent(true);
      // Track sign-up attempt
      trackSignUp('email');
      if (referralCode) {
        trackReferralSignup(referralCode);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to send magic link';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Header />
      <main className="flex-1">
        <section className="py-12">
          <div className="container mx-auto max-w-md px-4">
            <h1 className="text-2xl font-semibold tracking-tight">Sign in to JobiQueue</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Access your Apply Workspace, track applications, and get personalized job recommendations.
            </p>

            <div className="mt-6 rounded-xl border border-border bg-card p-5">
              {sent ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-center w-12 h-12 mx-auto rounded-full bg-green-100">
                    <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <div className="text-center">
                    <p className="text-base font-medium">Check your email</p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      We sent a magic link to <span className="font-medium text-foreground">{email}</span>
                    </p>
                    <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                      <p className="text-xs text-amber-800">
                        <strong>Tip:</strong> If you don&apos;t see the email, check your spam or junk folder.
                      </p>
                    </div>
                    <p className="mt-3 text-xs text-muted-foreground">
                      The link expires in 1 hour. Click it to sign in instantly.
                    </p>
                  </div>
                  <button
                    onClick={() => setSent(false)}
                    className="w-full mt-4 text-sm text-primary hover:underline"
                    type="button"
                  >
                    Use a different email
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSendMagicLink} className="space-y-4">
                  <div>
                    <label htmlFor="email" className="block text-sm font-medium mb-1">
                      Email address
                    </label>
                    <input
                      id="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      type="email"
                      required
                      autoComplete="email"
                      placeholder="you@example.com"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  
                  {error && (
                    <p className="text-sm text-red-600">{error}</p>
                  )}
                  
                  <button
                    disabled={loading}
                    className="w-full rounded-lg bg-foreground px-3 py-2.5 text-sm font-medium text-background disabled:opacity-60"
                    type="submit"
                  >
                    {loading ? 'Sending…' : 'Continue with Email'}
                  </button>
                  
                  <p className="text-xs text-center text-muted-foreground">
                    We&apos;ll send you a magic link to sign in instantly. No password needed.
                  </p>
                </form>
              )}
            </div>

            <div className="mt-4 text-sm text-muted-foreground">
              <Link href="/" className="hover:text-foreground">
                Back to Browse Jobs
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
