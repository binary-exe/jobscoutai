'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useTransition } from 'react';
import { cn } from '@/lib/utils';

const REMOTE_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'remote', label: 'Remote' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'onsite', label: 'On-site' },
];

const EMPLOYMENT_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'full_time', label: 'Full-time' },
  { value: 'contract', label: 'Contract' },
  { value: 'freelance', label: 'Freelance' },
  { value: 'part_time', label: 'Part-time' },
];

const TIME_OPTIONS = [
  { value: '', label: 'Any time' },
  { value: '1', label: 'Last 24h' },
  { value: '7', label: 'Last week' },
  { value: '30', label: 'Last month' },
];

const SORT_OPTIONS = [
  { value: 'personalized', label: 'Personalized' },
  { value: 'relevance_score', label: 'Best match' },
  { value: 'ai_score', label: 'AI match' },
  { value: 'posted_at', label: 'Most recent' },
  { value: 'first_seen_at', label: 'Newest' },
];

interface FilterButtonProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

function FilterButton({ active, onClick, children }: FilterButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-1.5 text-sm rounded-lg transition-all duration-150",
        active
          ? "bg-foreground text-background font-medium"
          : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}

interface FiltersProps {
  className?: string;
}

export function Filters({ className }: FiltersProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  
  const currentRemote = searchParams.get('remote') || '';
  const currentEmployment = searchParams.get('employment') || '';
  const currentPostedSince = searchParams.get('posted_since') || '';
  const currentSort = searchParams.get('sort') || 'relevance_score';
  
  const updateFilter = useCallback((key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    params.set('page', '1');
    
    startTransition(() => {
      router.push(`/?${params.toString()}`);
    });
  }, [router, searchParams]);
  
  return (
    <div className={cn("space-y-4", className, isPending && "opacity-70")}>
      {/* Remote type */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Work type
        </label>
        <div className="flex flex-wrap gap-2">
          {REMOTE_OPTIONS.map((option) => (
            <FilterButton
              key={option.value}
              active={currentRemote === option.value}
              onClick={() => updateFilter('remote', option.value)}
            >
              {option.label}
            </FilterButton>
          ))}
        </div>
      </div>
      
      {/* Employment type */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Employment
        </label>
        <div className="flex flex-wrap gap-2">
          {EMPLOYMENT_OPTIONS.map((option) => (
            <FilterButton
              key={option.value}
              active={currentEmployment === option.value}
              onClick={() => updateFilter('employment', option.value)}
            >
              {option.label}
            </FilterButton>
          ))}
        </div>
      </div>
      
      {/* Posted time */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Posted
        </label>
        <div className="flex flex-wrap gap-2">
          {TIME_OPTIONS.map((option) => (
            <FilterButton
              key={option.value}
              active={currentPostedSince === option.value}
              onClick={() => updateFilter('posted_since', option.value)}
            >
              {option.label}
            </FilterButton>
          ))}
        </div>
      </div>
      
      {/* Sort */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Sort by
        </label>
        <div className="flex flex-wrap gap-2">
          {SORT_OPTIONS.map((option) => (
            <FilterButton
              key={option.value}
              active={currentSort === option.value}
              onClick={() => updateFilter('sort', option.value)}
            >
              {option.label}
            </FilterButton>
          ))}
        </div>
      </div>
    </div>
  );
}
