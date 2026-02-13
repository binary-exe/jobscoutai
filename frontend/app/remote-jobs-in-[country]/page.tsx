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
    country: string;
  };
}

// Common country mappings
const COUNTRY_MAPPINGS: Record<string, { name: string; iso: string; timezone?: string }> = {
  'usa': { name: 'United States', iso: 'US', timezone: 'Americas' },
  'uk': { name: 'United Kingdom', iso: 'GB', timezone: 'Europe' },
  'germany': { name: 'Germany', iso: 'DE', timezone: 'Europe' },
  'canada': { name: 'Canada', iso: 'CA', timezone: 'Americas' },
  'australia': { name: 'Australia', iso: 'AU', timezone: 'Asia-Pacific' },
  'netherlands': { name: 'Netherlands', iso: 'NL', timezone: 'Europe' },
  'spain': { name: 'Spain', iso: 'ES', timezone: 'Europe' },
  'france': { name: 'France', iso: 'FR', timezone: 'Europe' },
  'portugal': { name: 'Portugal', iso: 'PT', timezone: 'Europe' },
  'ireland': { name: 'Ireland', iso: 'IE', timezone: 'Europe' },
  'sweden': { name: 'Sweden', iso: 'SE', timezone: 'Europe' },
  'india': { name: 'India', iso: 'IN', timezone: 'Asia-Pacific' },
  'brazil': { name: 'Brazil', iso: 'BR', timezone: 'Americas' },
  'mexico': { name: 'Mexico', iso: 'MX', timezone: 'Americas' },
  'poland': { name: 'Poland', iso: 'PL', timezone: 'Europe' },
  'italy': { name: 'Italy', iso: 'IT', timezone: 'Europe' },
  'switzerland': { name: 'Switzerland', iso: 'CH', timezone: 'Europe' },
  'singapore': { name: 'Singapore', iso: 'SG', timezone: 'Asia-Pacific' },
  'europe': { name: 'Europe', iso: 'EU', timezone: 'Europe' },
  'latam': { name: 'Latin America', iso: 'LATAM', timezone: 'Americas' },
  'apac': { name: 'Asia-Pacific', iso: 'APAC', timezone: 'Asia-Pacific' },
};

function formatCountryName(country: string | undefined): string {
  if (!country) return 'Worldwide';
  
  const mapping = COUNTRY_MAPPINGS[country.toLowerCase()];
  if (mapping) return mapping.name;
  
  // Convert kebab-case to Title Case
  return country
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const countryName = formatCountryName(params?.country);
  const title = `Remote Jobs in ${countryName} | JobScoutAI`;
  const description = `Find remote jobs hiring in ${countryName}. Browse curated remote positions with AI-powered matching, trust reports, and personalized apply packs.`;
  
  return {
    title,
    description,
    keywords: [
      `remote jobs ${countryName}`,
      `${countryName} remote positions`,
      `work from home ${countryName}`,
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

export default async function RemoteJobsInCountryPage({ params }: PageProps) {
  const country = params?.country || 'usa';
  const countryName = formatCountryName(country);
  const mapping = COUNTRY_MAPPINGS[country.toLowerCase()];
  
  // Fetch relevant jobs - search by country name or timezone preference
  let jobs: Job[] = [];
  try {
    const response = await getJobs({ 
      q: mapping?.name || countryName,
      remote: 'remote',
      page_size: 20 
    });
    jobs = response.jobs;
  } catch {
    // Fallback to empty on error
  }
  
  return (
    <>
      <BrowseSectionTracker section="remote-by-country" segment={country} />
      <Header />
      
      <main className="flex-1 py-8">
        <div className="container mx-auto max-w-5xl px-4">
          {/* SEO Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl mb-3">
              Remote Jobs in {countryName}
            </h1>
            <p className="text-muted-foreground max-w-2xl">
              Find remote positions that are open to candidates in {countryName}. 
              All jobs are curated and include AI-powered trust reports.
            </p>
            {mapping?.timezone && (
              <p className="text-sm text-muted-foreground mt-2">
                These jobs typically prefer candidates in the <strong>{mapping.timezone}</strong> timezone region.
              </p>
            )}
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
                        <span className="flex items-center gap-1">
                          <Clock className="h-3.5 w-3.5" />
                          {formatRelativeTime(job.posted_at || job.first_seen_at)}
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
                No remote jobs specifically targeting {countryName} found at the moment.
              </p>
              <Link
                href="/"
                className="mt-4 inline-flex items-center gap-2 text-primary hover:underline"
              >
                Browse all remote jobs
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          )}
          
          {/* SEO Content */}
          <div className="mt-12 prose prose-sm max-w-none text-muted-foreground">
            <h2 className="text-foreground">Remote Work in {countryName}</h2>
            <p>
              Looking for remote jobs that are open to candidates in {countryName}? 
              JobScoutAI curates the best remote positions and helps you identify 
              real opportunities with our AI-powered trust reports.
            </p>
            <p>
              Many companies are now hiring globally, but time zone alignment often matters 
              for collaboration. Jobs listed here typically accept candidates from {countryName} 
              or the surrounding region.
            </p>
          </div>
          
          {/* Related Countries */}
          <div className="mt-8 pt-8 border-t border-border">
            <h3 className="font-semibold mb-4">Remote Jobs in Other Regions</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(COUNTRY_MAPPINGS)
                .filter(([key]) => key !== country.toLowerCase())
                .slice(0, 8)
                .map(([key, value]) => (
                  <Link
                    key={key}
                    href={`/remote-jobs-in-${key}`}
                    className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
                  >
                    {value.name}
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
