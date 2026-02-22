'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { supabase } from '@/lib/supabase';

function friendlyAuthError(code?: string | null, description?: string | null) {
  const c = (code || '').toLowerCase();
  const d = (description || '').trim();
  if (c === 'otp_expired') return 'This sign-in link has expired. Please request a new one.';
  if (c === 'access_denied') return d || 'Access denied. Please try logging in again.';
  return d || (c ? `Login failed (${c}). Please try again.` : 'Login failed. Please try again.');
}

function getStored(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function clearStored() {
  try {
    window.localStorage.removeItem('jobiqueue_auth_next');
    window.localStorage.removeItem('jobiqueue_auth_ref');
  } catch {
    // ignore
  }
}

export default function AuthCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const code = searchParams.get('code');

        // Supabase may append error params; handle them explicitly.
        const errorCode = searchParams.get('error_code') || searchParams.get('error');
        const errorDescription = searchParams.get('error_description');

        // Legacy: if Supabase appended "?error=..." in a way that ended up inside `next`,
        // surface it as a real error.
        const nextParam = searchParams.get('next');
        if (!errorCode && nextParam && nextParam.includes('?error=')) {
          try {
            const q = nextParam.split('?')[1] || '';
            const qp = new URLSearchParams(q);
            const nestedError = qp.get('error_code') || qp.get('error');
            const nestedDesc = qp.get('error_description');
            if (nestedError || nestedDesc) {
              throw new Error(friendlyAuthError(nestedError, nestedDesc));
            }
          } catch (e) {
            if (e instanceof Error) throw e;
          }
        }

        if (errorCode || errorDescription) {
          throw new Error(friendlyAuthError(errorCode, errorDescription));
        }

        const nextUrl = nextParam || getStored('jobiqueue_auth_next') || '/profile';
        const referralCode = searchParams.get('ref') || getStored('jobiqueue_auth_ref');

        if (code) {
          const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
          if (exchangeError) throw exchangeError;
        }

        // Some flows don't use the code param (or rely on URL hash parsing); ensure session exists.
        const { data } = await supabase.auth.getSession();
        if (!data.session) {
          throw new Error('We could not complete sign-in. Please try again.');
        }

        // Apply referral code if present
        if (referralCode) {
          try {
            const token = data.session?.access_token;
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

        clearStored();
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

