'use client';

import Link from 'next/link';
import { MapPin, Clock, Star, AlertTriangle, Building2, ExternalLink } from 'lucide-react';
import { Job, formatRelativeTime, formatSalary } from '@/lib/api';
import { cn } from '@/lib/utils';

interface JobCardProps {
  job: Job;
  /** Pass from server (e.g. new Date().toISOString()) so server/client match and avoid hydration errors */
  nowIso?: string;
  className?: string;
}

const REMOTE_STYLES = {
  remote: 'bg-remote-light text-remote',
  hybrid: 'bg-hybrid-light text-hybrid',
  onsite: 'bg-onsite-light text-onsite',
  unknown: 'bg-muted text-muted-foreground',
};

export function JobCard({ job, nowIso, className }: JobCardProps) {
  const salary = formatSalary(job.salary_min, job.salary_max, job.salary_currency);
  const hasFlags = job.ai_flags && job.ai_flags.length > 0;
  
  return (
    <Link
      href={`/job/${job.job_id}`}
      className={cn(
        "group block rounded-xl border border-border bg-background p-5",
        "transition-all duration-200",
        "hover:border-foreground/20 hover:shadow-lg hover:shadow-foreground/5",
        "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-foreground truncate group-hover:text-foreground/80 transition-colors">
            {job.title}
          </h3>
          <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <Building2 className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{job.company}</span>
          </div>
        </div>
        
        {/* AI Score */}
        {job.ai_score !== undefined && job.ai_score !== null && (
          <div className={cn(
            "flex items-center gap-1 rounded-lg px-2 py-1",
            job.ai_score >= 70 ? "bg-remote-light text-remote" :
            job.ai_score >= 40 ? "bg-hybrid-light text-hybrid" :
            "bg-muted text-muted-foreground"
          )}>
            <Star className="h-3.5 w-3.5" />
            <span className="text-sm font-medium">{Math.round(job.ai_score)}</span>
          </div>
        )}
      </div>
      
      {/* Tags row */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {/* Remote badge */}
        <span className={cn(
          "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
          REMOTE_STYLES[job.remote_type] || REMOTE_STYLES.unknown
        )}>
          {job.remote_type === 'unknown' ? 'TBD' : job.remote_type}
        </span>
        
        {/* Location */}
        {job.location_raw && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3" />
            <span className="truncate max-w-[120px]">{job.location_raw}</span>
          </span>
        )}
        
        {/* Employment type */}
        {job.employment_types && job.employment_types.length > 0 && job.employment_types[0] !== 'unknown' && (
          <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {job.employment_types[0].replace('_', '-')}
          </span>
        )}
        
        {/* Salary */}
        {salary && (
          <span className="text-xs font-medium text-foreground">
            {salary}
          </span>
        )}
        
        {/* Warning flags */}
        {hasFlags && (
          <span className="inline-flex items-center gap-1 text-xs text-hybrid">
            <AlertTriangle className="h-3 w-3" />
          </span>
        )}
      </div>
      
      {/* AI Summary */}
      {job.ai_summary && (
        <p className="mt-3 text-sm text-muted-foreground line-clamp-2">
          {job.ai_summary}
        </p>
      )}
      
      {/* Footer */}
      <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          <span suppressHydrationWarning>{formatRelativeTime(job.posted_at || job.first_seen_at, nowIso)}</span>
        </div>
        
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <span>View details</span>
          <ExternalLink className="h-3 w-3" />
        </div>
      </div>
    </Link>
  );
}

export function JobCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-background p-5 animate-pulse">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-2">
          <div className="h-5 w-3/4 rounded bg-muted" />
          <div className="h-4 w-1/2 rounded bg-muted" />
        </div>
        <div className="h-7 w-12 rounded-lg bg-muted" />
      </div>
      <div className="mt-3 flex gap-2">
        <div className="h-5 w-16 rounded-md bg-muted" />
        <div className="h-5 w-24 rounded-md bg-muted" />
      </div>
      <div className="mt-3 space-y-2">
        <div className="h-4 w-full rounded bg-muted" />
        <div className="h-4 w-2/3 rounded bg-muted" />
      </div>
      <div className="mt-4 flex justify-between">
        <div className="h-3 w-16 rounded bg-muted" />
      </div>
    </div>
  );
}
