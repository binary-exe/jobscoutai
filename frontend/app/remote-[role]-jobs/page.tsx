import { Metadata } from 'next';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { BrowseSectionTracker } from '@/components/BrowseSectionTracker';
import { ArrowRight, MapPin, Building2, Clock } from 'lucide-react';
import { getJobs, formatRelativeTime, formatSalary, Job } from '@/lib/api';

// Avoid build-time static generation: these pages fetch from API and timeout on Vercel
export const dynamic = 'force-dynamic';

interface PageProps {
  params: {
    role: string;
  };
}

// Common role mappings for better SEO
const ROLE_MAPPINGS: Record<string, { title: string; keywords: string[] }> = {
  'python-developer': { title: 'Python Developer', keywords: ['python', 'django', 'flask', 'fastapi'] },
  'javascript-developer': { title: 'JavaScript Developer', keywords: ['javascript', 'js', 'node', 'react', 'vue'] },
  'react-developer': { title: 'React Developer', keywords: ['react', 'reactjs', 'frontend'] },
  'nodejs-developer': { title: 'Node.js Developer', keywords: ['node', 'nodejs', 'express', 'backend'] },
  'software-engineer': { title: 'Software Engineer', keywords: ['software', 'engineer', 'developer'] },
  'frontend-developer': { title: 'Frontend Developer', keywords: ['frontend', 'front-end', 'ui', 'react', 'vue'] },
  'backend-developer': { title: 'Backend Developer', keywords: ['backend', 'back-end', 'api', 'server'] },
  'fullstack-developer': { title: 'Full Stack Developer', keywords: ['fullstack', 'full-stack', 'full stack'] },
  'devops-engineer': { title: 'DevOps Engineer', keywords: ['devops', 'aws', 'kubernetes', 'docker'] },
  'data-scientist': { title: 'Data Scientist', keywords: ['data', 'scientist', 'ml', 'machine learning'] },
  'machine-learning-engineer': { title: 'Machine Learning Engineer', keywords: ['ml', 'machine learning', 'ai', 'deep learning'] },
  'product-manager': { title: 'Product Manager', keywords: ['product', 'manager', 'pm'] },
  'ux-designer': { title: 'UX Designer', keywords: ['ux', 'designer', 'user experience', 'ui/ux'] },
  'qa-engineer': { title: 'QA Engineer', keywords: ['qa', 'quality', 'testing', 'test'] },
  'security-engineer': { title: 'Security Engineer', keywords: ['security', 'cybersecurity', 'infosec'] },
};

function formatRoleTitle(role: string | undefined): string {
  if (!role) return 'Developer';
  
  const mapping = ROLE_MAPPINGS[role];
  if (mapping) return mapping.title;
  
  // Convert kebab-case to Title Case
  return role
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const roleTitle = formatRoleTitle(params?.role);
  const title = `Remote ${roleTitle} Jobs | JobScoutAI`;
  const description = `Find the best remote ${roleTitle.toLowerCase()} jobs. Browse curated remote positions with AI-powered matching, trust reports, and personalized apply packs.`;
  
  return {
    title,
    description,
    keywords: [
      `remote ${roleTitle.toLowerCase()} jobs`,
      `${roleTitle.toLowerCase()} remote positions`,
      `work from home ${roleTitle.toLowerCase()}`,
      'remote work',
      'JobScout',
    ],
    openGraph: {
      title,
      description,
      type: 'website',
    },
  };
}

export default async function RemoteRoleJobsPage({ params }: PageProps) {
  const role = params?.role || 'software-engineer';
  const roleTitle = formatRoleTitle(role);
  const mapping = ROLE_MAPPINGS[role];
  
  // Build search query from role keywords
  const searchQuery = mapping?.keywords?.join(' OR ') || role.replace(/-/g, ' ');
  
  // Fetch relevant jobs
  let jobs: Job[] = [];
  try {
    const response = await getJobs({ 
      q: searchQuery, 
      remote: 'remote',
      page_size: 20 
    });
    jobs = response.jobs;
  } catch {
    // Fallback to empty on error
  }

  const nowIso = new Date().toISOString();
  
  return (
    <>
      <BrowseSectionTracker section="remote-by-role" segment={role} />
      <Header />
      
      <main className="flex-1 py-8">
        <div className="container mx-auto max-w-5xl px-4">
          {/* SEO Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl mb-3">
              Remote {roleTitle} Jobs
            </h1>
            <p className="text-muted-foreground max-w-2xl">
              Find the best remote {roleTitle.toLowerCase()} positions. 
              All jobs are curated and include AI-powered trust reports to help you avoid scams and ghost jobs.
            </p>
          </div>
          
          {/* Job Listings */}
          {jobs.length > 0 ? (
            <div className="space-y-4">
              {jobs.map((job) => (
                <Link
                  key={job.job_id}
                  href={`/job/${job.job_id}`}
                  className="block rounded-xl border border-border bg-card p-4 hover:border-primary/50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <h2 className="font-semibold text-foreground truncate">{job.title}</h2>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Building2 className="h-3.5 w-3.5" />
                          {job.company}
                        </span>
                        {job.location_raw && (
                          <span className="flex items-center gap-1">
                            <MapPin className="h-3.5 w-3.5" />
                            {job.location_raw}
                          </span>
                        )}
                        <span className="flex items-center gap-1" suppressHydrationWarning>
                          <Clock className="h-3.5 w-3.5" />
                          {formatRelativeTime(job.posted_at || job.first_seen_at, nowIso)}
                        </span>
                      </div>
                      {(job.salary_min || job.salary_max) && (
                        <p className="mt-2 text-sm font-medium text-primary">
                          {formatSalary(job.salary_min, job.salary_max, job.salary_currency)}
                        </p>
                      )}
                    </div>
                    <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 rounded-xl border border-border bg-card">
              <p className="text-muted-foreground">
                No remote {roleTitle.toLowerCase()} jobs found at the moment.
              </p>
              <Link
                href="/"
                className="mt-4 inline-flex items-center gap-2 text-primary hover:underline"
              >
                Browse all jobs
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          )}
          
          {/* SEO Content */}
          <div className="mt-12 prose prose-sm max-w-none text-muted-foreground">
            <h2 className="text-foreground">About Remote {roleTitle} Jobs</h2>
            <p>
              Remote {roleTitle.toLowerCase()} positions offer the flexibility to work from anywhere 
              while building amazing products and solutions. Whether you&apos;re looking for your first 
              remote role or transitioning from an office job, JobScoutAI helps you find legitimate 
              opportunities with our AI-powered trust reports.
            </p>
            <p>
              Each job listing is analyzed for potential scam indicators and ghost job signals, 
              helping you focus on real opportunities that are actively hiring.
            </p>
          </div>
          
          {/* Related Categories */}
          <div className="mt-8 pt-8 border-t border-border">
            <h3 className="font-semibold mb-4">Related Job Categories</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(ROLE_MAPPINGS)
                .filter(([key]) => key !== role)
                .slice(0, 6)
                .map(([key, value]) => (
                  <Link
                    key={key}
                    href={`/remote-${key}-jobs`}
                    className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
                  >
                    Remote {value.title} Jobs
                  </Link>
                ))}
            </div>
          </div>
        </div>
      </main>
      
      <Footer />
    </>
  );
}
