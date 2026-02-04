'use client';

import { useEffect, Suspense } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';
import { initAnalytics, identifyUser, resetUser, trackEvent } from '@/lib/analytics';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';

function AnalyticsTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Track page views on route change
  useEffect(() => {
    if (pathname) {
      const url = typeof window !== 'undefined' ? window.origin + pathname : pathname;
      const search = searchParams?.toString();
      trackEvent('$pageview', {
        $current_url: search ? `${url}?${search}` : url,
      });
    }
  }, [pathname, searchParams]);

  return null;
}

export function AnalyticsProvider({ children }: { children: React.ReactNode }) {
  // Initialize PostHog on mount
  useEffect(() => {
    initAnalytics();
  }, []);

  // Sync user identity with Supabase auth state
  useEffect(() => {
    if (!isSupabaseConfigured()) return;

    let cancelled = false;

    // Check initial session
    (async () => {
      const { data } = await supabase.auth.getSession();
      if (cancelled) return;
      
      if (data.session?.user) {
        identifyUser(data.session.user.id, {
          email: data.session.user.email,
        });
      }
    })();

    // Listen for auth changes
    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      if (cancelled) return;
      
      if (event === 'SIGNED_IN' && session?.user) {
        identifyUser(session.user.id, {
          email: session.user.email,
        });
      } else if (event === 'SIGNED_OUT') {
        resetUser();
      }
    });

    return () => {
      cancelled = true;
      sub.subscription.unsubscribe();
    };
  }, []);

  return (
    <>
      <Suspense fallback={null}>
        <AnalyticsTracker />
      </Suspense>
      {children}
    </>
  );
}
