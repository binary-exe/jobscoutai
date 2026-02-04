import { supabase } from '@/lib/supabase';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

async function getAuthHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const auth = await getAuthHeader();
  const res = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...auth,
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || 'Request failed');
  }
  return res.json();
}

export interface Profile {
  user_id: string;
  email?: string | null;
  profile: any | null;
  resume_versions: any[];
}

export async function getProfile(): Promise<Profile> {
  return apiRequest<Profile>('/profile', { cache: 'no-store' });
}

export async function upsertProfile(payload: Record<string, unknown>): Promise<{ profile: any }> {
  return apiRequest<{ profile: any }>('/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function createResumeFromText(input: { resume_text: string; proof_points?: string; use_ai?: boolean }) {
  return apiRequest('/profile/resume/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...input, use_ai: input.use_ai ?? true }),
  });
}

export async function uploadResume(file: File) {
  const auth = await getAuthHeader();
  const form = new FormData();
  form.append('file', file);

  const res = await fetch(`${API_URL}/profile/resume/upload`, {
    method: 'POST',
    headers: {
      ...auth,
    },
    body: form,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || 'Upload failed');
  }
  return res.json();
}

export async function setPrimaryResume(resume_id: string) {
  return apiRequest('/profile/resume/primary', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_id }),
  });
}

export async function getResume(resume_id: string) {
  return apiRequest<{ resume: any }>(`/profile/resume/${resume_id}`, { cache: 'no-store' });
}
