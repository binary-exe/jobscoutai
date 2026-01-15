'use client';

import { useState } from 'react';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { FileText, Link as LinkIcon, Sparkles, CheckCircle2, AlertTriangle, Clock, Loader2, Edit2, Save, Shield, AlertCircle } from 'lucide-react';
import { parseJob, updateJobTarget, generateApplyPack, generateTrustReport, uploadResume, type ParsedJob, type ApplyPack, type TrustReport } from '@/lib/apply-api';

export default function ApplyWorkspacePage() {
  const [resumeText, setResumeText] = useState('');
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
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);

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

  const handleGenerateTrustReport = async (jobTargetId: string) => {
    setIsGeneratingTrust(true);
    try {
      const report = await generateTrustReport(jobTargetId);
      setTrustReport(report);
    } catch (err) {
      // Don't show error for trust report - it's optional
      console.error('Failed to generate trust report:', err);
    } finally {
      setIsGeneratingTrust(false);
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
    try {
      const pack = await generateApplyPack(
        resumeText,
        parsedJob.job_url,
        parsedJob.description_text,
        true
      );
      setApplyPack(pack);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate apply pack');
    } finally {
      setIsGenerating(false);
    }
  };

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
              a Trust Report, and track your applications.
            </p>
          </div>

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
                    <div className="text-xs text-muted-foreground italic">
                      Signals only, not guarantees
                    </div>
                  </div>
                  
                  <div className="space-y-4">
                    {/* Scam Risk */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Scam Risk</span>
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                          trustReport.scam_risk === 'high' ? 'bg-red-500/20 text-red-500' :
                          trustReport.scam_risk === 'medium' ? 'bg-yellow-500/20 text-yellow-500' :
                          'bg-green-500/20 text-green-500'
                        }`}>
                          {trustReport.scam_risk.toUpperCase()}
                        </span>
                      </div>
                      {trustReport.scam_reasons.length > 0 && (
                        <ul className="text-xs text-muted-foreground space-y-1">
                          {trustReport.scam_reasons.map((reason, i) => (
                            <li key={i} className="flex items-start gap-1">
                              <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                              <span>{reason}</span>
                            </li>
                          ))}
                        </ul>
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
                          {trustReport.ghost_likelihood.toUpperCase()}
                        </span>
                      </div>
                      {trustReport.ghost_reasons.length > 0 && (
                        <ul className="text-xs text-muted-foreground space-y-1">
                          {trustReport.ghost_reasons.map((reason, i) => (
                            <li key={i} className="flex items-start gap-1">
                              <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                              <span>{reason}</span>
                            </li>
                          ))}
                        </ul>
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
                          <ul className="text-xs text-muted-foreground space-y-1">
                            {trustReport.staleness_reasons.map((reason, i) => (
                              <li key={i} className="flex items-start gap-1">
                                <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                                <span>{reason}</span>
                              </li>
                            ))}
                          </ul>
                        )}
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
                  
                  {/* Actions */}
                  <div className="mt-4 pt-4 border-t border-border flex gap-2">
                    <button
                      onClick={() => {
                        if (applyPack.tailored_summary) {
                          navigator.clipboard.writeText(applyPack.tailored_summary);
                        }
                      }}
                      className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm hover:bg-muted"
                    >
                      Copy Summary
                    </button>
                    <button
                      onClick={async () => {
                        if (parsedJob) {
                          try {
                            const { exportApplyPackDocx } = await import('@/lib/apply-api');
                            const blob = await exportApplyPackDocx(applyPack.apply_pack_id, 'combined');
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `apply_pack_${applyPack.apply_pack_id.slice(0, 8)}.docx`;
                            document.body.appendChild(a);
                            a.click();
                            window.URL.revokeObjectURL(url);
                            document.body.removeChild(a);
                          } catch (err) {
                            alert(err instanceof Error ? err.message : 'DOCX export requires paid plan');
                          }
                        }
                      }}
                      className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm hover:bg-muted"
                    >
                      Download DOCX
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
