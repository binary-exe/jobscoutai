'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Clock, FileText, ExternalLink, Copy, Download, CheckCircle2, XCircle, Calendar, Briefcase, MessageSquare, Plus, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { getHistory, exportApplyPackDocx, getApplications, getApplicationFeedback, createApplicationFeedback, updateApplication, type Application, type ApplyPackHistory, type ApplicationFeedback } from '@/lib/apply-api';
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
      const [packsData, appsData] = await Promise.all([
        getHistory().catch(() => ({ packs: [], total: 0 })),
        getApplications().catch(() => ({ applications: [], total: 0 })),
      ]);
      setPacks(packsData.packs || []);
      setApplications(appsData.applications || []);
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
                Start tracking your applications to stay organized.
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
              {applications.map((app) => {
                const appFeedback = feedback[app.application_id] || [];
                const isSelected = selectedApplication === app.application_id;
                
                return (
                  <div 
                    key={app.application_id} 
                    className={`rounded-xl border border-border bg-card p-6 ${isSelected ? 'ring-2 ring-primary' : ''}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          {getStatusIcon(app.status)}
                          <h3 className="font-semibold">
                            {app.title || 'Untitled Job'}
                          </h3>
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            app.status === 'offer' ? 'bg-green-500/20 text-green-500' :
                            app.status === 'rejected' ? 'bg-red-500/20 text-red-500' :
                            app.status === 'interview' ? 'bg-blue-500/20 text-blue-500' :
                            'bg-muted text-muted-foreground'
                          }`}>
                            {app.status}
                          </span>
                        </div>
                        {app.company && (
                          <p className="text-sm text-muted-foreground mb-2">{app.company}</p>
                        )}
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          {app.applied_at && (
                            <div className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              Applied {new Date(app.applied_at).toLocaleDateString()}
                            </div>
                          )}
                          {app.interview_at && (
                            <div className="flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              Interview {new Date(app.interview_at).toLocaleDateString()}
                            </div>
                          )}
                          {app.offer_at && (
                            <div className="flex items-center gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              Offer {new Date(app.offer_at).toLocaleDateString()}
                            </div>
                          )}
                          {app.rejected_at && (
                            <div className="flex items-center gap-1">
                              <XCircle className="h-3 w-3" />
                              Rejected {new Date(app.rejected_at).toLocaleDateString()}
                            </div>
                          )}
                          {app.reminder_at && (
                            <div className="flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              Reminder: {new Date(app.reminder_at).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                        {app.notes && (
                          <p className="text-sm text-muted-foreground mt-2">{app.notes}</p>
                        )}
                        
                        {/* Feedback Section */}
                        {appFeedback.length > 0 && (
                          <div className="mt-4 pt-4 border-t border-border">
                            <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                              <MessageSquare className="h-4 w-4" />
                              Feedback ({appFeedback.length})
                            </h4>
                            <div className="space-y-2">
                              {appFeedback.map((fb) => (
                                <div key={fb.feedback_id} className="text-xs bg-muted/50 p-2 rounded">
                                  <div className="flex items-center justify-between mb-1">
                                    <span className="font-medium capitalize">{fb.feedback_type}</span>
                                    {fb.created_at && (
                                      <span className="text-muted-foreground">
                                        {new Date(fb.created_at).toLocaleDateString()}
                                      </span>
                                    )}
                                  </div>
                                  {fb.raw_text && (
                                    <p className="text-muted-foreground mb-1">{fb.raw_text}</p>
                                  )}
                                  {fb.parsed_json?.reason_categories && fb.parsed_json.reason_categories.length > 0 && (
                                    <div className="mt-1">
                                      <span className="text-muted-foreground">Reasons: </span>
                                      <span className="text-foreground">
                                        {fb.parsed_json.reason_categories.join(', ')}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Load feedback (lazy) */}
                        {appFeedback.length === 0 && (
                          <button
                            onClick={() => {
                              setSelectedApplication(app.application_id);
                              loadFeedback(app.application_id);
                            }}
                            className="mt-4 flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
                          >
                            <MessageSquare className="h-4 w-4" />
                            Load feedback
                          </button>
                        )}
                        
                        {/* Add Feedback Form */}
                        {showFeedbackForm === app.application_id ? (
                          <div className="mt-4 pt-4 border-t border-border space-y-2">
                            <select
                              value={feedbackType}
                              onChange={(e) => setFeedbackType(e.target.value as any)}
                              className="w-full rounded border border-input bg-background px-2 py-1 text-sm"
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
                              placeholder="Paste rejection email, feedback, or notes..."
                              className="w-full min-h-[80px] rounded border border-input bg-background px-2 py-1 text-sm"
                            />

                            {/* Structured feedback chips */}
                            <div className="space-y-2">
                              <div>
                                <div className="text-xs font-medium text-muted-foreground mb-1">Reason categories</div>
                                <div className="flex flex-wrap gap-2">
                                  {REASON_OPTIONS.map((opt) => (
                                    <button
                                      key={opt}
                                      type="button"
                                      onClick={() => setReasonCategories((prev) => toggle(prev, opt))}
                                      className={`rounded-full px-3 py-1 text-xs border ${
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

                              <div>
                                <div className="text-xs font-medium text-muted-foreground mb-1">Signals</div>
                                <div className="flex flex-wrap gap-2">
                                  {SIGNAL_OPTIONS.map((opt) => (
                                    <button
                                      key={opt}
                                      type="button"
                                      onClick={() => setSignals((prev) => toggle(prev, opt))}
                                      className={`rounded-full px-3 py-1 text-xs border ${
                                        signals.includes(opt)
                                          ? 'bg-primary text-primary-foreground border-primary'
                                          : 'bg-background border-border text-muted-foreground hover:text-foreground'
                                      }`}
                                    >
                                      {opt.replace('_', ' ')}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleSubmitFeedback(app.application_id)}
                                disabled={isSubmittingFeedback}
                                className="rounded bg-primary px-3 py-1 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                              >
                                {isSubmittingFeedback ? 'Submitting...' : 'Submit'}
                              </button>
                              <button
                                onClick={() => {
                                  setShowFeedbackForm(null);
                                  setFeedbackText('');
                                  setReasonCategories([]);
                                  setSignals([]);
                                }}
                                className="rounded border border-border px-3 py-1 text-sm hover:bg-muted"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <button
                            onClick={() => {
                              setShowFeedbackForm(app.application_id);
                              setSelectedApplication(app.application_id);
                              loadFeedback(app.application_id);
                            }}
                            className="mt-4 flex items-center gap-2 text-sm text-primary hover:text-primary/80"
                          >
                            <Plus className="h-4 w-4" />
                            Add Feedback
                          </button>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {app.job_url && (
                          <a
                            href={app.job_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-2 rounded-lg border border-border hover:bg-muted"
                            title="View Job"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      </main>
      
      <Footer />
    </>
  );
}
