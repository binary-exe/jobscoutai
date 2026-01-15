'use client';

import { useState, useEffect } from 'react';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Clock, FileText, ExternalLink, Copy, Download, CheckCircle2, XCircle, Calendar, Briefcase } from 'lucide-react';
import Link from 'next/link';
import { getHistory, exportApplyPackDocx, getApplications, type Application, type ApplyPackHistory } from '@/lib/apply-api';

export default function HistoryPage() {
  const [packs, setPacks] = useState<ApplyPackHistory[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [activeTab, setActiveTab] = useState<'packs' | 'applications'>('packs');
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

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
          ) : activeTab === 'packs' && packs.length === 0 ? (
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
              {applications.map((app) => (
                <div key={app.application_id} className="rounded-xl border border-border bg-card p-6">
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
              ))}
            </div>
          ) : null}
        </div>
      </main>
      
      <Footer />
    </>
  );
}
