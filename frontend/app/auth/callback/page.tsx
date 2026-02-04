'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { supabase } from '@/lib/supabase';

export default function AuthCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const code = searchParams.get('code');
        const nextUrl = searchParams.get('next') || '/profile';
        const referralCode = searchParams.get('ref');

        if (code) {
          const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
          if (exchangeError) throw exchangeError;
        } else {
          // Some flows don't use the code param; still try to load session
          const { data } = await supabase.auth.getSession();
          if (!data.session) {
            throw new Error('No session found. Please try logging in again.');
          }
        }

        // Apply referral code if present
        if (referralCode) {
          try {
            const { data: sessionData } = await supabase.auth.getSession();
            const token = sessionData.session?.access_token;
            if (token) {
              await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/referrals/apply`, {
                method: 'POST',
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({ referral_code: referralCode }),
              });
              // Don't fail the login if referral apply fails
            }
          } catch {
            // Ignore referral errors
          }
        }

        if (!cancelled) router.replace(nextUrl);
      } catch (err: unknown) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Login failed');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [router, searchParams]);

  return (
    <>
      <Header />
      <main className="flex-1">
        <section className="py-12">
          <div className="container mx-auto max-w-md px-4">
            <h1 className="text-2xl font-semibold tracking-tight">Signing you in…</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Please wait a moment.
            </p>
            {error ? (
              <div className="mt-6 rounded-xl border border-border bg-card p-5">
                <p className="text-sm text-red-600">{error}</p>
                <button
                  onClick={() => router.replace('/login')}
                  className="mt-4 rounded-lg bg-foreground px-3 py-2 text-sm font-medium text-background"
                >
                  Back to login
                </button>
              </div>
            ) : null}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}

