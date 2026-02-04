'use client';

import { useEffect } from 'react';
import { trackJobViewed } from '@/lib/analytics';

interface JobViewTrackerProps {
  jobId: string;
  jobTitle?: string;
  company?: string;
}

/**
 * Client component that tracks job detail view in PostHog.
 * Used on the server-rendered job detail page.
 */
export function JobViewTracker({ jobId, jobTitle, company }: JobViewTrackerProps) {
  useEffect(() => {
    trackJobViewed(jobId, jobTitle, company);
  }, [jobId, jobTitle, company]);
  return null;
}
