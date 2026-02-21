'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Search, User, ChevronDown } from 'lucide-react';
import { useEffect, useState, useRef } from 'react';
import { supabase } from '@/lib/supabase';

export function Header() {
  const pathname = usePathname();
  const [email, setEmail] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loginUrl, setLoginUrl] = useState('/login');
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const { data } = await supabase.auth.getSession();
      if (!cancelled) setEmail(data.session?.user?.email || null);
    })();

    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!cancelled) setEmail(session?.user?.email || null);
    });

    return () => {
      cancelled = true;
      sub.subscription.unsubscribe();
    };
  }, []);

  // Build login URL with current path as redirect.
  // Do this in an effect so SSR + first client render match (prevents hydration #418/#422).
  useEffect(() => {
    const url =
      pathname && pathname !== '/login' && pathname !== '/auth/callback'
        ? `/login?next=${encodeURIComponent(pathname)}`
        : '/login';
    setLoginUrl(url);
  }, [pathname]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    setShowDropdown(false);
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-14 max-w-5xl items-center px-4">
        <Link href="/" className="flex items-center space-x-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground">
            <Search className="h-4 w-4 text-background" />
          </div>
          <span className="font-semibold tracking-tight">JobiQueue</span>
        </Link>
        
        <nav className="ml-auto flex items-center space-x-1">
          <Link 
            href="/apply"
            className="px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:text-foreground"
          >
            Apply Workspace
          </Link>
          <Link 
            href="/"
            className="px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Browse Jobs
          </Link>
          <Link 
            href="/pricing"
            className="px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Pricing
          </Link>
          
          {email ? (
            /* Logged in: Show user dropdown */
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setShowDropdown(!showDropdown)}
                className="flex items-center gap-1 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                type="button"
              >
                <User className="h-4 w-4" />
                <span className="hidden sm:inline max-w-[120px] truncate">{email.split('@')[0]}</span>
                <ChevronDown className="h-3 w-3" />
              </button>
              
              {showDropdown && (
                <div className="absolute right-0 mt-2 w-48 rounded-lg border border-border bg-background shadow-lg py-1 z-50">
                  <div className="px-3 py-2 border-b border-border">
                    <p className="text-xs text-muted-foreground">Signed in as</p>
                    <p className="text-sm font-medium truncate">{email}</p>
                  </div>
                  <Link
                    href="/profile"
                    onClick={() => setShowDropdown(false)}
                    className="block px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                  >
                    Profile & Resume
                  </Link>
                  <Link
                    href="/account"
                    onClick={() => setShowDropdown(false)}
                    className="block px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                  >
                    Account & Billing
                  </Link>
                  <Link
                    href="/apply/history"
                    onClick={() => setShowDropdown(false)}
                    className="block px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                  >
                    Application History
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-muted transition-colors"
                    type="button"
                  >
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* Logged out: Show Login button */
            <Link
              href={loginUrl}
              className="ml-2 px-4 py-1.5 text-sm font-medium bg-foreground text-background rounded-lg transition-colors hover:bg-foreground/90"
            >
              Sign In
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
