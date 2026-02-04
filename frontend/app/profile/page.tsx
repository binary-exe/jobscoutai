'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { supabase } from '@/lib/supabase';
import { createResumeFromText, getProfile, setPrimaryResume, upsertProfile, uploadResume } from '@/lib/profile-api';
import { trackProfileCompleted, trackEvent } from '@/lib/analytics';

function csvToList(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

function listToCsv(list: string[] | undefined | null): string {
  return (list || []).join(', ');
}

export default function ProfilePage() {
  const [sessionEmail, setSessionEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);

  const [headline, setHeadline] = useState('');
  const [location, setLocation] = useState('');
  const [desiredRolesCsv, setDesiredRolesCsv] = useState('');
  const [skillsCsv, setSkillsCsv] = useState('');
  const [interestsCsv, setInterestsCsv] = useState('');
  const [linksJson, setLinksJson] = useState('{"linkedin":"","github":"","website":""}');

  const [resumeText, setResumeText] = useState('');
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const primaryResumeId = useMemo(() => data?.profile?.primary_resume_id || null, [data]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const { data: sess } = await supabase.auth.getSession();
      const email = sess.session?.user?.email || null;
      if (!cancelled) setSessionEmail(email);
      if (!email) {
        if (!cancelled) setLoading(false);
        return;
      }

      try {
        const profile = await getProfile();
        if (cancelled) return;
        setData(profile);

        const p = profile.profile || {};
        setHeadline(p.headline || '');
        setLocation(p.location || '');
        setDesiredRolesCsv(listToCsv(p.desired_roles));
        setSkillsCsv(listToCsv(p.skills));
        setInterestsCsv(listToCsv(p.interests));
        setLinksJson(JSON.stringify(p.links || { linkedin: '', github: '', website: '' }, null, 2));
      } catch (err: any) {
        if (!cancelled) setError(err?.message || 'Failed to load profile');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleSaveProfile = async () => {
    setError(null);
    setSaving(true);
    try {
      const links = JSON.parse(linksJson || '{}');
      await upsertProfile({
        headline,
        location,
        desired_roles: csvToList(desiredRolesCsv),
        skills: csvToList(skillsCsv),
        interests: csvToList(interestsCsv),
        links,
      });
      const refreshed = await getProfile();
      setData(refreshed);
      const hasResume = !!(refreshed?.profile?.primary_resume_id || (refreshed?.resume_versions?.length ?? 0) > 0);
      trackProfileCompleted(hasResume);
      trackEvent('profile_saved', { has_resume: hasResume });
    } catch (err: any) {
      setError(err?.message || 'Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async (file: File) => {
    setError(null);
    setUploading(true);
    try {
      await uploadResume(file);
      const refreshed = await getProfile();
      setData(refreshed);
      trackEvent('resume_uploaded', {});
    } catch (err: any) {
      setError(err?.message || 'Failed to upload resume');
    } finally {
      setUploading(false);
    }
  };

  const handlePasteResume = async () => {
    setError(null);
    setUploading(true);
    try {
      if (!resumeText.trim()) throw new Error('Paste your resume text first');
      await createResumeFromText({ resume_text: resumeText, use_ai: true });
      setResumeText('');
      const refreshed = await getProfile();
      setData(refreshed);
      trackEvent('resume_pasted', { use_ai: true });
    } catch (err: any) {
      setError(err?.message || 'Failed to save resume');
    } finally {
      setUploading(false);
    }
  };

  const handleSetPrimary = async (resumeId: string) => {
    setError(null);
    try {
      await setPrimaryResume(resumeId);
      const refreshed = await getProfile();
      setData(refreshed);
    } catch (err: any) {
      setError(err?.message || 'Failed to set primary resume');
    }
  };

  return (
    <>
      <Header />
      <main className="flex-1">
        <section className="py-10">
          <div className="container mx-auto max-w-4xl px-4">
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
              <Link href="/apply" className="text-sm text-muted-foreground hover:text-foreground">
                Go to Apply Workspace
              </Link>
            </div>

            {!sessionEmail ? (
              <div className="mt-6 rounded-xl border border-border bg-card p-6">
                <p className="text-sm text-muted-foreground">
                  Login to create your profile and unlock personalized ranking.
                </p>
                <Link
                  href="/login?next=/profile"
                  className="mt-4 inline-flex rounded-lg bg-foreground px-3 py-2 text-sm font-medium text-background"
                >
                  Login
                </Link>
              </div>
            ) : null}

            {error ? (
              <div className="mt-6 rounded-xl border border-border bg-card p-4">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            ) : null}

            {loading ? (
              <div className="mt-6 h-40 rounded-xl bg-muted animate-pulse" />
            ) : sessionEmail ? (
              <div className="mt-6 grid gap-6 lg:grid-cols-2">
                <div className="rounded-xl border border-border bg-card p-6 space-y-4">
                  <div>
                    <label className="block text-sm font-medium">Headline</label>
                    <input
                      className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      value={headline}
                      onChange={(e) => setHeadline(e.target.value)}
                      placeholder="e.g., Senior Backend Engineer (Python/FastAPI)"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium">Location</label>
                    <input
                      className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      placeholder="e.g., London, UK"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium">Desired roles (comma-separated)</label>
                    <input
                      className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      value={desiredRolesCsv}
                      onChange={(e) => setDesiredRolesCsv(e.target.value)}
                      placeholder="Backend Engineer, Platform Engineer, DevOps"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium">Skills (comma-separated)</label>
                    <textarea
                      className="mt-1 w-full min-h-[90px] rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      value={skillsCsv}
                      onChange={(e) => setSkillsCsv(e.target.value)}
                      placeholder="Python, FastAPI, Postgres, AWS, Docker, Kubernetes"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium">Interests (comma-separated)</label>
                    <input
                      className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      value={interestsCsv}
                      onChange={(e) => setInterestsCsv(e.target.value)}
                      placeholder="Developer tools, AI, FinTech"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium">Links (JSON)</label>
                    <textarea
                      className="mt-1 w-full min-h-[120px] rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-primary"
                      value={linksJson}
                      onChange={(e) => setLinksJson(e.target.value)}
                    />
                  </div>
                  <button
                    onClick={handleSaveProfile}
                    disabled={saving}
                    className="w-full rounded-lg bg-foreground px-3 py-2 text-sm font-medium text-background disabled:opacity-60"
                    type="button"
                  >
                    {saving ? 'Saving…' : 'Save profile'}
                  </button>
                </div>

                <div className="rounded-xl border border-border bg-card p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-medium">Resume versions</h2>
                    <span className="text-xs text-muted-foreground">
                      Primary used for personalization
                    </span>
                  </div>

                  <div className="space-y-2">
                    {(data?.resume_versions || []).length ? (
                      (data.resume_versions as any[]).map((r) => {
                        const id = String(r.resume_id);
                        const created = r.created_at ? new Date(r.created_at).toLocaleString() : '';
                        const isPrimary = primaryResumeId && String(primaryResumeId) === id;
                        return (
                          <div key={id} className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2">
                            <div className="min-w-0">
                              <div className="text-sm truncate">{id}</div>
                              <div className="text-xs text-muted-foreground">{created}</div>
                            </div>
                            <button
                              onClick={() => handleSetPrimary(id)}
                              className="ml-3 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted"
                              type="button"
                            >
                              {isPrimary ? 'Primary' : 'Set primary'}
                            </button>
                          </div>
                        );
                      })
                    ) : (
                      <p className="text-sm text-muted-foreground">No resumes saved yet.</p>
                    )}
                  </div>

                  <div className="pt-2 border-t border-border">
                    <label className="block text-sm font-medium">Upload resume (PDF/DOCX)</label>
                    <input
                      type="file"
                      accept=".pdf,.doc,.docx"
                      disabled={uploading}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUpload(file);
                      }}
                      className="mt-2 block w-full text-sm"
                    />
                    <p className="mt-2 text-xs text-muted-foreground">
                      Upload creates a new saved resume version.
                    </p>
                  </div>

                  <div className="pt-2 border-t border-border">
                    <label className="block text-sm font-medium">Or paste resume text</label>
                    <textarea
                      value={resumeText}
                      onChange={(e) => setResumeText(e.target.value)}
                      className="mt-1 w-full min-h-[120px] rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      placeholder="Paste resume text here…"
                    />
                    <button
                      onClick={handlePasteResume}
                      disabled={uploading}
                      className="mt-2 w-full rounded-lg bg-foreground px-3 py-2 text-sm font-medium text-background disabled:opacity-60"
                      type="button"
                    >
                      {uploading ? 'Saving…' : 'Save resume version'}
                    </button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}

