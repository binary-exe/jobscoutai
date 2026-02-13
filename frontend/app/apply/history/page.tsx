'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Clock, FileText, ExternalLink, Copy, Download, CheckCircle2, XCircle, Calendar, Briefcase, MessageSquare, Plus, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { getHistory, exportApplyPackDocx, getApplications, getApplicationFeedback, createApplicationFeedback, updateApplication, createApplication, getApplicationInsights, type Application, type ApplyPackHistory, type ApplicationFeedback, type ApplicationInsights } from '@/lib/apply-api';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';

export default function HistoryPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [authChecked, setAuthChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [packs, setPacks] = useState<ApplyPackHistory[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [activeTab, setActiveTab] = useState<'packs' | 'applications'>('packs');
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<string | null>(null);
  const [selectedApplication, setSelectedApplication] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<string, ApplicationFeedback[]>>({});
  const [showFeedbackForm, setShowFeedbackForm] = useState<string | null>(null);
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackType, setFeedbackType] = useState<'rejection' | 'shortlisted' | 'offer' | 'no_response' | 'withdrawn'>('rejection');
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [reasonCategories, setReasonCategories] = useState<string[]>([]);
  const [signals, setSignals] = useState<string[]>([]);
  const [notesDraft, setNotesDraft] = useState<Record<string, string>>({});
  const [savingNotes, setSavingNotes] = useState<string | null>(null);
  const [contactDraft, setContactDraft] = useState<Record<string, { email: string; linkedin: string; phone: string }>>({});
  const [savingContact, setSavingContact] = useState<string | null>(null);
  const [insights, setInsights] = useState<ApplicationInsights | null>(null);

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
      } else {
        // Redirect to login with return URL
        router.replace(`/login?next=${encodeURIComponent('/apply/history')}`);
        return;
      }
      setAuthChecked(true);
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    if (!authChecked || !isAuthenticated) return;
    
    fetchData();
    // Check if we should show a specific application
    const applicationId = searchParams?.get('application');
    if (applicationId) {
      setActiveTab('applications');
      setSelectedApplication(applicationId);
      loadFeedback(applicationId);
    }
  }, [searchParams, authChecked, isAuthenticated]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [packsData, appsData, insightsData] = await Promise.all([
        getHistory().catch(() => ({ packs: [], total: 0 })),
        getApplications().catch(() => ({ applications: [], total: 0 })),
        getApplicationInsights().catch(() => ({ by_type: {}, reason_counts: {} })),
      ]);
      setPacks(packsData.packs || []);
      setApplications(appsData.applications || []);
      setInsights(insightsData);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (packId: string, format: 'resume' | 'cover' | 'combined' = 'combined') => {
    setExporting(packId);
    try {
      const blob = await exportApplyPackDocx(packId, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `apply_pack_${packId.slice(0, 8)}.docx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to export');
    } finally {
      setExporting(null);
    }
  };

  const loadFeedback = async (applicationId: string) => {
    try {
      const result = await getApplicationFeedback(applicationId);
      setFeedback(prev => ({ ...prev, [applicationId]: result.feedback }));
    } catch (err) {
      console.error('Failed to load feedback:', err);
    }
  };

  const handleSubmitFeedback = async (applicationId: string) => {
    if (!feedbackText.trim()) {
      alert('Please enter feedback text');
      return;
    }

    setIsSubmittingFeedback(true);
    try {
      await createApplicationFeedback(applicationId, {
        feedback_type: feedbackType,
        raw_text: feedbackText,
        parsed_json: {
          decision: feedbackType,
          reason_categories: reasonCategories,
          signals,
        },
      });
      setFeedbackText('');
      setReasonCategories([]);
      setSignals([]);
      setShowFeedbackForm(null);
      await loadFeedback(applicationId);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to submit feedback');
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'offer':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'rejected':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'interview':
        return <Calendar className="h-4 w-4 text-blue-500" />;
      default:
        return <Briefcase className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const toggle = (arr: string[], value: string) => {
    return arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value];
  };

  const REASON_OPTIONS = [
    'skills_gap',
    'seniority',
    'location',
    'compensation',
    'visa',
    'domain_experience',
    'timing',
    'portfolio',
    'other',
  ];

  const SIGNAL_OPTIONS = [
    'strong_relevant_experience',
    'strong_tech_stack_match',
    'strong_metrics',
    'leadership',
    'communication',
    'culture_fit',
    'fast_response',
    'referral',
  ];

  const toLocalDateTimeInput = (iso?: string) => {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      const pad = (n: number) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch {
      return '';
    }
  };

  const downloadIcs = (title: string, startsAtIso: string) => {
    try {
      const dt = new Date(startsAtIso);
      const toIcsTs = (d: Date) => {
        const pad = (n: number) => String(n).padStart(2, '0');
        return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`;
      };

      const uid = `jobscout-${Math.random().toString(36).slice(2)}@jobscout`;
      const now = toIcsTs(new Date());
      const start = toIcsTs(dt);
      const end = toIcsTs(new Date(dt.getTime() + 30 * 60 * 1000)); // +30m default

      const ics = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//JobScoutAI//Apply Tracker//EN',
        'CALSCALE:GREGORIAN',
        'BEGIN:VEVENT',
        `UID:${uid}`,
        `DTSTAMP:${now}`,
        `DTSTART:${start}`,
        `DTEND:${end}`,
        `SUMMARY:${title.replace(/\n/g, ' ')}`,
        'END:VEVENT',
        'END:VCALENDAR',
      ].join('\r\n');

      const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title.slice(0, 40).replace(/[^a-z0-9-_ ]/gi, '').trim() || 'reminder'}.ics`;
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch {
      alert('Failed to export calendar invite');
    }
  };

  // Show loading while checking auth
  if (!authChecked) {
    return (
      <>
        <Header />
        <main className="flex-1">
          <div className="container mx-auto max-w-5xl px-4 py-12">
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
        <div className="container mx-auto max-w-5xl px-4 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold tracking-tight mb-2">Application History</h1>
            <p className="text-muted-foreground mb-4">
              View and manage your saved apply packs and tracked applications.
            </p>
            
            {/* Tabs */}
            <div className="flex gap-2 border-b border-border">
              <button
                onClick={() => setActiveTab('packs')}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'packs'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                Apply Packs ({packs.length})
              </button>
              <button
                onClick={() => setActiveTab('applications')}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'applications'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                Tracked Applications ({applications.length})
              </button>
            </div>
          </div>

          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="rounded-xl border border-border bg-card p-6 animate-pulse">
                  <div className="h-4 bg-muted w-1/3 mb-2"></div>
                  <div className="h-3 bg-muted w-1/2"></div>
                </div>
              ))}
            </div>
          ) : activeTab === 'packs' ? (
            packs.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border bg-card p-16 text-center">
                <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="font-semibold mb-2">No apply packs yet</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Generate your first apply pack to get started.
                </p>
                <Link
                  href="/apply"
                  className="inline-block rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Create Apply Pack
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {packs.map((pack) => (
                  <div key={pack.apply_pack_id} className="rounded-xl border border-border bg-card p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="font-semibold mb-1">
                          {pack.title || 'Untitled Job'}
                        </h3>
                        {pack.company && (
                          <p className="text-sm text-muted-foreground mb-2">{pack.company}</p>
                        )}
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {new Date(pack.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {pack.job_url && (
                          <a
                            href={pack.job_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-2 rounded-lg border border-border hover:bg-muted"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        )}
                        <button
                          onClick={() => handleExport(pack.apply_pack_id, 'combined')}
                          disabled={exporting === pack.apply_pack_id}
                          className="p-2 rounded-lg border border-border hover:bg-muted disabled:opacity-50"
                          title="Download DOCX"
                        >
                          {exporting === pack.apply_pack_id ? (
                            <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <Download className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )
          ) : activeTab === 'applications' && applications.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-card p-16 text-center">
              <Briefcase className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="font-semibold mb-2">No tracked applications yet</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Start tracking your applications to stay organized. Your tracker is a Kanban board (Saved → Applied → Interview → Offer → Rejected).
              </p>
              <Link
                href="/apply"
                className="inline-block rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                Create Apply Pack
              </Link>
            </div>
          ) : activeTab === 'applications' ? (
            <div className="space-y-4">
              {/* Feedback-driven insights (recommendation cards) */}
              {insights && (Object.keys(insights.by_type ?? {}).length > 0 || Object.keys(insights.reason_counts ?? {}).length > 0) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.keys(insights.by_type ?? {}).length > 0 && (
                    <div className="rounded-xl border border-border bg-card p-4">
                      <h3 className="text-sm font-semibold mb-2">Outcomes</h3>
                      <p className="text-xs text-muted-foreground mb-2">Feedback you&apos;ve recorded</p>
                      <ul className="space-y-1 text-sm">
                        {Object.entries(insights.by_type).map(([type, count]) => (
                          <li key={type} className="flex justify-between">
                            <span className="capitalize text-muted-foreground">{type.replace(/_/g, ' ')}</span>
                            <span className="font-medium">{count}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {Object.keys(insights.reason_counts ?? {}).length > 0 && (
                    <div className="rounded-xl border border-border bg-card p-4">
                      <h3 className="text-sm font-semibold mb-2">Most common rejection reasons</h3>
                      <p className="text-xs text-muted-foreground mb-2">Use this to focus your prep</p>
                      <ul className="space-y-1 text-sm">
                        {Object.entries(insights.reason_counts)
                          .sort((a, b) => b[1] - a[1])
                          .slice(0, 8)
                          .map(([reason, count]) => (
                            <li key={reason} className="flex justify-between">
                              <span className="capitalize text-muted-foreground">{reason.replace(/_/g, ' ')}</span>
                              <span className="font-medium">{count}</span>
                            </li>
                          ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Kanban board */}
              <div className="text-sm text-muted-foreground">
                Tip: move cards by changing status. Saved items are Apply Packs you haven’t started tracking yet.
              </div>

              {(() => {
                const trackedPackIds = new Set(applications.map((a) => a.apply_pack_id).filter(Boolean) as string[]);
                const saved = packs.filter((p) => !trackedPackIds.has(p.apply_pack_id));
                const byStatus = (s: string) => applications.filter((a) => a.status === s);
                const rejectedLike = applications.filter((a) => a.status === 'rejected' || a.status === 'withdrawn');

                const columns: Array<{
                  key: string;
                  title: string;
                  apps: Application[];
                  packs?: ApplyPackHistory[];
                }> = [
                  { key: 'saved', title: `Saved (${saved.length})`, apps: [], packs: saved },
                  { key: 'applied', title: `Applied (${byStatus('applied').length})`, apps: byStatus('applied') },
                  { key: 'interview', title: `Interview (${byStatus('interview').length})`, apps: byStatus('interview') },
                  { key: 'offer', title: `Offer (${byStatus('offer').length})`, apps: byStatus('offer') },
                  { key: 'rejected', title: `Rejected (${rejectedLike.length})`, apps: rejectedLike },
                ];

                return (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
                    {columns.map((col) => (
                      <div key={col.key} className="rounded-xl border border-border bg-card p-4">
                        <div className="text-sm font-semibold mb-3">{col.title}</div>

                        <div className="space-y-3">
                          {/* Saved packs (not yet tracked) */}
                          {col.key === 'saved' && col.packs?.map((p) => (
                            <div key={p.apply_pack_id} className="rounded-lg border border-border bg-background p-3">
                              <div className="text-sm font-medium">{p.title || 'Untitled Job'}</div>
                              {p.company && <div className="text-xs text-muted-foreground">{p.company}</div>}
                              <div className="mt-2 flex items-center justify-between gap-2">
                                <div className="text-xs text-muted-foreground">
                                  {new Date(p.created_at).toLocaleDateString()}
                                </div>
                                <button
                                  type="button"
                                  onClick={async () => {
                                    try {
                                      await createApplication(p.apply_pack_id, undefined, 'applied');
                                      await fetchData();
                                    } catch (err) {
                                      alert(err instanceof Error ? err.message : 'Failed to start tracking');
                                    }
                                  }}
                                  className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                                >
                                  Track
                                </button>
                              </div>
                            </div>
                          ))}

                          {/* Application cards */}
                          {col.apps.map((app) => (
                            <div key={app.application_id} className="rounded-lg border border-border bg-background p-3">
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <div className="text-sm font-medium truncate">{app.title || 'Untitled Job'}</div>
                                  {app.company && <div className="text-xs text-muted-foreground truncate">{app.company}</div>}
                                </div>
                                {app.job_url && (
                                  <a
                                    href={app.job_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="shrink-0 p-1 rounded border border-border hover:bg-muted"
                                    title="Open job link"
                                  >
                                    <ExternalLink className="h-3.5 w-3.5" />
                                  </a>
                                )}
                              </div>

                              <div className="mt-2 flex items-center justify-between gap-2">
                                <div className="text-xs text-muted-foreground">
                                  {app.applied_at ? `Applied ${new Date(app.applied_at).toLocaleDateString()}` : ''}
                                </div>
                                <select
                                  value={app.status}
                                  onChange={async (e) => {
                                    const next = e.target.value;
                                    try {
                                      await updateApplication(app.application_id, { status: next });
                                      await fetchData();
                                    } catch (err) {
                                      alert(err instanceof Error ? err.message : 'Failed to update status');
                                    }
                                  }}
                                  className="rounded border border-input bg-background px-2 py-1 text-xs"
                                >
                                  <option value="applied">Applied</option>
                                  <option value="interview">Interview</option>
                                  <option value="offer">Offer</option>
                                  <option value="rejected">Rejected</option>
                                  <option value="withdrawn">Withdrawn</option>
                                </select>
                              </div>

                              <div className="mt-2">
                                <label className="block text-[11px] text-muted-foreground mb-1">Reminder</label>
                                <div className="flex items-center gap-2">
                                  <input
                                    type="datetime-local"
                                    defaultValue={toLocalDateTimeInput(app.reminder_at || undefined)}
                                    className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
                                    onBlur={async (e) => {
                                      const v = e.currentTarget.value;
                                      try {
                                        await updateApplication(app.application_id, { reminder_at: v ? new Date(v).toISOString() : null });
                                        await fetchData();
                                      } catch (err) {
                                        alert(err instanceof Error ? err.message : 'Failed to update reminder');
                                      }
                                    }}
                                  />
                                  {app.reminder_at && (
                                    <button
                                      type="button"
                                      onClick={() => downloadIcs(`${app.title || 'Reminder'} — follow up`, app.reminder_at!)}
                                      className="shrink-0 rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                      title="Export to calendar (ICS)"
                                    >
                                      ICS
                                    </button>
                                  )}
                                </div>
                              </div>

                              {/* Notes (recruiter/private notes on this application) */}
                              <div className="mt-2">
                                <label className="block text-[11px] text-muted-foreground mb-1">Notes</label>
                                <textarea
                                  value={notesDraft[app.application_id] ?? app.notes ?? ''}
                                  onChange={(e) => setNotesDraft((prev) => ({ ...prev, [app.application_id]: e.target.value }))}
                                  onBlur={async () => {
                                    const value = notesDraft[app.application_id] ?? app.notes ?? '';
                                    const current = (app.notes ?? '').trim();
                                    if (value.trim() === current) return;
                                    setSavingNotes(app.application_id);
                                    try {
                                      await updateApplication(app.application_id, { notes: value.trim() });
                                      await fetchData();
                                      setNotesDraft((prev) => {
                                        const next = { ...prev };
                                        delete next[app.application_id];
                                        return next;
                                      });
                                    } catch (err) {
                                      alert(err instanceof Error ? err.message : 'Failed to save notes');
                                    } finally {
                                      setSavingNotes(null);
                                    }
                                  }}
                                  placeholder="Recruiter, contacts, follow-up…"
                                  className="w-full min-h-[52px] rounded border border-input bg-background px-2 py-1 text-xs resize-y"
                                />
                                {savingNotes === app.application_id && (
                                  <span className="text-[10px] text-muted-foreground">Saving…</span>
                                )}
                              </div>

                              {/* Contact (recruiter/contact info) */}
                              <div className="mt-2 space-y-1.5">
                                <label className="block text-[11px] text-muted-foreground mb-1">Contact</label>
                                <input
                                  type="email"
                                  value={contactDraft[app.application_id]?.email ?? app.contact_email ?? ''}
                                  onChange={(e) => setContactDraft((prev) => ({
                                    ...prev,
                                    [app.application_id]: {
                                      email: e.target.value,
                                      linkedin: contactDraft[app.application_id]?.linkedin ?? app.contact_linkedin_url ?? '',
                                      phone: contactDraft[app.application_id]?.phone ?? app.contact_phone ?? '',
                                    },
                                  }))}
                                  onBlur={async () => {
                                    const d = contactDraft[app.application_id];
                                    const email = (d?.email ?? app.contact_email ?? '').trim();
                                    const linkedin = (d?.linkedin ?? app.contact_linkedin_url ?? '').trim();
                                    const phone = (d?.phone ?? app.contact_phone ?? '').trim();
                                    const cur = [(app.contact_email ?? '').trim(), (app.contact_linkedin_url ?? '').trim(), (app.contact_phone ?? '').trim()];
                                    if (email === cur[0] && linkedin === cur[1] && phone === cur[2]) return;
                                    setSavingContact(app.application_id);
                                    try {
                                      await updateApplication(app.application_id, {
                                        contact_email: email,
                                        contact_linkedin_url: linkedin,
                                        contact_phone: phone,
                                      });
                                      await fetchData();
                                      setContactDraft((prev) => {
                                        const next = { ...prev };
                                        delete next[app.application_id];
                                        return next;
                                      });
                                    } catch (err) {
                                      alert(err instanceof Error ? err.message : 'Failed to save contact');
                                    } finally {
                                      setSavingContact(null);
                                    }
                                  }}
                                  placeholder="Email"
                                  className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
                                />
                                <input
                                  type="url"
                                  value={contactDraft[app.application_id]?.linkedin ?? app.contact_linkedin_url ?? ''}
                                  onChange={(e) => setContactDraft((prev) => ({
                                    ...prev,
                                    [app.application_id]: {
                                      email: contactDraft[app.application_id]?.email ?? app.contact_email ?? '',
                                      linkedin: e.target.value,
                                      phone: contactDraft[app.application_id]?.phone ?? app.contact_phone ?? '',
                                    },
                                  }))}
                                  onBlur={async () => {
                                    const d = contactDraft[app.application_id];
                                    const email = (d?.email ?? app.contact_email ?? '').trim();
                                    const linkedin = (d?.linkedin ?? app.contact_linkedin_url ?? '').trim();
                                    const phone = (d?.phone ?? app.contact_phone ?? '').trim();
                                    const cur = [(app.contact_email ?? '').trim(), (app.contact_linkedin_url ?? '').trim(), (app.contact_phone ?? '').trim()];
                                    if (email === cur[0] && linkedin === cur[1] && phone === cur[2]) return;
                                    setSavingContact(app.application_id);
                                    try {
                                      await updateApplication(app.application_id, {
                                        contact_email: email,
                                        contact_linkedin_url: linkedin,
                                        contact_phone: phone,
                                      });
                                      await fetchData();
                                      setContactDraft((prev) => {
                                        const next = { ...prev };
                                        delete next[app.application_id];
                                        return next;
                                      });
                                    } catch (err) {
                                      alert(err instanceof Error ? err.message : 'Failed to save contact');
                                    } finally {
                                      setSavingContact(null);
                                    }
                                  }}
                                  placeholder="LinkedIn URL"
                                  className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
                                />
                                <input
                                  type="tel"
                                  value={contactDraft[app.application_id]?.phone ?? app.contact_phone ?? ''}
                                  onChange={(e) => setContactDraft((prev) => ({
                                    ...prev,
                                    [app.application_id]: {
                                      email: contactDraft[app.application_id]?.email ?? app.contact_email ?? '',
                                      linkedin: contactDraft[app.application_id]?.linkedin ?? app.contact_linkedin_url ?? '',
                                      phone: e.target.value,
                                    },
                                  }))}
                                  onBlur={async () => {
                                    const d = contactDraft[app.application_id];
                                    const email = (d?.email ?? app.contact_email ?? '').trim();
                                    const linkedin = (d?.linkedin ?? app.contact_linkedin_url ?? '').trim();
                                    const phone = (d?.phone ?? app.contact_phone ?? '').trim();
                                    const cur = [(app.contact_email ?? '').trim(), (app.contact_linkedin_url ?? '').trim(), (app.contact_phone ?? '').trim()];
                                    if (email === cur[0] && linkedin === cur[1] && phone === cur[2]) return;
                                    setSavingContact(app.application_id);
                                    try {
                                      await updateApplication(app.application_id, {
                                        contact_email: email,
                                        contact_linkedin_url: linkedin,
                                        contact_phone: phone,
                                      });
                                      await fetchData();
                                      setContactDraft((prev) => {
                                        const next = { ...prev };
                                        delete next[app.application_id];
                                        return next;
                                      });
                                    } catch (err) {
                                      alert(err instanceof Error ? err.message : 'Failed to save contact');
                                    } finally {
                                      setSavingContact(null);
                                    }
                                  }}
                                  placeholder="Phone"
                                  className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
                                />
                                {savingContact === app.application_id && (
                                  <span className="text-[10px] text-muted-foreground">Saving…</span>
                                )}
                              </div>

                              <div className="mt-2 flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  onClick={() => {
                                    setSelectedApplication(app.application_id);
                                    setShowFeedbackForm(app.application_id);
                                    loadFeedback(app.application_id);
                                  }}
                                  className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                >
                                  Feedback
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setSelectedApplication(app.application_id);
                                    loadFeedback(app.application_id);
                                  }}
                                  className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                >
                                  View feedback
                                </button>
                              </div>

                              {/* Inline feedback form (re-uses existing UI state) */}
                              {showFeedbackForm === app.application_id && (
                                <div className="mt-3 pt-3 border-t border-border space-y-2">
                                  <select
                                    value={feedbackType}
                                    onChange={(e) => setFeedbackType(e.target.value as any)}
                                    className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
                                  >
                                    <option value="rejection">Rejection</option>
                                    <option value="shortlisted">Shortlisted</option>
                                    <option value="offer">Offer</option>
                                    <option value="no_response">No Response</option>
                                    <option value="withdrawn">Withdrawn</option>
                                  </select>
                                  <textarea
                                    value={feedbackText}
                                    onChange={(e) => setFeedbackText(e.target.value)}
                                    placeholder="Paste feedback (email/notes)..."
                                    className="w-full min-h-[70px] rounded border border-input bg-background px-2 py-1 text-xs"
                                  />

                                  <div>
                                    <div className="text-[11px] font-medium text-muted-foreground mb-1">Reasons</div>
                                    <div className="flex flex-wrap gap-2">
                                      {REASON_OPTIONS.map((opt) => (
                                        <button
                                          key={opt}
                                          type="button"
                                          onClick={() => setReasonCategories((prev) => toggle(prev, opt))}
                                          className={`rounded-full px-3 py-1 text-[11px] border ${
                                            reasonCategories.includes(opt)
                                              ? 'bg-primary text-primary-foreground border-primary'
                                              : 'bg-background border-border text-muted-foreground hover:text-foreground'
                                          }`}
                                        >
                                          {opt.replace('_', ' ')}
                                        </button>
                                      ))}
                                    </div>
                                  </div>

                                  <div className="flex gap-2">
                                    <button
                                      type="button"
                                      onClick={() => handleSubmitFeedback(app.application_id)}
                                      disabled={isSubmittingFeedback}
                                      className="rounded bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                                    >
                                      {isSubmittingFeedback ? 'Submitting…' : 'Submit'}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setShowFeedbackForm(null);
                                        setFeedbackText('');
                                        setReasonCategories([]);
                                        setSignals([]);
                                      }}
                                      className="rounded border border-border px-3 py-1.5 text-xs hover:bg-muted"
                                    >
                                      Close
                                    </button>
                                  </div>
                                </div>
                              )}

                              {/* Show loaded feedback summary */}
                              {(feedback[app.application_id] || []).length > 0 && (
                                <div className="mt-3 pt-3 border-t border-border">
                                  <div className="text-[11px] text-muted-foreground mb-1">
                                    Feedback entries: {(feedback[app.application_id] || []).length}
                                  </div>
                                  <div className="space-y-2">
                                    {(feedback[app.application_id] || []).slice(0, 2).map((fb) => (
                                      <div key={fb.feedback_id} className="text-[11px] text-muted-foreground">
                                        <span className="text-foreground font-medium">{fb.feedback_type}</span>
                                        {fb.parsed_json?.reason_categories?.length ? (
                                          <> · {fb.parsed_json.reason_categories.slice(0, 3).join(', ')}</>
                                        ) : null}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
          ) : null}
        </div>
      </main>
      
      <Footer />
    </>
  );
}
