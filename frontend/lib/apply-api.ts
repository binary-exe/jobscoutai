/**
 * API client for Apply Workspace endpoints.
 * 
 * All Apply Workspace endpoints require authentication (Supabase JWT).
 * There is no anonymous access - users must be logged in.
 */

import { supabase } from '@/lib/supabase';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function formatApiError(status: number, detail?: string | unknown): string {
  let raw: string;
  if (typeof detail === 'string') {
    raw = detail.trim();
  } else if (Array.isArray(detail) && detail.length > 0) {
    raw = detail.map((d: { msg?: string }) => d?.msg || JSON.stringify(d)).join('; ');
  } else if (detail != null && typeof detail === 'object') {
    raw = JSON.stringify(detail);
  } else {
    raw = '';
  }
  const msg = raw.toLowerCase();
  const providerOutage =
    msg.includes('insufficient_quota') ||
    msg.includes('error code: 429') ||
    msg.includes('rate limit') ||
    msg.includes('temporarily unavailable') ||
    msg.includes('billing') ||
    msg.includes('credit balance');

  if ((status === 503 && providerOutage) || providerOutage) {
    return 'AI is temporarily unavailable due to provider quota/capacity. This is not your JobiQueue plan usage. Please try again shortly.';
  }

  return raw || `HTTP ${status}`;
}

/**
 * Get the current auth token. Returns null if not authenticated.
 */
async function getAuthToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token || null;
}

/**
 * Make an authenticated API request.
 * Throws an error if not authenticated or if the request fails.
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getAuthToken();
  
  if (!token) {
    throw new Error('Authentication required. Please log in to use Apply Workspace.');
  }
  
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(formatApiError(response.status, error.detail));
  }

  return response.json();
}

export interface ParsedJob {
  job_target_id: string;
  title?: string;
  company?: string;
  location?: string;
  remote_type?: string;
  employment_type?: string[];
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  description_text?: string;
  job_url?: string;
  apply_url?: string;
  extracted: boolean;
  extraction_method?: string;
}

export async function uploadResume(file: File): Promise<{ resume_text: string; filename: string; size: number }> {
  const token = await getAuthToken();
  
  if (!token) {
    throw new Error('Authentication required. Please log in to upload a resume.');
  }
  
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(`${API_URL}/apply/resume/upload`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function parseJob(jobUrl?: string, jobText?: string): Promise<ParsedJob> {
  return apiRequest<ParsedJob>('/apply/job/parse', {
    method: 'POST',
    body: JSON.stringify({
      job_url: jobUrl || undefined,
      job_text: jobText || undefined,
    }),
  });
}

/** Get a job target by ID (e.g. from extension save). Returns ParsedJob shape for Apply page. */
export async function getJobTarget(jobTargetId: string): Promise<ParsedJob> {
  return apiRequest<ParsedJob>(`/apply/job/target/${jobTargetId}`);
}

export async function importJobFromJobScout(job: {
  job_id?: string;
  job_url?: string;
  apply_url?: string;
  title: string;
  company: string;
  location_raw?: string;
  remote_type?: string;
  employment_types?: string[];
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  description_text?: string;
  company_website?: string;
  linkedin_url?: string;
  ai_company_summary?: string;
  ai_summary?: string;
  ai_requirements?: string;
  ai_tech_stack?: string;
}): Promise<ParsedJob> {
  return apiRequest<ParsedJob>('/apply/job/import', {
    method: 'POST',
    body: JSON.stringify({
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
    }),
  });
}

export async function updateJobTarget(
  jobTargetId: string,
  updates: Partial<ParsedJob>
): Promise<ParsedJob> {
  return apiRequest<ParsedJob>(`/apply/job/${jobTargetId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export interface TrustReport {
  trust_report_id: string;
  scam_risk: 'low' | 'medium' | 'high';
  scam_reasons: string[];
  ghost_likelihood: 'low' | 'medium' | 'high';
  ghost_reasons: string[];
  staleness_score?: number;
  staleness_reasons?: string[];
  scam_score?: number;
  ghost_score?: number;
  apply_link_status?: string;
  apply_link_final_url?: string;
  apply_link_redirects?: number;
  apply_link_cached?: boolean;
  apply_link_warnings?: string[];
  domain_consistency_reasons?: string[];
  trust_score?: number;
  trust_score_raw?: number;
  trust_score_after_community?: number;
  verified_at?: string;
  confidence?: {
    scam?: number;
    ghost?: number;
    staleness?: number;
    domain?: number;
    link?: number;
    overall?: number;
  };
  community?: {
    reports_total: number;
    accurate_total: number;
    inaccurate_total: number;
    reports_scam: number;
    reports_ghost: number;
    reports_expired: number;
    [k: string]: number;
  };
  community_reasons?: string[];
  next_steps?: string[];
}

export async function generateTrustReport(
  jobTargetId: string,
  opts: { force?: boolean; refresh_apply_link?: boolean } = {}
): Promise<TrustReport> {
  const qs = new URLSearchParams();
  if (opts.force) qs.set('force', 'true');
  if (opts.refresh_apply_link) qs.set('refresh_apply_link', 'true');
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return apiRequest<TrustReport>(`/apply/job/${jobTargetId}/trust${suffix}`, {
    method: 'POST',
  });
}

export async function submitTrustFeedback(
  jobTargetId: string,
  feedback: {
    feedback_kind: 'report' | 'accuracy';
    dimension?: 'overall' | 'scam' | 'ghost' | 'staleness' | 'link';
    value?: string;
    comment?: string;
  }
): Promise<{ ok: boolean; community: Record<string, number> }> {
  return apiRequest<{ ok: boolean; community: Record<string, number> }>(
    `/apply/job/${jobTargetId}/trust/feedback`,
    {
      method: 'POST',
      body: JSON.stringify(feedback),
    }
  );
}

export interface ApplyPack {
  apply_pack_id: string;
  tailored_summary?: string;
  tailored_bullets?: Array<{ text: string; match_score?: number }>;
  cover_note?: string;
  ats_checklist?: {
    keyword_coverage: number;
    missing_skills: string[];
    matched_skills: string[];
  };
  keyword_coverage?: number;
}

export async function generateApplyPack(
  resumeText: string,
  jobUrl?: string,
  jobText?: string,
  useAi: boolean = true
): Promise<ApplyPack> {
  return apiRequest<ApplyPack>('/apply/pack/generate', {
    method: 'POST',
    body: JSON.stringify({
      resume_text: resumeText,
      job_url: jobUrl || undefined,
      job_text: jobText || undefined,
      use_ai: useAi,
    }),
  });
}

export interface ApplyPackHistory {
  apply_pack_id: string;
  title?: string;
  company?: string;
  job_url?: string;
  created_at: string;
}

export async function getHistory(): Promise<{ packs: ApplyPackHistory[]; total: number }> {
  return apiRequest<{ packs: ApplyPackHistory[]; total: number }>('/apply/history');
}

export interface Quota {
  plan: string;
  subscription_status?: string;
  apply_packs: {
    allowed: boolean;
    remaining?: number;
    limit?: number;
    used?: number;
  };
  docx_export: {
    allowed: boolean;
    remaining?: number;
    limit?: number;
    used?: number;
  };
  tracking: {
    allowed: boolean;
    remaining?: number;
    limit?: number;
    used?: number;
  };
  credits_balance?: number;
  credits_expires_soon?: boolean;
  credits_enabled?: boolean;
  packs_equivalent?: number;
  premium_ai_enabled?: boolean;
  premium_ai_configured?: boolean;
  apply_pack_review_enabled?: boolean;
}

export async function getQuota(): Promise<Quota> {
  return apiRequest<Quota>('/apply/quota');
}

export async function exportApplyPackDocx(applyPackId: string, format: 'resume' | 'cover' | 'combined' = 'combined'): Promise<Blob> {
  const token = await getAuthToken();
  
  if (!token) {
    throw new Error('Authentication required. Please log in to export documents.');
  }
  
  const response = await fetch(`${API_URL}/apply/pack/${applyPackId}/export?format=${format}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.blob();
}

export interface Application {
  application_id: string;
  apply_pack_id?: string | null;
  job_target_id?: string | null;
  status: 'applied' | 'interview' | 'offer' | 'rejected' | 'withdrawn';
  title?: string;
  company?: string;
  job_url?: string;
  applied_at?: string;
  interview_at?: string;
  offer_at?: string;
  rejected_at?: string;
  notes?: string;
  reminder_at?: string;
  contact_email?: string | null;
  contact_linkedin_url?: string | null;
  contact_phone?: string | null;
}

export async function createApplication(
  applyPackId?: string,
  jobTargetId?: string,
  status: string = 'applied',
  notes?: string,
  reminderAt?: string
): Promise<Application> {
  return apiRequest<Application>('/apply/application', {
    method: 'POST',
    body: JSON.stringify({
      apply_pack_id: applyPackId,
      job_target_id: jobTargetId,
      status,
      notes,
      reminder_at: reminderAt,
    }),
  });
}

export async function getApplications(status?: string): Promise<{ applications: Application[]; total: number }> {
  const params = status ? `?status=${status}` : '';
  return apiRequest<{ applications: Application[]; total: number }>(`/apply/application${params}`);
}

export async function updateApplication(
  applicationId: string,
  updates: {
    status?: string;
    notes?: string;
    reminder_at?: string | null;
    contact_email?: string | null;
    contact_linkedin_url?: string | null;
    contact_phone?: string | null;
  }
): Promise<Application> {
  return apiRequest<Application>(`/apply/application/${applicationId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export type ApplicationInsights = {
  by_type: Record<string, number>;
  reason_counts: Record<string, number>;
};

export async function getApplicationInsights(): Promise<ApplicationInsights> {
  return apiRequest<ApplicationInsights>('/apply/insights');
}

// ==================== Premium AI (optional) ====================

export type InterviewCoachResult = {
  cached: boolean;
  fallback?: boolean;
  cache_key: string;
  tokens_used?: number;
  /** True when KB context was used; false when none; undefined for cached (unknown) */
  kb_context_used?: boolean | null;
  result: {
    questions?: Array<{
      type?: string;
      question?: string;
      why_they_ask?: string;
      what_good_looks_like?: string[];
      red_flags?: string[];
      difficulty?: string;
      suggested_answer_outline?: string[];
      study_focus?: string[];
    }>;
    rubric?: Array<{ dimension?: string; how_to_score?: string }>;
    suggested_stories?: Array<{ story_prompt?: string; STAR_outline?: Record<string, string> }>;
    recommendations?: string[];
    study_materials?: Array<{
      topic?: string;
      why_it_matters?: string;
      priority?: string;
      resources?: string[];
      practice_tasks?: string[];
    }>;
    preparation_plan?: Array<{
      label?: string;
      objective?: string;
      actions?: string[];
    }>;
    gap_analysis?: {
      matched?: string[];
      missing?: string[];
      notes?: string[];
    };
    next_steps?: string[];
    [k: string]: unknown;
  };
};

export async function generateInterviewCoach(opts: {
  resume_text: string;
  job_target_id?: string;
  job_text?: string;
}): Promise<InterviewCoachResult> {
  return apiRequest<InterviewCoachResult>('/apply/ai/interview-coach', {
    method: 'POST',
    body: JSON.stringify(opts),
  });
}

export type PremiumTemplateResult = {
  cached: boolean;
  cache_key: string;
  tokens_used?: number;
  result: {
    template_id?: string;
    tone?: string;
    content?: string;
    [k: string]: unknown;
  };
};

export async function generatePremiumTemplate(opts: {
  template_id: string;
  tone?: string;
  resume_text: string;
  job_target_id?: string;
  job_text?: string;
}): Promise<PremiumTemplateResult> {
  return apiRequest<PremiumTemplateResult>('/apply/ai/template', {
    method: 'POST',
    body: JSON.stringify(opts),
  });
}

export interface ApplicationFeedback {
  feedback_id: string;
  feedback_type: 'rejection' | 'shortlisted' | 'offer' | 'no_response' | 'withdrawn';
  raw_text?: string;
  parsed_json?: {
    decision?: string;
    reason_categories?: string[];
    signals?: string[];
  };
  created_at?: string;
}

export async function createApplicationFeedback(
  applicationId: string,
  feedback: {
    feedback_type: string;
    raw_text?: string;
    parsed_json?: Record<string, unknown>;
  }
): Promise<ApplicationFeedback> {
  return apiRequest<ApplicationFeedback>(`/apply/application/${applicationId}/feedback`, {
    method: 'POST',
    body: JSON.stringify(feedback),
  });
}

export async function getApplicationFeedback(applicationId: string): Promise<{ feedback: ApplicationFeedback[] }> {
  return apiRequest<{ feedback: ApplicationFeedback[] }>(`/apply/application/${applicationId}/feedback`);
}

/**
 * Check if user is authenticated. Useful for auth guards.
 */
export async function isAuthenticated(): Promise<boolean> {
  const token = await getAuthToken();
  return !!token;
}

// --- Second Brain (KB) RAG ---

export interface KbIndexPayload {
  source_type: string;
  source_table?: string;
  source_id?: string;
  title?: string;
  metadata?: Record<string, unknown>;
  /** Required for manual index; omit when source_table + source_id are provided (index from artifact) */
  text?: string;
}

export interface KbIndexResponse {
  document_id: string;
  chunks_indexed: number;
}

export interface KbCitation {
  chunk_id: string;
  document_id: string;
  source_type: string;
  source_id: string;
  page: number | null;
  score: number;
  snippet: string;
}

export interface KbQueryPayload {
  question: string;
  source_type?: string;
  source_table?: string;
  source_id?: string;
  max_chunks?: number;
}

export interface KbQueryResponse {
  answer: string;
  citations: KbCitation[];
}

export async function indexKnowledgeDocument(payload: KbIndexPayload): Promise<KbIndexResponse> {
  return apiRequest<KbIndexResponse>('/kb/index', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function queryKnowledge(payload: KbQueryPayload): Promise<KbQueryResponse> {
  return apiRequest<KbQueryResponse>('/kb/query', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
