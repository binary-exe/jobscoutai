/**
 * API client for JobScout backend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface Job {
  job_id: string;
  title: string;
  company: string;
  location_raw: string;
  country?: string;
  city?: string;
  remote_type: 'remote' | 'hybrid' | 'onsite' | 'unknown';
  employment_types: string[];
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  job_url: string;
  apply_url?: string;
  description_text?: string;
  company_website?: string;
  linkedin_url?: string;
  tags: string[];
  source: string;
  posted_at?: string;
  first_seen_at: string;
  last_seen_at: string;
  ai_score?: number;
  ai_reasons?: string;
  ai_seniority?: string;
  ai_summary?: string;
  ai_requirements?: string;
  ai_tech_stack?: string;
  ai_flags: string[];
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface JobDetail extends Job {
  emails: string[];
  ai_company_summary?: string;
}

export interface Stats {
  total_jobs: number;
  jobs_last_24h: number;
  jobs_last_7d: number;
  sources: Record<string, number>;
  last_run_at?: string;
  last_run_jobs_new: number;
}

export interface ScrapeResponse {
  status: 'queued' | 'error' | string;
  run_id: number;
  message?: string;
}

export interface RunStatus {
  run_id: number;
  started_at: string;
  finished_at?: string | null;
  jobs_collected: number;
  jobs_new: number;
  jobs_updated: number;
  jobs_filtered: number;
  errors: number;
  sources?: string | null;
  criteria?: Record<string, unknown> | null;
}

export interface SearchParams {
  q?: string;
  location?: string;
  remote?: string;
  employment?: string;
  source?: string;
  posted_since?: number;
  min_score?: number;
  sort?: 'ai_score' | 'posted_at' | 'first_seen_at';
  page?: number;
  page_size?: number;
}

/**
 * Fetch jobs with filters and pagination.
 */
export async function getJobs(params: SearchParams = {}): Promise<JobListResponse> {
  const searchParams = new URLSearchParams();
  
  if (params.q) searchParams.set('q', params.q);
  if (params.location) searchParams.set('location', params.location);
  if (params.remote) searchParams.set('remote', params.remote);
  if (params.employment) searchParams.set('employment', params.employment);
  if (params.source) searchParams.set('source', params.source);
  if (params.posted_since) searchParams.set('posted_since', params.posted_since.toString());
  if (params.min_score !== undefined) searchParams.set('min_score', params.min_score.toString());
  if (params.sort) searchParams.set('sort', params.sort);
  if (params.page) searchParams.set('page', params.page.toString());
  if (params.page_size) searchParams.set('page_size', params.page_size.toString());
  
  const url = `${API_URL}/jobs?${searchParams.toString()}`;
  const res = await fetch(url, { next: { revalidate: 60 } });
  
  if (!res.ok) {
    throw new Error('Failed to fetch jobs');
  }
  
  return res.json();
}

/**
 * Fetch single job by ID.
 */
export async function getJob(id: string): Promise<JobDetail> {
  const res = await fetch(`${API_URL}/jobs/${id}`, { next: { revalidate: 60 } });
  
  if (!res.ok) {
    throw new Error('Job not found');
  }
  
  return res.json();
}

/**
 * Fetch system stats.
 */
export async function getStats(): Promise<Stats> {
  const res = await fetch(`${API_URL}/admin/stats`, { next: { revalidate: 300 } });
  
  if (!res.ok) {
    throw new Error('Failed to fetch stats');
  }
  
  return res.json();
}

/**
 * Trigger an on-demand scrape (public endpoint).
 */
export async function triggerScrape(input: { query: string; location?: string; use_ai?: boolean }): Promise<ScrapeResponse> {
  const res = await fetch(`${API_URL}/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: input.query,
      location: input.location,
      use_ai: !!input.use_ai,
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || 'Failed to trigger scrape');
  }

  return res.json();
}

/**
 * Get run status by id.
 */
export async function getRun(runId: number): Promise<RunStatus> {
  const res = await fetch(`${API_URL}/runs/${runId}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch run status');
  return res.json();
}

/**
 * Format relative time.
 */
export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return date.toLocaleDateString();
}

/**
 * Format salary range.
 */
export function formatSalary(min?: number, max?: number, currency?: string): string | null {
  if (!min && !max) return null;
  
  const curr = currency || 'USD';
  const formatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: curr,
    maximumFractionDigits: 0,
  });
  
  if (min && max && min !== max) {
    return `${formatter.format(min)} - ${formatter.format(max)}`;
  }
  return formatter.format(min || max || 0);
}
