/**
 * API client for Apply Workspace endpoints.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// Get or create user ID (stored in localStorage for anonymous users)
function getUserId(): string {
  if (typeof window === 'undefined') return '';
  
  let userId = localStorage.getItem('jobscout_user_id');
  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem('jobscout_user_id', userId);
  }
  return userId;
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const userId = getUserId();
  
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': userId,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
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

export async function parseJob(jobUrl?: string, jobText?: string): Promise<ParsedJob> {
  return apiRequest<ParsedJob>('/apply/job/parse', {
    method: 'POST',
    body: JSON.stringify({
      job_url: jobUrl || undefined,
      job_text: jobText || undefined,
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
}

export async function generateTrustReport(jobTargetId: string): Promise<TrustReport> {
  return apiRequest<TrustReport>(`/apply/job/${jobTargetId}/trust`, {
    method: 'POST',
  });
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
  plan: 'free' | 'paid';
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
  };
}

export async function getQuota(): Promise<Quota> {
  return apiRequest<Quota>('/apply/quota');
}

export async function exportApplyPackDocx(applyPackId: string, format: 'resume' | 'cover' | 'combined' = 'combined'): Promise<Blob> {
  const userId = getUserId();
  const response = await fetch(`${API_URL}/apply/pack/${applyPackId}/export?format=${format}`, {
    headers: {
      'X-User-ID': userId,
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
  status: 'applied' | 'interview' | 'offer' | 'rejected' | 'withdrawn';
  title?: string;
  company?: string;
  job_url?: string;
  applied_at?: string;
  notes?: string;
  reminder_at?: string;
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
  updates: { status?: string; notes?: string; reminder_at?: string }
): Promise<Application> {
  return apiRequest<Application>(`/apply/application/${applicationId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}
