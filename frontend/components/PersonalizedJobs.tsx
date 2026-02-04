'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';
import type { JobListResponse, SearchParams } from '@/lib/api';
import { JobCard } from '@/components/JobCard';
import { Pagination } from '@/components/Pagination';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function buildQuery(params: SearchParams): string {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.location) sp.set('location', params.location);
  if (params.remote) sp.set('remote', params.remote);
  if (params.employment) sp.set('employment', params.employment);
  if (params.source) sp.set('source', params.source);
  if (params.posted_since) sp.set('posted_since', String(params.posted_since));
  if (params.min_score !== undefined) sp.set('min_score', String(params.min_score));
  if (params.sort) sp.set('sort', params.sort);
  if (params.page) sp.set('page', String(params.page));
  if (params.page_size) sp.set('page_size', String(params.page_size));
  return sp.toString();
}

export function PersonalizedJobs({ params }: { params: SearchParams }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<JobListResponse>({ jobs: [], total: 0, page: 1, page_size: 20, has_more: false });

  const query = useMemo(() => buildQuery(params), [params]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);

      try {
        const { data: sess } = await supabase.auth.getSession();
        const token = sess.session?.access_token;
        if (!token) {
          throw new Error('LOGIN_REQUIRED');
        }

        const res = await fetch(`${API_URL}/jobs?${query}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          cache: 'no-store',
        });

        if (res.status === 401) throw new Error('LOGIN_REQUIRED');
        if (!res.ok) {
          const t = await res.text().catch(() => '');
          throw new Error(t || 'Failed to fetch personalized jobs');
        }

        const json = (await res.json()) as JobListResponse;
        if (!cancelled) setData(json);
      } catch (err: any) {
        if (cancelled) return;
        if (err?.message === 'LOGIN_REQUIRED') {
          setError('Login to see personalized ranking.');
        } else {
          setError(err?.message || 'Failed to fetch personalized jobs');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [query]);

  if (loading) {
    return <div className="h-40 rounded-xl bg-muted animate-pulse" />;
  }

  if (error) {
    return (
      <div className="rounded-xl border border-border bg-card p-6">
        <p className="text-sm text-muted-foreground">{error}</p>
        <Link
          href={`/login?next=${encodeURIComponent(`/?${query}`)}`}
          className="mt-4 inline-flex rounded-lg bg-foreground px-3 py-2 text-sm font-medium text-background"
        >
          Login
        </Link>
        <p className="mt-3 text-xs text-muted-foreground">
          Then create a profile and set a primary resume to improve personalization.
        </p>
      </div>
    );
  }

  const totalPages = Math.ceil(data.total / data.page_size);

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{data.total.toLocaleString()} jobs found</p>
      </div>

      {data.jobs.length > 0 ? (
        <>
          <div className="space-y-4">
            {data.jobs.map((job, index) => (
              <div key={job.job_id} className="animate-fade-in" style={{ animationDelay: `${index * 50}ms` }}>
                <JobCard job={job} />
              </div>
            ))}
          </div>

          <div className="mt-8">
            <Pagination currentPage={data.page} totalPages={totalPages} hasMore={data.has_more} />
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16 text-center">
          <h3 className="font-semibold">No jobs found</h3>
          <p className="mt-1 text-sm text-muted-foreground max-w-sm">
            Try adjusting your filters or search terms.
          </p>
        </div>
      )}
    </>
  );
}

