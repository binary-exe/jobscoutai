'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useTransition } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  hasMore: boolean;
  className?: string;
}

export function Pagination({ currentPage, totalPages, hasMore, className }: PaginationProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  
  const goToPage = useCallback((page: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('page', page.toString());
    
    startTransition(() => {
      router.push(`/?${params.toString()}`);
    });
  }, [router, searchParams]);
  
  if (totalPages <= 1) return null;
  
  return (
    <div className={cn("flex items-center justify-center gap-2", className, isPending && "opacity-70")}>
      <button
        onClick={() => goToPage(currentPage - 1)}
        disabled={currentPage <= 1}
        className={cn(
          "flex items-center gap-1 rounded-lg px-3 py-2 text-sm transition-colors",
          currentPage <= 1
            ? "text-muted-foreground cursor-not-allowed"
            : "text-foreground hover:bg-muted"
        )}
      >
        <ChevronLeft className="h-4 w-4" />
        Previous
      </button>
      
      <div className="flex items-center gap-1">
        {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
          let pageNum: number;
          if (totalPages <= 5) {
            pageNum = i + 1;
          } else if (currentPage <= 3) {
            pageNum = i + 1;
          } else if (currentPage >= totalPages - 2) {
            pageNum = totalPages - 4 + i;
          } else {
            pageNum = currentPage - 2 + i;
          }
          
          return (
            <button
              key={pageNum}
              onClick={() => goToPage(pageNum)}
              className={cn(
                "h-8 w-8 rounded-lg text-sm transition-colors",
                pageNum === currentPage
                  ? "bg-foreground text-background font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              {pageNum}
            </button>
          );
        })}
      </div>
      
      <button
        onClick={() => goToPage(currentPage + 1)}
        disabled={!hasMore}
        className={cn(
          "flex items-center gap-1 rounded-lg px-3 py-2 text-sm transition-colors",
          !hasMore
            ? "text-muted-foreground cursor-not-allowed"
            : "text-foreground hover:bg-muted"
        )}
      >
        Next
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}
