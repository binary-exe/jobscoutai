import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind classes with clsx.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Build URL with search params.
 */
export function buildUrl(base: string, params: Record<string, string | undefined>): string {
  const url = new URL(base, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
  
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      url.searchParams.set(key, value);
    }
  });
  
  return `${url.pathname}${url.search}`;
}
