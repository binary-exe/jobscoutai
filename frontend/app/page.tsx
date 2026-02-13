import { Suspense } from 'react';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { SearchBar } from '@/components/SearchBar';
import { Filters } from '@/components/Filters';
import { JobCard, JobCardSkeleton } from '@/components/JobCard';
import { Pagination } from '@/components/Pagination';
import { Stats } from '@/components/Stats';
import { PersonalizedJobs } from '@/components/PersonalizedJobs';
import { getJobs, getStats, type SearchParams } from '@/lib/api';
import { Sparkles, ArrowRight, FileText, Shield, Clock } from 'lucide-react';

interface PageProps {
  searchParams: {
    q?: string;
    location?: string;
    remote?: string;
    employment?: string;
    posted_since?: string;
    sort?: string;
    page?: string;
  };
}

export default async function HomePage({ searchParams }: PageProps) {
  const isPersonalized = searchParams.sort === 'personalized';

  const params: SearchParams = {
    q: searchParams.q,
    location: searchParams.location,
    remote: searchParams.remote,
    employment: searchParams.employment,
    posted_since: searchParams.posted_since ? parseInt(searchParams.posted_since) : undefined,
    sort: (searchParams.sort as SearchParams['sort']) || 'ai_score',
    page: searchParams.page ? parseInt(searchParams.page) : 1,
    page_size: 20,
  };

  // Fetch data in parallel
  const [jobsData, stats] = await Promise.all([
    isPersonalized
      ? Promise.resolve({ jobs: [], total: 0, page: params.page || 1, page_size: params.page_size || 20, has_more: false })
      : getJobs(params).catch(() => ({ jobs: [], total: 0, page: 1, page_size: 20, has_more: false })),
    getStats().catch(() => ({ total_jobs: 0, jobs_last_24h: 0, jobs_last_7d: 0, sources: {}, last_run_jobs_new: 0 })),
  ]);

  const totalPages = Math.ceil(jobsData.total / jobsData.page_size);
  const nowIso = new Date().toISOString();

  return (
    <>
      <Header />
      
      <main className="flex-1">
        {/* Hero Section */}
        <section className="border-b border-border/40 bg-gradient-to-b from-muted/30 to-background py-12 sm:py-16">
          <div className="container mx-auto max-w-5xl px-4">
            <div className="mx-auto max-w-2xl text-center">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-remote-light px-3 py-1 text-sm font-medium text-remote">
                <Sparkles className="h-3.5 w-3.5" />
                AI-powered job matching
              </div>
              
              <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
                Find your perfect remote job
              </h1>
              <p className="mt-3 text-muted-foreground">
                Thousands of remote opportunities from top companies, ranked by AI for your skills.
              </p>
              
              <div className="mt-8">
                <Suspense fallback={<div className="h-12 rounded-xl bg-muted animate-pulse" />}>
                  <SearchBar />
                </Suspense>
              </div>
            </div>
            
            {/* Stats */}
            <div className="mt-10">
              <Stats stats={stats} />
            </div>
          </div>
        </section>
        
        {/* Apply Workspace CTA - Activation Flow */}
        <section className="border-b border-border/40 py-8 bg-primary/5">
          <div className="container mx-auto max-w-5xl px-4">
            <div className="flex flex-col md:flex-row items-center justify-between gap-6 rounded-xl border border-primary/20 bg-background p-6">
              <div className="flex-1 text-center md:text-left">
                <h2 className="text-lg font-semibold">Get interview-ready in 2 minutes</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Paste a job link + your resume → Get tailored cover letter, ATS tips, and trust report
                </p>
                <div className="mt-3 flex flex-wrap items-center justify-center md:justify-start gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <FileText className="h-3.5 w-3.5" />
                    AI-tailored cover letter
                  </span>
                  <span className="flex items-center gap-1">
                    <Shield className="h-3.5 w-3.5" />
                    Trust Report included
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" />
                    Save 45+ mins
                  </span>
                </div>
              </div>
              <Link
                href="/apply"
                className="shrink-0 inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Try Apply Workspace Free
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </section>
        
        {/* Jobs Section */}
        <section className="py-8">
          <div className="container mx-auto max-w-5xl px-4">
            <div className="flex flex-col gap-6 lg:flex-row">
              {/* Filters Sidebar */}
              <aside className="lg:w-64 shrink-0">
                <div className="sticky top-20">
                  <Suspense fallback={<div className="h-64 rounded-xl bg-muted animate-pulse" />}>
                    <Filters />
                  </Suspense>
                </div>
              </aside>
              
              {/* Job List */}
              <div className="flex-1 min-w-0">
                {isPersonalized ? (
                  <PersonalizedJobs params={params} />
                ) : (
                  <>
                    <div className="mb-4 flex items-center justify-between">
                      <p className="text-sm text-muted-foreground">
                        {jobsData.total.toLocaleString()} jobs found
                      </p>
                    </div>
                    
                    {jobsData.jobs.length > 0 ? (
                      <>
                        <div className="space-y-4">
                          {jobsData.jobs.map((job, index) => (
                            <div
                              key={job.job_id}
                              className="animate-fade-in"
                              style={{ animationDelay: `${index * 50}ms` }}
                            >
                              <JobCard job={job} nowIso={nowIso} />
                            </div>
                          ))}
                        </div>
                        
                        <div className="mt-8">
                          <Pagination
                            currentPage={jobsData.page}
                            totalPages={totalPages}
                            hasMore={jobsData.has_more}
                          />
                        </div>
                      </>
                    ) : (
                      <EmptyState />
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        </section>
      </main>
      
      <Footer />
    </>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16 text-center">
      <div className="rounded-full bg-muted p-4">
        <Sparkles className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="mt-4 font-semibold">No jobs found</h3>
      <p className="mt-1 text-sm text-muted-foreground max-w-sm">
        Try adjusting your filters or search terms to find more opportunities.
      </p>
    </div>
  );
}
