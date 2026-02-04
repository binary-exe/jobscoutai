'use client';

import { useEffect } from 'react';
import { trackEvent } from '@/lib/analytics';

interface BrowseSectionTrackerProps {
  section: string;
  segment?: string; // e.g. role slug or country slug
}

/**
 * Fires a single browse_section_viewed event when the section is viewed.
 */
export function BrowseSectionTracker({ section, segment }: BrowseSectionTrackerProps) {
  useEffect(() => {
    trackEvent('browse_section_viewed', { section, ...(segment ? { segment } : {}) });
  }, [section, segment]);
  return null;
}
