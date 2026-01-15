'use client';

import Link from 'next/link';
import { Search } from 'lucide-react';

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-14 max-w-5xl items-center px-4">
        <Link href="/" className="flex items-center space-x-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground">
            <Search className="h-4 w-4 text-background" />
          </div>
          <span className="font-semibold tracking-tight">JobScout</span>
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
          <Link 
            href="/account"
            className="px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Account
          </Link>
          <a 
            href="https://github.com/binary-exe/jobscoutai"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}
