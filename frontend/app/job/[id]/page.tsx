import { notFound } from 'next/navigation';
import Link from 'next/link';
import { 
  ArrowLeft, 
  ExternalLink, 
  MapPin, 
  Building2, 
  Clock, 
  Star, 
  Briefcase,
  Mail,
  Globe,
  Linkedin,
  AlertTriangle,
  CheckCircle,
  Sparkles,
} from 'lucide-react';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { FormattedDescription } from '@/components/FormattedDescription';
import { JobViewTracker } from '@/components/JobViewTracker';
import { getJob, formatRelativeTime, formatSalary, JobDetail } from '@/lib/api';
import { cn } from '@/lib/utils';

interface PageProps {
  params: {
    id: string;
  };
}

// Generate JobPosting structured data for Google Jobs
function generateJobPostingJsonLd(job: JobDetail) {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://jobiqueue.com';
  
  // Build the structured data object
  const jsonLd: Record<string, unknown> = {
    '@context': 'https://schema.org/',
    '@type': 'JobPosting',
    title: job.title,
    description: job.description_text || job.ai_summary || '',
    datePosted: job.posted_at || job.first_seen_at,
    hiringOrganization: {
      '@type': 'Organization',
      name: job.company,
      ...(job.company_website && { sameAs: job.company_website }),
    },
    jobLocation: {
      '@type': 'Place',
      address: {
        '@type': 'PostalAddress',
        ...(job.location_raw && { addressLocality: job.location_raw }),
        ...(job.country_iso && { addressCountry: job.country_iso }),
      },
    },
    // Required: employment type
    employmentType: job.employment_types?.map(t => t.toUpperCase().replace('-', '_')) || ['FULL_TIME'],
  };

  // Add remote/location type
  if (job.remote_type === 'remote') {
    jsonLd.jobLocationType = 'TELECOMMUTE';
  }

  // Add salary if available
  if (job.salary_min || job.salary_max) {
    jsonLd.baseSalary = {
      '@type': 'MonetaryAmount',
      currency: job.salary_currency || 'USD',
      value: {
        '@type': 'QuantitativeValue',
        ...(job.salary_min && { minValue: job.salary_min }),
        ...(job.salary_max && { maxValue: job.salary_max }),
        unitText: 'YEAR',
      },
    };
  }

  // Add valid through (30 days from posting if not specified)
  if (job.expires_at) {
    jsonLd.validThrough = job.expires_at;
  } else if (job.posted_at) {
    const expiresDate = new Date(job.posted_at);
    expiresDate.setDate(expiresDate.getDate() + 30);
    jsonLd.validThrough = expiresDate.toISOString();
  }

  // Add identifier
  jsonLd.identifier = {
    '@type': 'PropertyValue',
    name: 'JobiQueue',
    value: job.job_id,
  };

  // Add direct apply URL
  if (job.apply_url || job.job_url) {
    jsonLd.directApply = true;
  }

  return jsonLd;
}

export default async function JobPage({ params }: PageProps) {
  let job: JobDetail;
  try {
    job = await getJob(params.id);
  } catch {
    notFound();
  }

  // Stable "now" so server and client render the same relative time (avoids hydration #418/#422)
  const nowIso = new Date().toISOString();
  const salary = formatSalary(job.salary_min, job.salary_max, job.salary_currency);
  const jsonLd = generateJobPostingJsonLd(job);

  return (
    <>
      {/* JobPosting structured data for Google Jobs */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <JobViewTracker jobId={job.job_id} jobTitle={job.title} company={job.company} />
      <Header />
      
      <main className="flex-1 py-8">
        <div className="container mx-auto max-w-3xl px-4">
          {/* Back link */}
          <Link 
            href="/"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to jobs
          </Link>
          
          {/* Job Header */}
          <div className="rounded-xl border border-border bg-background p-6 sm:p-8">
            {/* AI Score badge */}
            {job.ai_score !== undefined && job.ai_score !== null && (
              <div className="mb-4 flex items-center gap-2">
                <div className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5",
                  job.ai_score >= 70 ? "bg-remote-light text-remote" :
                  job.ai_score >= 40 ? "bg-hybrid-light text-hybrid" :
                  "bg-muted text-muted-foreground"
                )}>
                  <Star className="h-4 w-4" />
                  <span className="font-semibold">{Math.round(job.ai_score)}</span>
                  <span className="text-sm">match score</span>
                </div>
              </div>
            )}
            
            <h1 className="text-2xl font-bold sm:text-3xl">{job.title}</h1>
            
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <Building2 className="h-4 w-4" />
                <span className="font-medium text-foreground">{job.company}</span>
              </div>
              
              {job.location_raw && (
                <div className="flex items-center gap-1.5">
                  <MapPin className="h-4 w-4" />
                  <span>{job.location_raw}</span>
                </div>
              )}
              
              <div className="flex items-center gap-1.5">
                <Clock className="h-4 w-4" />
                <span suppressHydrationWarning>{formatRelativeTime(job.posted_at || job.first_seen_at, nowIso)}</span>
              </div>
            </div>
            
            {/* Tags */}
            <div className="mt-4 flex flex-wrap gap-2">
              <span className={cn(
                "inline-flex items-center rounded-md px-2.5 py-1 text-sm font-medium",
                job.remote_type === 'remote' ? "bg-remote-light text-remote" :
                job.remote_type === 'hybrid' ? "bg-hybrid-light text-hybrid" :
                job.remote_type === 'onsite' ? "bg-onsite-light text-onsite" :
                "bg-muted text-muted-foreground"
              )}>
                {job.remote_type === 'unknown' ? 'TBD' : job.remote_type}
              </span>
              
              {job.employment_types?.map((type) => (
                <span key={type} className="inline-flex items-center rounded-md bg-muted px-2.5 py-1 text-sm">
                  {type.replace('_', '-')}
                </span>
              ))}
              
              {salary && (
                <span className="inline-flex items-center rounded-md bg-muted px-2.5 py-1 text-sm font-medium">
                  {salary}
                </span>
              )}
              
              {job.ai_seniority && job.ai_seniority !== 'unknown' && (
                <span className="inline-flex items-center rounded-md bg-muted px-2.5 py-1 text-sm">
                  {job.ai_seniority}
                </span>
              )}
            </div>
            
            {/* Flags */}
            {job.ai_flags && job.ai_flags.length > 0 && (
              <div className="mt-4 rounded-lg bg-hybrid-light/50 p-3 border border-hybrid/20">
                <div className="flex items-center gap-2 text-hybrid">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="text-sm font-medium">Heads up</span>
                </div>
                <ul className="mt-1 text-sm text-hybrid/80">
                  {job.ai_flags.map((flag) => (
                    <li key={flag}>• {flag.replace(/_/g, ' ')}</li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Apply Button */}
            <div className="mt-6 flex flex-wrap gap-3">
              <a
                href={job.apply_url || job.job_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg bg-foreground px-5 py-2.5 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
              >
                Apply Now
                <ExternalLink className="h-4 w-4" />
              </a>
              
              <Link
                href={`/apply?jobId=${job.job_id}`}
                className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-5 py-2.5 text-sm font-medium transition-colors hover:bg-muted"
              >
                Open in Apply Workspace
                <Sparkles className="h-4 w-4" />
              </Link>
              
              {job.job_url && job.job_url !== job.apply_url && (
                <a
                  href={job.job_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-2.5 text-sm font-medium transition-colors hover:bg-muted"
                >
                  View Original
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </div>
          </div>
          
          {/* AI Insights */}
          {(job.ai_summary || job.ai_requirements || job.ai_tech_stack) && (
            <div className="mt-6 rounded-xl border border-border bg-background p-6 sm:p-8">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="h-5 w-5 text-remote" />
                <h2 className="text-lg font-semibold">AI Insights</h2>
              </div>
              
              {job.ai_summary && (
                <div className="mb-4">
                  <h3 className="text-sm font-medium text-muted-foreground mb-1">Summary</h3>
                  <p className="text-foreground">{job.ai_summary}</p>
                </div>
              )}
              
              {job.ai_requirements && (
                <div className="mb-4">
                  <h3 className="text-sm font-medium text-muted-foreground mb-2">Key Requirements</h3>
                  <ul className="space-y-1">
                    {job.ai_requirements.split(';').map((req, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <CheckCircle className="h-4 w-4 text-remote shrink-0 mt-0.5" />
                        <span>{req.trim()}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {job.ai_tech_stack && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-2">Tech Stack</h3>
                  <div className="flex flex-wrap gap-2">
                    {job.ai_tech_stack.split(',').map((tech) => (
                      <span key={tech} className="rounded-md bg-muted px-2 py-1 text-xs font-medium">
                        {tech.trim()}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              {job.ai_reasons && (
                <div className="mt-4 pt-4 border-t border-border">
                  <p className="text-xs text-muted-foreground">{job.ai_reasons}</p>
                </div>
              )}
            </div>
          )}
          
          {/* Description */}
          {job.description_text && (
            <div className="mt-6 rounded-xl border border-border bg-background p-6 sm:p-8">
              <h2 className="text-lg font-semibold mb-4">Job Description</h2>
              <FormattedDescription 
                text={job.description_text}
                className="prose-headings:text-foreground prose-headings:font-semibold prose-headings:mt-6 prose-headings:mb-3 prose-headings:text-base prose-p:text-muted-foreground prose-p:mb-4 prose-p:leading-relaxed prose-ul:my-4 prose-ul:space-y-2 prose-li:text-muted-foreground prose-li:leading-relaxed prose-li:marker:text-foreground/40"
              />
            </div>
          )}
          
          {/* Company Info */}
          <div className="mt-6 rounded-xl border border-border bg-background p-6 sm:p-8">
            <h2 className="text-lg font-semibold mb-4">Company</h2>
            
            {job.ai_company_summary && (
              <p className="text-muted-foreground mb-4">{job.ai_company_summary}</p>
            )}
            
            <div className="flex flex-wrap gap-3">
              {job.company_website && (
                <a
                  href={job.company_website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <Globe className="h-4 w-4" />
                  Website
                </a>
              )}
              
              {job.linkedin_url && (
                <a
                  href={job.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <Linkedin className="h-4 w-4" />
                  LinkedIn
                </a>
              )}
              
              {job.emails && job.emails.length > 0 && (
                <a
                  href={`mailto:${job.emails[0]}`}
                  className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <Mail className="h-4 w-4" />
                  {job.emails[0]}
                </a>
              )}
            </div>
          </div>
          
          {/* Source attribution */}
          <p className="mt-6 text-center text-xs text-muted-foreground">
            Source: {job.source} • Last updated <span suppressHydrationWarning>{formatRelativeTime(job.last_seen_at, nowIso)}</span>
          </p>
        </div>
      </main>
      
      <Footer />
    </>
  );
}
