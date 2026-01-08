import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { JobCardSkeleton } from '@/components/JobCard';

export default function Loading() {
  return (
    <>
      <Header />
      
      <main className="flex-1">
        {/* Hero skeleton */}
        <section className="border-b border-border/40 bg-gradient-to-b from-muted/30 to-background py-12 sm:py-16">
          <div className="container mx-auto max-w-5xl px-4">
            <div className="mx-auto max-w-2xl text-center">
              <div className="h-6 w-40 mx-auto rounded-full bg-muted animate-pulse" />
              <div className="mt-4 h-10 w-3/4 mx-auto rounded bg-muted animate-pulse" />
              <div className="mt-3 h-5 w-2/3 mx-auto rounded bg-muted animate-pulse" />
              <div className="mt-8 h-12 rounded-xl bg-muted animate-pulse" />
            </div>
            
            <div className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-20 rounded-xl bg-muted animate-pulse" />
              ))}
            </div>
          </div>
        </section>
        
        {/* Jobs skeleton */}
        <section className="py-8">
          <div className="container mx-auto max-w-5xl px-4">
            <div className="flex flex-col gap-6 lg:flex-row">
              <aside className="lg:w-64 shrink-0">
                <div className="h-64 rounded-xl bg-muted animate-pulse" />
              </aside>
              
              <div className="flex-1 space-y-4">
                {[...Array(5)].map((_, i) => (
                  <JobCardSkeleton key={i} />
                ))}
              </div>
            </div>
          </div>
        </section>
      </main>
      
      <Footer />
    </>
  );
}
