'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { FileText, Link as LinkIcon, Sparkles, CheckCircle2, AlertTriangle, Clock, Loader2, Edit2, Save, Shield, AlertCircle, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { parseJob, updateJobTarget, generateApplyPack, generateTrustReport, submitTrustFeedback, uploadResume, importJobFromJobScout, createApplication, getHistory, getJobTarget, generateInterviewCoach, getQuota, queryKnowledge, indexKnowledgeDocument, type Quota, type ParsedJob, type ApplyPack, type TrustReport, type InterviewCoachResult, type KbQueryResponse } from '@/lib/apply-api';
import type { JobDetail } from '@/lib/api';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import { getProfile, getResume } from '@/lib/profile-api';
import { trackApplyWorkspaceOpened, trackJobImported, trackTrustReportGenerated, trackApplyPackCreated, trackFirstApplyPackCreated, trackApplicationTracked, trackDocxDownloaded, trackEvent, setUserProperties } from '@/lib/analytics';

export default function ApplyWorkspacePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [authChecked, setAuthChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [resumeText, setResumeText] = useState('');
  const [profileResumeVersions, setProfileResumeVersions] = useState<any[]>([]);
  const [selectedProfileResumeId, setSelectedProfileResumeId] = useState<string | null>(null);
  const [isLoadingProfileResume, setIsLoadingProfileResume] = useState(false);
  const [jobUrl, setJobUrl] = useState('');
  const [jobText, setJobText] = useState('');
  const [isParsing, setIsParsing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [parsedJob, setParsedJob] = useState<ParsedJob | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedJob, setEditedJob] = useState<Partial<ParsedJob>>({});
  const [applyPack, setApplyPack] = useState<ApplyPack | null>(null);
  const [trustReport, setTrustReport] = useState<TrustReport | null>(null);
  const [isGeneratingTrust, setIsGeneratingTrust] = useState(false);
  const [isSubmittingTrustFeedback, setIsSubmittingTrustFeedback] = useState(false);
  const [trustFeedbackNotice, setTrustFeedbackNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  // Prevent infinite retry loops: attempt auto-import at most once per jobId / job_target_id
  const [autoImportAttemptedJobId, setAutoImportAttemptedJobId] = useState<string | null>(null);
  const [autoLoadAttemptedJobTargetId, setAutoLoadAttemptedJobTargetId] = useState<string | null>(null);
  const [trackedApplicationId, setTrackedApplicationId] = useState<string | null>(null);
  const [isTracking, setIsTracking] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [hasProfile, setHasProfile] = useState(false);
  const [interviewCoachResult, setInterviewCoachResult] = useState<InterviewCoachResult | null>(null);
  const [isGeneratingInterviewCoach, setIsGeneratingInterviewCoach] = useState(false);
  const [interviewCoachError, setInterviewCoachError] = useState<string | null>(null);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [quotaLoaded, setQuotaLoaded] = useState(false);
  const [askNotesQuestion, setAskNotesQuestion] = useState('');
  const [askNotesResult, setAskNotesResult] = useState<KbQueryResponse | null>(null);
  const [isAskingNotes, setIsAskingNotes] = useState(false);
  const [addNoteText, setAddNoteText] = useState('');
  const [isAddingNote, setIsAddingNote] = useState(false);
  const [showAddNote, setShowAddNote] = useState(false);
  const [hashInterviewPrep, setHashInterviewPrep] = useState(false);

  // Auth check - redirect to login if not authenticated
  useEffect(() => {
    let cancelled = false;

    (async () => {
      // Skip auth check if Supabase not configured (dev mode)
      if (!isSupabaseConfigured()) {
        setAuthChecked(true);
        setIsAuthenticated(true);
        return;
      }

      const { data } = await supabase.auth.getSession();
      if (cancelled) return;

      if (data.session) {
        setIsAuthenticated(true);
        // Track workspace opened
        const source = searchParams?.get('jobId') ? 'job_detail' : 'direct';
        trackApplyWorkspaceOpened(source as 'direct' | 'job_card' | 'job_detail');
      } else {
        // Redirect to login with return URL
        const returnUrl = typeof window !== 'undefined' ? window.location.pathname + window.location.search : '/apply';
        router.replace(`/login?next=${encodeURIComponent(returnUrl)}`);
        return;
      }
      setAuthChecked(true);
    })();

    return () => {
      cancelled = true;
    };
  }, [router, searchParams]);

  // Pre-fill "Ask your notes" with company when parsedJob changes
  useEffect(() => {
    if (parsedJob?.company) {
      setAskNotesQuestion(`What do I know about ${parsedJob.company}?`);
    }
  }, [parsedJob?.company]);

  // Track hash on mount and when it changes
  useEffect(() => {
    const onHashChange = () => setHashInterviewPrep(window.location.hash === '#interview-prep');
    onHashChange();
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  // Scroll to Interview Prep section when hash is #interview-prep and content is ready
  useEffect(() => {
    if (hashInterviewPrep) {
      const el = document.getElementById('interview-prep');
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
  }, [hashInterviewPrep, parsedJob, applyPack]);

  // Load quota/capability flags once authenticated (prevents noisy 404s for disabled Premium AI endpoints)
  useEffect(() => {
    let cancelled = false;
    if (!authChecked || !isAuthenticated) return;
    (async () => {
      try {
        const q = await getQuota();
        if (!cancelled) setQuota(q);
      } catch {
        // best-effort; don't block UI
      } finally {
        if (!cancelled) setQuotaLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authChecked, isAuthenticated]);

  // If logged in, auto-load primary resume from Profile once
  useEffect(() => {
    if (!authChecked || !isAuthenticated) return;

    let cancelled = false;

    (async () => {
      try {
        setIsLoadingProfileResume(true);

        const prof = await getProfile();
        if (cancelled) return;
        
        const resumeVersions = prof.resume_versions || [];
        setProfileResumeVersions(resumeVersions);

        const primaryId = prof.profile?.primary_resume_id ? String(prof.profile.primary_resume_id) : null;
        
        // Check if user has a profile/resume (for onboarding)
        const hasExistingProfile = !!(prof.profile || resumeVersions.length > 0);
        setHasProfile(hasExistingProfile);
        const hasResume = resumeVersions.length > 0;
        const hasCompletedProfile = !!prof.profile && !!(prof.profile.headline || prof.profile.skills?.length || prof.profile.desired_roles?.length);
        setUserProperties({ has_resume: hasResume, has_completed_profile: hasCompletedProfile });
        
        // Show onboarding banner for first-time users without a resume
        if (!hasExistingProfile && !localStorage.getItem('jobscout_onboarding_dismissed')) {
          setShowOnboarding(true);
        }
        
        if (primaryId) {
          setSelectedProfileResumeId(primaryId);
          // Only auto-fill if user hasn't already typed or uploaded a resume
          if (!resumeText.trim()) {
            const r = await getResume(primaryId);
            if (cancelled) return;
            const text = (r?.resume?.resume_text || '').toString();
            if (text) {
              setResumeText(text);
              setUploadedFileName('Profile resume (primary)');
            }
          }
        }
      } catch {
        // Ignore; Apply workspace works without profile
        // Show onboarding for new users who hit profile not found
        if (!localStorage.getItem('jobscout_onboarding_dismissed')) {
          setShowOnboarding(true);
        }
      } finally {
        if (!cancelled) setIsLoadingProfileResume(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authChecked, isAuthenticated]);

  const handleSelectProfileResume = async (resumeId: string) => {
    setError(null);
    setIsLoadingProfileResume(true);
    try {
      setSelectedProfileResumeId(resumeId);
      const r = await getResume(resumeId);
      const text = (r?.resume?.resume_text || '').toString();
      if (text) {
        setResumeText(text);
        setUploadedFileName('Profile resume');
      } else {
        setError('Could not load selected resume');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load resume');
    } finally {
      setIsLoadingProfileResume(false);
    }
  };

  // Auto-import job from JobScout if jobId is in query params
  // Wait for auth to complete before attempting import
  useEffect(() => {
    if (!authChecked || !isAuthenticated) return;
    
    const jobId = searchParams?.get('jobId');
    if (jobId && !parsedJob && !isImporting && jobId !== autoImportAttemptedJobId) {
      setAutoImportAttemptedJobId(jobId);
      handleImportFromJobScout(jobId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, parsedJob, isImporting, autoImportAttemptedJobId, authChecked, isAuthenticated]);

  // Deep-link: load job target by ID (e.g. from extension "Open Apply")
  useEffect(() => {
    if (!authChecked || !isAuthenticated) return;
    const jobTargetId = searchParams?.get('job_target_id');
    if (!jobTargetId || parsedJob || jobTargetId === autoLoadAttemptedJobTargetId) return;
    setAutoLoadAttemptedJobTargetId(jobTargetId);
    (async () => {
      try {
        const result = await getJobTarget(jobTargetId);
        setParsedJob(result);
        setEditedJob({
          title: result.title,
          company: result.company,
          location: result.location,
          remote_type: result.remote_type,
          employment_type: result.employment_type,
          salary_min: result.salary_min,
          salary_max: result.salary_max,
          salary_currency: result.salary_currency,
          description_text: result.description_text,
        });
        if (result.job_url) setJobUrl(result.job_url);
        if (result.description_text) setJobText(result.description_text);
        handleGenerateTrustReport(result.job_target_id);
      } catch {
        setAutoLoadAttemptedJobTargetId(null);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authChecked, isAuthenticated, searchParams, parsedJob, autoLoadAttemptedJobTargetId]);

  const handleImportFromJobScout = async (jobId: string) => {
    setIsImporting(true);
    setError(null);
    try {
      // Fetch job details from JobScout API (client-side)
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
      const res = await fetch(`${API_URL}/jobs/${jobId}`);
      if (!res.ok) {
        throw new Error('Job not found');
      }
      const job: JobDetail = await res.json();
      
      // Import into Apply Workspace
      const result = await importJobFromJobScout({
        job_id: job.job_id,
        job_url: job.job_url,
        apply_url: job.apply_url,
        title: job.title,
        company: job.company,
        location_raw: job.location_raw,
        remote_type: job.remote_type,
        employment_types: job.employment_types,
        salary_min: job.salary_min,
        salary_max: job.salary_max,
        salary_currency: job.salary_currency,
        description_text: job.description_text,
        company_website: job.company_website,
        linkedin_url: job.linkedin_url,
        ai_company_summary: job.ai_company_summary,
        ai_summary: job.ai_summary,
        ai_requirements: job.ai_requirements,
        ai_tech_stack: job.ai_tech_stack,
      });

      setParsedJob(result);
      setEditedJob({
        title: result.title,
        company: result.company,
        location: result.location,
        remote_type: result.remote_type,
        employment_type: result.employment_type,
        salary_min: result.salary_min,
        salary_max: result.salary_max,
        salary_currency: result.salary_currency,
        description_text: result.description_text,
      });
      
      // Pre-fill job URL and text fields
      if (result.job_url) {
        setJobUrl(result.job_url);
      }
      if (result.description_text) {
        setJobText(result.description_text);
      }
      
      // Track job import
      trackJobImported(result.job_target_id, 'jobscout_import');
      
      // Automatically generate trust report
      handleGenerateTrustReport(result.job_target_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to import job from JobScout');
    } finally {
      setIsImporting(false);
    }
  };

  const handleParseJob = async () => {
    if (!jobUrl.trim() && !jobText.trim()) {
      setError('Please provide either a job URL or job description text');
      return;
    }

    setIsParsing(true);
    setError(null);
    try {
      const result = await parseJob(jobUrl || undefined, jobText || undefined);
      setParsedJob(result);
      setEditedJob({
        title: result.title,
        company: result.company,
        location: result.location,
        remote_type: result.remote_type,
        employment_type: result.employment_type,
        salary_min: result.salary_min,
        salary_max: result.salary_max,
        salary_currency: result.salary_currency,
        description_text: result.description_text,
      });
      
      // Automatically generate trust report after parsing
      handleGenerateTrustReport(result.job_target_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse job');
    } finally {
      setIsParsing(false);
    }
  };

  const handleGenerateTrustReport = async (
    jobTargetId: string,
    opts: { force?: boolean; refresh_apply_link?: boolean } = {}
  ) => {
    setIsGeneratingTrust(true);
    setTrustFeedbackNotice(null);
    try {
      const report = await generateTrustReport(jobTargetId, opts);
      setTrustReport(report);
      // Track trust report generation
      trackTrustReportGenerated(jobTargetId, report.trust_score);
    } catch (err) {
      // Don't show error for trust report - it's optional
      console.error('Failed to generate trust report:', err);
    } finally {
      setIsGeneratingTrust(false);
    }
  };

  const confidenceLabel = (n?: number) => {
    if (n === undefined || n === null) return null;
    if (n >= 80) return 'High';
    if (n >= 60) return 'Medium';
    return 'Low';
  };

  const handleSubmitTrustFeedback = async (payload: Parameters<typeof submitTrustFeedback>[1]) => {
    if (!parsedJob) return;
    setIsSubmittingTrustFeedback(true);
    setTrustFeedbackNotice(null);
    try {
      const res = await submitTrustFeedback(parsedJob.job_target_id, payload);
      setTrustReport((prev) => (prev ? { ...prev, community: res.community as any } : prev));
      setTrustFeedbackNotice('Thanks — your feedback helps improve Trust Reports.');
      trackEvent('trust_report_feedback_submitted', { ...payload, job_target_id: parsedJob.job_target_id });
    } catch (err) {
      setTrustFeedbackNotice(err instanceof Error ? err.message : 'Failed to submit feedback');
    } finally {
      setIsSubmittingTrustFeedback(false);
    }
  };

  const handleSaveEdits = async () => {
    if (!parsedJob) return;

    setIsParsing(true);
    try {
      const updated = await updateJobTarget(parsedJob.job_target_id, editedJob);
      setParsedJob(updated);
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update job');
    } finally {
      setIsParsing(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    setError(null);
    try {
      const result = await uploadResume(file);
      setResumeText(result.resume_text);
      setUploadedFileName(result.filename);
      trackEvent('resume_uploaded', { context: 'apply_workspace' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload resume');
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleGenerateInterviewCoach = async () => {
    if (!resumeText.trim() || !parsedJob) return;
    setInterviewCoachError(null);
    let q = quota;
    if (!quotaLoaded) {
      try {
        q = await getQuota();
        setQuota(q);
      } catch {
        // ignore; fallback to attempting request
      } finally {
        setQuotaLoaded(true);
      }
    }
    if (q && q.premium_ai_enabled === false) {
      setInterviewCoachError('Interview prep is not enabled on this server.');
      return;
    }
    if (q && q.premium_ai_configured === false) {
      setInterviewCoachError('AI is not configured. Contact support.');
      return;
    }
    setIsGeneratingInterviewCoach(true);
    setInterviewCoachResult(null);
    try {
      const res = await generateInterviewCoach({
        resume_text: resumeText,
        job_target_id: parsedJob.job_target_id,
      });
      setInterviewCoachError(null);
      setInterviewCoachResult(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Request failed';
      if (
        msg.includes('Insufficient credits')
        || msg.includes('Premium AI quota exceeded')
        || msg.includes('not available on your plan')
        || msg.includes('403')
      ) {
        setInterviewCoachError('Interview prep quota used or not available on your plan. Upgrade for more.');
      } else if (msg.includes('404') || msg.includes('disabled')) {
        setInterviewCoachError('Interview prep is not enabled on this server.');
      } else if (msg.includes('not configured')) {
        setInterviewCoachError('AI is not configured. Contact support.');
      } else if (msg.includes('503') || msg.includes('temporarily unavailable')) {
        setInterviewCoachError('Interview prep is temporarily unavailable. Please try again in a bit.');
      } else if (msg.toLowerCase().includes('invalid response') || msg.toLowerCase().includes('malformed')) {
        setInterviewCoachError('Interview prep returned an invalid AI response. Please try again.');
      } else if (msg.includes('generation failed')) {
        setInterviewCoachError('Interview prep could not be generated right now. Please try again in a moment.');
      } else {
        setInterviewCoachError(msg);
      }
    } finally {
      setIsGeneratingInterviewCoach(false);
    }
  };

  const handleGeneratePack = async () => {
    if (!resumeText.trim()) {
      setError('Please provide your resume text');
      return;
    }
    if (!parsedJob) {
      setError('Please parse a job first');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setInterviewCoachError(null);
    setInterviewCoachResult(null);
    trackEvent('apply_pack_generation_started', {});
    try {
      const pack = await generateApplyPack(
        resumeText,
        parsedJob.job_url,
        parsedJob.description_text,
        true
      );
      setApplyPack(pack);
      const { total } = await getHistory().catch(() => ({ total: 1 }));
      trackApplyPackCreated(pack.apply_pack_id, total);
      if (total === 1) {
        trackFirstApplyPackCreated(pack.apply_pack_id);
      }
      trackEvent('apply_pack_generation_completed', { apply_pack_id: pack.apply_pack_id });
      setTrackedApplicationId(null);
      await handleGenerateInterviewCoach();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate apply pack');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleStartTracking = async () => {
    if (!applyPack || !parsedJob) {
      setError('Please generate an apply pack first');
      return;
    }

    setIsTracking(true);
    setError(null);
    try {
      const application = await createApplication(
        applyPack.apply_pack_id,
        parsedJob.job_target_id,
        'applied'
      );
      setTrackedApplicationId(application.application_id);
      // Track application started
      trackApplicationTracked(application.application_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start tracking');
    } finally {
      setIsTracking(false);
    }
  };

  // Show loading while checking auth
  if (!authChecked) {
    return (
      <>
        <Header />
        <main className="flex-1">
          <div className="container mx-auto max-w-7xl px-4 py-12">
            <div className="flex flex-col items-center justify-center space-y-4">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-muted-foreground">Checking authentication...</p>
            </div>
          </div>
        </main>
        <Footer />
      </>
    );
  }

  return (
    <>
      <Header />
      
      <main className="flex-1">
        <div className="container mx-auto max-w-7xl px-4 py-8">
          {/* Hero Section */}
          <div className="mb-8 text-center">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              AI-Powered Application Assistant
            </div>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Apply Workspace
            </h1>
            <p className="mt-3 text-muted-foreground max-w-2xl mx-auto">
              Upload your resume and paste a job link or description. Get ATS-ready tailored content,
              a Trust Report, and track your applications. Don&apos;t waste time on ghost or scam jobs—check trust first.
            </p>
          </div>

          {/* Empty state when landing on Interview Prep with no job */}
          {hashInterviewPrep && !parsedJob && (
            <div className="mb-6 rounded-xl border border-border bg-muted/30 p-6 text-center">
              <p className="text-muted-foreground">
                Add a job to get interview prep.
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                Parse a job URL or paste a job description below to get started.
              </p>
            </div>
          )}

          {/* Onboarding Banner for First-Time Users */}
          {showOnboarding && (
            <div className="mb-6 rounded-xl border border-primary/30 bg-primary/5 p-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold mb-2">Welcome to Apply Workspace!</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Get started by uploading your resume below. Your resume will be saved to your profile 
                    for easy reuse across applications.
                  </p>
                  <div className="flex items-center gap-3">
                    <Link
                      href="/profile"
                      className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                    >
                      <FileText className="h-4 w-4" />
                      Complete Profile Setup
                    </Link>
                    <button
                      onClick={() => {
                        setShowOnboarding(false);
                        localStorage.setItem('jobscout_onboarding_dismissed', 'true');
                      }}
                      className="text-sm text-muted-foreground hover:text-foreground"
                    >
                      Skip for now
                    </button>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setShowOnboarding(false);
                    localStorage.setItem('jobscout_onboarding_dismissed', 'true');
                  }}
                  className="text-muted-foreground hover:text-foreground"
                  aria-label="Dismiss"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>
            </div>
          )}

          {/* Main Workspace */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Pane - Inputs */}
            <div className="space-y-6">
              <div className="rounded-xl border border-border bg-card p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  Resume
                </h2>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Upload PDF/DOCX or paste text
                    </label>

                    {/* Profile resume selector (if logged in) */}
                    {profileResumeVersions.length > 0 && (
                      <div className="mb-3">
                        <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                          Use saved resume
                        </label>
                        <select
                          value={selectedProfileResumeId || ''}
                          onChange={(e) => {
                            const v = e.target.value;
                            if (v) handleSelectProfileResume(v);
                          }}
                          disabled={isLoadingProfileResume}
                          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary disabled:opacity-60"
                        >
                          <option value="">Select a saved resume…</option>
                          {profileResumeVersions.map((r) => {
                            const id = String(r.resume_id);
                            const created = r.created_at ? new Date(r.created_at).toLocaleDateString() : '';
                            return (
                              <option key={id} value={id}>
                                {created ? `${created} · ${id.slice(0, 8)}` : id}
                              </option>
                            );
                          })}
                        </select>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Or upload/paste a different resume below for this application.
                        </p>
                      </div>
                    )}
                    
                    {/* File Upload Area */}
                    <div
                      onDrop={handleDrop}
                      onDragOver={handleDragOver}
                      className="mb-3 border-2 border-dashed border-border rounded-lg p-6 text-center hover:border-primary/50 transition-colors cursor-pointer"
                    >
                      <input
                        type="file"
                        accept=".pdf,.docx,.doc"
                        onChange={handleFileChange}
                        className="hidden"
                        id="resume-upload"
                        disabled={isUploading}
                      />
                      <label
                        htmlFor="resume-upload"
                        className="cursor-pointer"
                      >
                        {isUploading ? (
                          <div className="flex flex-col items-center gap-2">
                            <Loader2 className="h-6 w-6 animate-spin text-primary" />
                            <span className="text-sm text-muted-foreground">Uploading...</span>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center gap-2">
                            <FileText className="h-8 w-8 text-muted-foreground" />
                            <span className="text-sm font-medium">
                              {uploadedFileName ? `Uploaded: ${uploadedFileName}` : 'Click to upload or drag and drop'}
                            </span>
                            <span className="text-xs text-muted-foreground">PDF or DOCX (max 10MB)</span>
                          </div>
                        )}
                      </label>
                    </div>
                    
                    <p className="text-xs text-muted-foreground mb-2 text-center">OR</p>
                    
                    <textarea
                      value={resumeText}
                      onChange={(e) => {
                        setResumeText(e.target.value);
                        setUploadedFileName(null);
                      }}
                      placeholder="Paste your resume text here..."
                      className="w-full min-h-[200px] rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Proof Points (2-3 quantified achievements)
                    </label>
                    <textarea
                      placeholder="e.g., Increased conversion by 40%..."
                      className="w-full min-h-[100px] rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    />
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <LinkIcon className="h-5 w-5" />
                  Job Description
                </h2>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Job URL or paste JD text
                    </label>
                    <input
                      type="url"
                      value={jobUrl}
                      onChange={(e) => setJobUrl(e.target.value)}
                      placeholder="https://company.com/careers/job-id"
                      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm mb-2"
                      disabled={isParsing}
                    />
                    <p className="text-xs text-muted-foreground mb-3">OR</p>
                    <textarea
                      value={jobText}
                      onChange={(e) => setJobText(e.target.value)}
                      placeholder="Paste job description text here..."
                      className="w-full min-h-[200px] rounded-lg border border-input bg-background px-3 py-2 text-sm"
                      disabled={isParsing}
                    />
                  </div>
                  
                  <button
                    onClick={handleParseJob}
                    disabled={isParsing || (!jobUrl.trim() && !jobText.trim())}
                    className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isParsing ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Parsing...
                      </>
                    ) : (
                      'Parse Job'
                    )}
                  </button>
                </div>
              </div>

              {/* Extracted Job Fields (Editable) */}
              {parsedJob && (
                <div className="rounded-xl border border-border bg-card p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                      Extracted Fields
                    </h2>
                    {!isEditing ? (
                      <button
                        onClick={() => setIsEditing(true)}
                        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
                      >
                        <Edit2 className="h-4 w-4" />
                        Edit
                      </button>
                    ) : (
                      <button
                        onClick={handleSaveEdits}
                        disabled={isParsing}
                        className="flex items-center gap-1 text-sm text-primary hover:text-primary/80"
                      >
                        <Save className="h-4 w-4" />
                        Save
                      </button>
                    )}
                  </div>
                  
                  <div className="space-y-3 text-sm">
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Title</label>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editedJob.title || ''}
                          onChange={(e) => setEditedJob({ ...editedJob, title: e.target.value })}
                          className="w-full rounded border border-input bg-background px-2 py-1 text-sm"
                        />
                      ) : (
                        <p className="font-medium">{parsedJob.title || 'Not extracted'}</p>
                      )}
                    </div>
                    
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Company</label>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editedJob.company || ''}
                          onChange={(e) => setEditedJob({ ...editedJob, company: e.target.value })}
                          className="w-full rounded border border-input bg-background px-2 py-1 text-sm"
                        />
                      ) : (
                        <p>{parsedJob.company || 'Not extracted'}</p>
                      )}
                    </div>
                    
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Location</label>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editedJob.location || ''}
                          onChange={(e) => setEditedJob({ ...editedJob, location: e.target.value })}
                          className="w-full rounded border border-input bg-background px-2 py-1 text-sm"
                        />
                      ) : (
                        <p>{parsedJob.location || 'Not extracted'}</p>
                      )}
                    </div>
                    
                    {parsedJob.salary_min && (
                      <div>
                        <label className="block text-xs text-muted-foreground mb-1">Salary</label>
                        <p>
                          {parsedJob.salary_currency || '$'}{parsedJob.salary_min}
                          {parsedJob.salary_max && ` - ${parsedJob.salary_currency || '$'}${parsedJob.salary_max}`}
                        </p>
                      </div>
                    )}
                    
                    <div>
                      <label className="block text-xs text-muted-foreground mb-1">Extraction Method</label>
                      <p className="text-xs text-muted-foreground">
                        {parsedJob.extraction_method === 'jsonld' && '✓ JSON-LD (Schema.org)'}
                        {parsedJob.extraction_method === 'html' && '⚠ HTML parsing (heuristic)'}
                        {parsedJob.extraction_method === 'text' && '📝 Text parsing'}
                        {parsedJob.extraction_method === 'cached' && '💾 Cached'}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {error && (
                <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-500">
                  {error}
                </div>
              )}

              <button
                onClick={handleGeneratePack}
                disabled={isGenerating || !resumeText.trim() || !parsedJob}
                className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  'Generate Apply Pack'
                )}
              </button>
            </div>

            {/* Right Pane - Outputs */}
            <div className="space-y-6">
              {/* Trust Report */}
              {trustReport ? (
                <div className="rounded-xl border border-border bg-card p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                      <Shield className="h-5 w-5" />
                      Trust Report
                    </h2>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => parsedJob && handleGenerateTrustReport(parsedJob.job_target_id, { force: true, refresh_apply_link: true })}
                        disabled={isGeneratingTrust || !parsedJob}
                        className="text-xs rounded-lg border border-border px-3 py-1.5 hover:bg-muted disabled:opacity-50"
                        type="button"
                      >
                        Re-run
                      </button>
                      <div className="text-xs text-muted-foreground italic">
                        Signals only, not guarantees
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                      <div>
                        {trustReport.verified_at ? (() => {
                          const verified = new Date(trustReport.verified_at);
                          const now = new Date();
                          const days = Math.floor((now.getTime() - verified.getTime()) / (24 * 60 * 60 * 1000));
                          if (days === 0) return <>Last verified today</>;
                          if (days === 1) return <>Last verified 1 day ago</>;
                          return <>Last verified {days} days ago</>;
                        })() : (
                          <>Verified recently</>
                        )}
                      </div>
                      {trustReport.confidence?.overall !== undefined && (
                        <div>
                          Confidence: <span className="text-foreground">{confidenceLabel(trustReport.confidence.overall)} ({trustReport.confidence.overall}%)</span>
                        </div>
                      )}
                    </div>

                    {(trustReport.trust_score !== undefined && trustReport.trust_score !== null) && (
                      <div className="flex items-center justify-between rounded-lg bg-muted/30 p-3">
                        <span className="text-sm font-medium">Overall trust score</span>
                        <span className="text-sm font-semibold">{trustReport.trust_score}/100</span>
                      </div>
                    )}

                    {/* Community feedback */}
                    <div className="rounded-lg border border-border bg-background p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-medium">Community</div>
                        <div className="text-xs text-muted-foreground">
                          Reports: <span className="text-foreground">{trustReport.community?.reports_total ?? 0}</span>
                          {' · '}
                          Accurate: <span className="text-foreground">{trustReport.community?.accurate_total ?? 0}</span>
                          {' · '}
                          Inaccurate: <span className="text-foreground">{trustReport.community?.inaccurate_total ?? 0}</span>
                        </div>
                      </div>
                      {trustReport.community_reasons && trustReport.community_reasons.length > 0 && (
                        <ul className="mt-2 text-xs text-muted-foreground space-y-1 list-disc pl-5">
                          {trustReport.community_reasons.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>
                      )}
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={isSubmittingTrustFeedback}
                          onClick={() => handleSubmitTrustFeedback({ feedback_kind: 'accuracy', value: 'accurate' })}
                          className="text-xs rounded-lg border border-border px-3 py-1.5 hover:bg-muted disabled:opacity-50"
                        >
                          This was accurate
                        </button>
                        <button
                          type="button"
                          disabled={isSubmittingTrustFeedback}
                          onClick={() => handleSubmitTrustFeedback({ feedback_kind: 'accuracy', value: 'inaccurate' })}
                          className="text-xs rounded-lg border border-border px-3 py-1.5 hover:bg-muted disabled:opacity-50"
                        >
                          Inaccurate
                        </button>
                        <button
                          type="button"
                          disabled={isSubmittingTrustFeedback}
                          onClick={() => handleSubmitTrustFeedback({ feedback_kind: 'report', value: 'scam' })}
                          className="text-xs rounded-lg border border-border px-3 py-1.5 hover:bg-muted disabled:opacity-50"
                        >
                          Report scam
                        </button>
                        <button
                          type="button"
                          disabled={isSubmittingTrustFeedback}
                          onClick={() => handleSubmitTrustFeedback({ feedback_kind: 'report', value: 'ghost' })}
                          className="text-xs rounded-lg border border-border px-3 py-1.5 hover:bg-muted disabled:opacity-50"
                        >
                          Report ghost
                        </button>
                        <button
                          type="button"
                          disabled={isSubmittingTrustFeedback}
                          onClick={() => handleSubmitTrustFeedback({ feedback_kind: 'report', value: 'expired' })}
                          className="text-xs rounded-lg border border-border px-3 py-1.5 hover:bg-muted disabled:opacity-50"
                        >
                          Report expired
                        </button>
                      </div>
                      {trustFeedbackNotice && (
                        <div className="mt-2 text-xs text-muted-foreground">
                          {trustFeedbackNotice}
                        </div>
                      )}
                    </div>

                    {trustReport.apply_link_status && (
                      <div className="text-xs text-muted-foreground">
                        Apply link status: <span className="text-foreground">{trustReport.apply_link_status}</span>
                      </div>
                    )}

                    {trustReport.domain_consistency_reasons && trustReport.domain_consistency_reasons.length > 0 && (
                      <div className="rounded-lg border border-border bg-background p-3">
                        <div className="text-sm font-medium mb-2 flex items-center gap-2">
                          <AlertCircle className="h-4 w-4 text-hybrid" />
                          Domain consistency warnings
                        </div>
                        <p className="text-xs text-muted-foreground mb-1.5">Why we flagged this:</p>
                        <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-5">
                          {trustReport.domain_consistency_reasons.map((reason, i) => (
                            <li key={i}>{reason}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Scam Risk */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Scam Risk</span>
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                          trustReport.scam_risk === 'high' ? 'bg-red-500/20 text-red-500' :
                          trustReport.scam_risk === 'medium' ? 'bg-yellow-500/20 text-yellow-500' :
                          'bg-green-500/20 text-green-500'
                        }`}>
                          {trustReport.scam_risk.toUpperCase()}{trustReport.scam_score !== undefined && trustReport.scam_score !== null ? ` (${trustReport.scam_score})` : ''}
                        </span>
                      </div>
                      {trustReport.scam_reasons.length > 0 && (
                        <>
                          <p className="text-xs text-muted-foreground mb-1.5">Why we flagged this:</p>
                          <ul className="text-xs text-muted-foreground space-y-1">
                            {trustReport.scam_reasons.map((reason, i) => (
                              <li key={i} className="flex items-start gap-1">
                                <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                                <span>{reason}</span>
                              </li>
                            ))}
                          </ul>
                        </>
                      )}
                    </div>
                    
                    {/* Ghost Likelihood */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Ghost Job Likelihood</span>
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                          trustReport.ghost_likelihood === 'high' ? 'bg-red-500/20 text-red-500' :
                          trustReport.ghost_likelihood === 'medium' ? 'bg-yellow-500/20 text-yellow-500' :
                          'bg-green-500/20 text-green-500'
                        }`}>
                          {trustReport.ghost_likelihood.toUpperCase()}{trustReport.ghost_score !== undefined && trustReport.ghost_score !== null ? ` (${trustReport.ghost_score})` : ''}
                        </span>
                      </div>
                      {trustReport.ghost_reasons.length > 0 && (
                        <>
                          <p className="text-xs text-muted-foreground mb-1.5">Why we flagged this:</p>
                          <ul className="text-xs text-muted-foreground space-y-1">
                            {trustReport.ghost_reasons.map((reason, i) => (
                              <li key={i} className="flex items-start gap-1">
                                <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                                <span>{reason}</span>
                              </li>
                            ))}
                          </ul>
                        </>
                      )}
                    </div>
                    
                    {/* Staleness */}
                    {trustReport.staleness_score !== undefined && trustReport.staleness_score > 0 && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium">Staleness</span>
                          <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                            trustReport.staleness_score >= 50 ? 'bg-red-500/20 text-red-500' :
                            trustReport.staleness_score >= 20 ? 'bg-yellow-500/20 text-yellow-500' :
                            'bg-green-500/20 text-green-500'
                          }`}>
                            {trustReport.staleness_score}/100
                          </span>
                        </div>
                        {trustReport.staleness_reasons && trustReport.staleness_reasons.length > 0 && (
                          <>
                            <p className="text-xs text-muted-foreground mb-1.5">Why we flagged this:</p>
                            <ul className="text-xs text-muted-foreground space-y-1">
                              {trustReport.staleness_reasons.map((reason, i) => (
                                <li key={i} className="flex items-start gap-1">
                                  <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                                  <span>{reason}</span>
                                </li>
                              ))}
                            </ul>
                          </>
                        )}
                      </div>
                    )}

                    {/* Next steps (actionable checklist from plan) */}
                    {trustReport.next_steps && trustReport.next_steps.length > 0 && (
                      <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                        <h3 className="text-sm font-medium mb-2">Next steps</h3>
                        <ul className="text-xs text-muted-foreground space-y-1.5 list-disc pl-5">
                          {trustReport.next_steps.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ) : parsedJob ? (
                <div className="rounded-xl border border-border bg-card p-6">
                  <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <Shield className="h-5 w-5" />
                    Trust Report
                  </h2>
                  {isGeneratingTrust ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Analyzing...
                    </div>
                  ) : (
                    <button
                      onClick={() => handleGenerateTrustReport(parsedJob.job_target_id)}
                      className="text-sm text-primary hover:text-primary/80"
                    >
                      Generate Trust Report
                    </button>
                  )}
                </div>
              ) : (
                <div className="rounded-xl border border-border bg-card p-6">
                  <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <Shield className="h-5 w-5" />
                    Trust Report
                  </h2>
                  <div className="text-sm text-muted-foreground">
                    <p>Parse a job to see trust signals (scam risk, ghost-likelihood, staleness).</p>
                  </div>
                </div>
              )}

              {/* Apply Pack Output */}
              {applyPack ? (
                <div className="rounded-xl border border-border bg-card p-6 space-y-4">
                  <h2 className="text-lg font-semibold mb-4">Apply Pack</h2>
                  
                  {applyPack.tailored_summary && (
                    <div>
                      <h3 className="text-sm font-medium mb-2">Tailored Summary</h3>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                        {applyPack.tailored_summary}
                      </p>
                    </div>
                  )}
                  
                  {applyPack.tailored_bullets && applyPack.tailored_bullets.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium mb-2">Tailored Bullets</h3>
                      <ul className="space-y-1 text-sm text-muted-foreground">
                        {applyPack.tailored_bullets.map((bullet, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="text-primary">•</span>
                            <span>{bullet.text}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {applyPack.cover_note && (
                    <div>
                      <h3 className="text-sm font-medium mb-2">Cover Note</h3>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                        {applyPack.cover_note}
                      </p>
                    </div>
                  )}
                  
                  {applyPack.ats_checklist && (
                    <div>
                      <h3 className="text-sm font-medium mb-2">ATS Checklist</h3>
                      <div className="space-y-2 text-sm">
                        <div>
                          <span className="text-muted-foreground">Keyword Coverage: </span>
                          <span className="font-medium">{applyPack.keyword_coverage || 0}%</span>
                        </div>
                        {applyPack.ats_checklist.matched_skills && applyPack.ats_checklist.matched_skills.length > 0 && (
                          <div>
                            <span className="text-muted-foreground">Matched Skills: </span>
                            <span className="text-green-500">
                              {applyPack.ats_checklist.matched_skills.join(', ')}
                            </span>
                          </div>
                        )}
                        {applyPack.ats_checklist.missing_skills && applyPack.ats_checklist.missing_skills.length > 0 && (
                          <div>
                            <span className="text-muted-foreground">Missing Skills: </span>
                            <span className="text-red-500">
                              {applyPack.ats_checklist.missing_skills.join(', ')}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Interview Prep (auto-generated with Apply Pack) */}
                  <div id="interview-prep" className="pt-2 border-t border-border/70">
                    <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-primary" />
                      Interview Prep
                    </h3>
                    {isGeneratingInterviewCoach && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Generating tailored interview prep...
                      </div>
                    )}
                    {interviewCoachResult && (
                      <div className="space-y-3">
                        {interviewCoachResult.fallback && (
                          <p className="text-xs text-amber-400">
                            AI provider was temporarily unavailable, so this prep was generated using a deterministic fallback tailored to the job description.
                          </p>
                        )}
                        {interviewCoachResult.cached && (
                          <p className="text-xs text-muted-foreground">From cache (no additional usage).</p>
                        )}
                        {interviewCoachResult.kb_context_used === false && (
                          <p className="text-xs text-muted-foreground italic">
                            Add company notes to get more personalized prep next time.
                          </p>
                        )}
                        {Array.isArray(interviewCoachResult.result.questions) && interviewCoachResult.result.questions.length > 0 && (
                          <div>
                            <h4 className="text-xs font-medium mb-2">Top interview questions</h4>
                            <ul className="space-y-2">
                              {interviewCoachResult.result.questions.slice(0, 6).map((q, i) => (
                                <li key={i} className="rounded-lg border border-border bg-background p-3 text-xs">
                                  <p className="font-medium text-foreground">{q.question || 'Question'}</p>
                                  {q.why_they_ask && <p className="text-muted-foreground mt-1">Why: {q.why_they_ask}</p>}
                                  {Array.isArray(q.suggested_answer_outline) && q.suggested_answer_outline.length > 0 && (
                                    <p className="text-muted-foreground mt-1">Answer outline: {q.suggested_answer_outline.slice(0, 2).join('; ')}</p>
                                  )}
                                  {Array.isArray(q.study_focus) && q.study_focus.length > 0 && (
                                    <p className="text-muted-foreground mt-1">Study focus: {q.study_focus.slice(0, 3).join(', ')}</p>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {Array.isArray(interviewCoachResult.result.recommendations) && interviewCoachResult.result.recommendations.length > 0 && (
                          <div>
                            <h4 className="text-xs font-medium mb-1">Recommendations</h4>
                            <ul className="text-xs text-muted-foreground list-disc pl-5 space-y-1">
                              {interviewCoachResult.result.recommendations.slice(0, 4).map((item, idx) => (
                                <li key={idx}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {Array.isArray(interviewCoachResult.result.study_materials) && interviewCoachResult.result.study_materials.length > 0 && (
                          <div>
                            <h4 className="text-xs font-medium mb-1">Study materials</h4>
                            <ul className="space-y-2">
                              {interviewCoachResult.result.study_materials.slice(0, 4).map((m, idx) => (
                                <li key={idx} className="rounded-md border border-border/70 bg-background px-2.5 py-2 text-xs">
                                  <p className="font-medium text-foreground">{m.topic || 'Topic'} {m.priority ? `(${m.priority})` : ''}</p>
                                  {m.why_it_matters && <p className="text-muted-foreground mt-1">{m.why_it_matters}</p>}
                                  {Array.isArray(m.resources) && m.resources.length > 0 && (
                                    <p className="text-muted-foreground mt-1">Resources: {m.resources.slice(0, 2).join('; ')}</p>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {interviewCoachResult.result.gap_analysis && (
                          <div className="text-xs text-muted-foreground">
                            {Array.isArray(interviewCoachResult.result.gap_analysis.matched) && interviewCoachResult.result.gap_analysis.matched.length > 0 && (
                              <p>Matched: {interviewCoachResult.result.gap_analysis.matched.slice(0, 6).join(', ')}</p>
                            )}
                            {Array.isArray(interviewCoachResult.result.gap_analysis.missing) && interviewCoachResult.result.gap_analysis.missing.length > 0 && (
                              <p className="mt-1">Missing/priority: {interviewCoachResult.result.gap_analysis.missing.slice(0, 6).join(', ')}</p>
                            )}
                          </div>
                        )}
                        {Array.isArray(interviewCoachResult.result.next_steps) && interviewCoachResult.result.next_steps.length > 0 && (
                          <div>
                            <h4 className="text-xs font-medium mb-1">Next steps</h4>
                            <ul className="text-xs text-muted-foreground list-disc pl-5 space-y-1">
                              {interviewCoachResult.result.next_steps.slice(0, 4).map((step, idx) => (
                                <li key={idx}>{step}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                    {!isGeneratingInterviewCoach && !interviewCoachResult && !interviewCoachError && (
                      <p className="text-xs text-muted-foreground">
                        Interview prep is generated automatically each time you generate an Apply Pack.
                      </p>
                    )}
                    {interviewCoachError && (
                      <div className="mt-2 rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-xs text-red-500">
                        {interviewCoachError}
                      </div>
                    )}

                    {/* Ask your notes */}
                    {parsedJob?.company && (
                      <div className="mt-4 space-y-2">
                        <label className="block text-xs font-medium">Ask your notes</label>
                        <form
                          onSubmit={async (e) => {
                            e.preventDefault();
                            if (!askNotesQuestion.trim()) return;
                            setIsAskingNotes(true);
                            setAskNotesResult(null);
                            try {
                              const res = await queryKnowledge({
                                question: askNotesQuestion.trim(),
                                max_chunks: 10,
                              });
                              setAskNotesResult(res);
                            } catch {
                              setAskNotesResult({ answer: 'Query failed.', citations: [] });
                            } finally {
                              setIsAskingNotes(false);
                            }
                          }}
                          className="flex gap-2"
                        >
                          <input
                            type="text"
                            value={askNotesQuestion}
                            onChange={(e) => setAskNotesQuestion(e.target.value)}
                            placeholder={`What do I know about ${parsedJob.company}?`}
                            className="flex-1 rounded-md border border-input bg-background px-2 py-1.5 text-xs"
                          />
                          <button
                            type="submit"
                            disabled={isAskingNotes}
                            className="shrink-0 px-3 py-1.5 rounded-md text-xs bg-muted hover:bg-muted/80 disabled:opacity-50"
                          >
                            {isAskingNotes ? '...' : 'Ask'}
                          </button>
                        </form>
                        {askNotesResult && (
                          <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs">
                            <p className="whitespace-pre-wrap">{askNotesResult.answer}</p>
                            {askNotesResult.citations.length > 0 && (
                              <p className="mt-2 text-muted-foreground">
                                From {askNotesResult.citations.length} source(s)
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Add to prep library */}
                    {parsedJob?.job_target_id && (
                      <div className="mt-4">
                        <button
                          type="button"
                          onClick={() => setShowAddNote(!showAddNote)}
                          className="text-xs text-muted-foreground hover:text-foreground"
                        >
                          {showAddNote ? 'Hide' : 'Add to prep library'}
                        </button>
                        {showAddNote && (
                          <form
                            onSubmit={async (e) => {
                              e.preventDefault();
                              if (!addNoteText.trim()) return;
                              setIsAddingNote(true);
                              try {
                                await indexKnowledgeDocument({
                                  source_type: 'manual_note',
                                  source_table: 'job_targets',
                                  source_id: parsedJob.job_target_id,
                                  text: addNoteText.trim(),
                                });
                                setAddNoteText('');
                                setShowAddNote(false);
                              } finally {
                                setIsAddingNote(false);
                              }
                            }}
                            className="mt-2 space-y-2"
                          >
                            <textarea
                              value={addNoteText}
                              onChange={(e) => setAddNoteText(e.target.value)}
                              placeholder="Company research, interview notes..."
                              rows={3}
                              className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs"
                            />
                            <button
                              type="submit"
                              disabled={isAddingNote}
                              className="px-3 py-1.5 rounded-md text-xs bg-muted hover:bg-muted/80 disabled:opacity-50"
                            >
                              {isAddingNote ? 'Adding…' : 'Save'}
                            </button>
                          </form>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {/* Actions */}
                  <div className="mt-4 pt-4 border-t border-border flex flex-wrap gap-2">
                    {(() => {
                      const applyUrl =
                        trustReport?.apply_link_final_url ||
                        parsedJob?.apply_url ||
                        parsedJob?.job_url;
                      const isHttp = applyUrl && /^https?:\/\//i.test(applyUrl);
                      return isHttp ? (
                        <a
                          href={applyUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 flex items-center gap-2"
                        >
                          <ExternalLink className="h-4 w-4" />
                          Apply Now
                        </a>
                      ) : null;
                    })()}
                    {!trackedApplicationId && (
                      <button
                        onClick={handleStartTracking}
                        disabled={isTracking}
                        className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                      >
                        {isTracking ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Starting...
                          </>
                        ) : (
                          'Start Tracking'
                        )}
                      </button>
                    )}
                    {trackedApplicationId && (
                      <Link
                        href={`/apply/history?application=${trackedApplicationId}`}
                        className="rounded-lg bg-green-500/20 text-green-500 px-3 py-2 text-sm font-medium hover:bg-green-500/30 flex items-center gap-2"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        View Application
                      </Link>
                    )}
                    <button
                      onClick={() => {
                        if (applyPack.tailored_summary) {
                          navigator.clipboard.writeText(applyPack.tailored_summary);
                        }
                      }}
                      className="rounded-lg border border-border bg-background px-3 py-2 text-sm hover:bg-muted"
                    >
                      Copy Summary
                    </button>
                    {applyPack.cover_note && (
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(applyPack.cover_note || '');
                        }}
                        className="rounded-lg border border-border bg-background px-3 py-2 text-sm hover:bg-muted"
                      >
                        Copy Cover Letter
                      </button>
                    )}
                    <button
                      onClick={async () => {
                        if (parsedJob) {
                          try {
                            const { exportApplyPackDocx } = await import('@/lib/apply-api');
                            const blob = await exportApplyPackDocx(applyPack.apply_pack_id, 'resume');
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = 'tailored_resume.docx';
                            document.body.appendChild(a);
                            a.click();
                            window.URL.revokeObjectURL(url);
                            document.body.removeChild(a);
                            trackDocxDownloaded(applyPack.apply_pack_id, 'resume');
                          } catch (err) {
                            alert(err instanceof Error ? err.message : 'DOCX export limit reached. Upgrade for more exports.');
                          }
                        }
                      }}
                      className="rounded-lg border border-border bg-background px-3 py-2 text-sm hover:bg-muted"
                    >
                      Download Resume DOCX
                    </button>
                    {applyPack.cover_note && (
                      <button
                        onClick={async () => {
                          if (parsedJob) {
                            try {
                              const { exportApplyPackDocx } = await import('@/lib/apply-api');
                              const blob = await exportApplyPackDocx(applyPack.apply_pack_id, 'cover');
                              const url = window.URL.createObjectURL(blob);
                              const a = document.createElement('a');
                              a.href = url;
                              a.download = 'cover_letter.docx';
                              document.body.appendChild(a);
                              a.click();
                              window.URL.revokeObjectURL(url);
                              document.body.removeChild(a);
                              trackDocxDownloaded(applyPack.apply_pack_id, 'cover');
                            } catch (err) {
                              alert(err instanceof Error ? err.message : 'DOCX export limit reached. Upgrade for more exports.');
                            }
                          }
                        }}
                        className="rounded-lg border border-border bg-background px-3 py-2 text-sm hover:bg-muted"
                      >
                        Download Cover Letter DOCX
                      </button>
                    )}
                    <button
                      onClick={async () => {
                        if (parsedJob) {
                          try {
                            const { exportApplyPackDocx } = await import('@/lib/apply-api');
                            const blob = await exportApplyPackDocx(applyPack.apply_pack_id, 'combined');
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `apply_pack_${applyPack.apply_pack_id.slice(0, 8)}.zip`;
                            document.body.appendChild(a);
                            a.click();
                            window.URL.revokeObjectURL(url);
                            document.body.removeChild(a);
                            trackDocxDownloaded(applyPack.apply_pack_id, 'combined');
                          } catch (err) {
                            alert(err instanceof Error ? err.message : 'DOCX export limit reached. Upgrade for more exports.');
                          }
                        }
                      }}
                      className="rounded-lg border border-border bg-background px-3 py-2 text-sm hover:bg-muted"
                    >
                      Download Apply Pack (ZIP)
                    </button>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-border bg-card p-6">
                  <h2 className="text-lg font-semibold mb-4">Apply Pack</h2>
                  <p className="text-sm text-muted-foreground">
                    Parse a job and generate an Apply Pack to see tailored content.
                  </p>
                </div>
              )}

            </div>
          </div>
        </div>
      </main>
      
      <Footer />
    </>
  );
}
