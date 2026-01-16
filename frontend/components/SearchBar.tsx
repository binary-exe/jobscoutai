'use client';

import { Search, X } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useCallback, useTransition } from 'react';
import { cn } from '@/lib/utils';

interface SearchBarProps {
  className?: string;
}

export function SearchBar({ className }: SearchBarProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  
  const [query, setQuery] = useState(searchParams.get('q') || '');
  
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    
    const params = new URLSearchParams(searchParams.toString());
    
    if (query) {
      params.set('q', query);
    } else {
      params.delete('q');
    }

    params.set('page', '1');
    
    startTransition(() => {
      router.push(`/?${params.toString()}`);
    });

  }, [query, router, searchParams]);
  
  const handleClear = useCallback(() => {
    setQuery('');
    const params = new URLSearchParams(searchParams.toString());
    params.delete('q');
    params.set('page', '1');
    
    startTransition(() => {
      router.push(`/?${params.toString()}`);
    });

  }, [router, searchParams]);
  
  return (
    <form onSubmit={handleSubmit} className={cn('relative', className)}>
      <div className="relative">
        <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search jobs, companies, skills..."
          className={cn(
            "h-12 w-full rounded-xl border border-border bg-background pl-12 pr-12 text-base",
            "placeholder:text-muted-foreground",
            "focus:border-foreground/20 focus:outline-none focus:ring-2 focus:ring-foreground/5",
            "transition-all duration-200",
            isPending && "opacity-70"
          )}
        />
        <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-2">
          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"
              aria-label="Clear"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </form>
  );
}
