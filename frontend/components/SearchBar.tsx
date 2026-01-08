'use client';

import { RefreshCw, Search, Sparkles, X } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState, useCallback, useTransition } from 'react';
import { cn } from '@/lib/utils';
import { getRun, triggerScrape } from '@/lib/api';

interface SearchBarProps {
  className?: string;
}

export function SearchBar({ className }: SearchBarProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [useAi, setUseAi] = useState(searchParams.get('ai') === '1');
  const [scrapeRunId, setScrapeRunId] = useState<number | null>(null);
  const [scrapeStatus, setScrapeStatus] = useState<'idle' | 'queued' | 'running' | 'done' | 'error'>('idle');
  const [scrapeMessage, setScrapeMessage] = useState<string>('');

  const locationForScrape = useMemo(() => searchParams.get('location') || undefined, [searchParams]);

  const startScrape = useCallback(async () => {
    const q = query.trim();
    if (q.length < 2) return;

    setScrapeStatus('queued');
    setScrapeMessage('Starting scrape…');

    try {
      const res = await triggerScrape({ query: q, location: locationForScrape, use_ai: useAi });
      setScrapeRunId(res.run_id);
      setScrapeStatus('running');
      setScrapeMessage('Scraping sources… this can take 1–2 minutes.');
    } catch (e) {
      setScrapeStatus('error');
      setScrapeMessage(e instanceof Error ? e.message : 'Failed to start scrape');
    }
  }, [query, locationForScrape, useAi]);
  
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    
    const params = new URLSearchParams(searchParams.toString());
    
    if (query) {
      params.set('q', query);
    } else {
      params.delete('q');
    }

    if (useAi) {
      params.set('ai', '1');
    } else {
      params.delete('ai');
    }
    params.set('page', '1');
    
    startTransition(() => {
      router.push(`/?${params.toString()}`);
    });

    // Trigger a fresh scrape in the background (in addition to showing cached results immediately)
    void startScrape();
  }, [query, router, searchParams]);
  
  const handleClear = useCallback(() => {
    setQuery('');
    const params = new URLSearchParams(searchParams.toString());
    params.delete('q');
    params.delete('ai');
    params.set('page', '1');
    
    startTransition(() => {
      router.push(`/?${params.toString()}`);
    });

    setScrapeRunId(null);
    setScrapeStatus('idle');
    setScrapeMessage('');
  }, [router, searchParams]);

  // Poll run status; when finished, refresh data.
  useEffect(() => {
    if (!scrapeRunId || scrapeStatus !== 'running') return;

    let cancelled = false;
    const interval = setInterval(async () => {
      try {
        const run = await getRun(scrapeRunId);
        if (cancelled) return;
        if (run.finished_at) {
          setScrapeStatus('done');
          setScrapeMessage(`Scrape finished. Added ${run.jobs_new} new jobs.`);
          startTransition(() => router.refresh());
          clearInterval(interval);
        }
      } catch {
        // Ignore transient errors while the server is waking up / deploying
      }
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [scrapeRunId, scrapeStatus, router, startTransition]);
  
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
            "h-12 w-full rounded-xl border border-border bg-background pl-12 pr-24 text-base",
            "placeholder:text-muted-foreground",
            "focus:border-foreground/20 focus:outline-none focus:ring-2 focus:ring-foreground/5",
            "transition-all duration-200",
            isPending && "opacity-70"
          )}
        />
        <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-2">
          <button
            type="button"
            onClick={() => void startScrape()}
            className={cn(
              "rounded-md p-1.5 text-muted-foreground hover:text-foreground",
              (scrapeStatus === 'queued' || scrapeStatus === 'running') && "opacity-60"
            )}
            aria-label="Refresh (scrape)"
            title="Refresh (scrape)"
          >
            <RefreshCw className={cn("h-4 w-4", scrapeStatus === 'running' && "animate-spin")} />
          </button>

          <button
            type="button"
            onClick={() => setUseAi((v) => !v)}
            className={cn(
              "rounded-md p-1.5",
              useAi ? "text-remote" : "text-muted-foreground hover:text-foreground"
            )}
            aria-label="Toggle AI"
            title="Toggle AI (optional)"
          >
            <Sparkles className="h-4 w-4" />
          </button>

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

      {(scrapeStatus === 'queued' || scrapeStatus === 'running' || scrapeStatus === 'done' || scrapeStatus === 'error') && (
        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          <span
            className={cn(
              "inline-flex h-1.5 w-1.5 rounded-full",
              scrapeStatus === 'running' && "bg-remote animate-pulse",
              scrapeStatus === 'queued' && "bg-muted-foreground",
              scrapeStatus === 'done' && "bg-hybrid",
              scrapeStatus === 'error' && "bg-red-500"
            )}
          />
          <span>{scrapeMessage || (scrapeStatus === 'running' ? 'Scraping…' : '')}</span>
        </div>
      )}
    </form>
  );
}
