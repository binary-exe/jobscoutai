'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';
import { Brain, FileUp, MessageCircle, Loader2, AlertCircle } from 'lucide-react';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import { indexKnowledgeDocument, queryKnowledge, type KbQueryResponse, type KbCitation } from '@/lib/apply-api';

export default function KbPage() {
  const router = useRouter();
  const [authChecked, setAuthChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Index form
  const [indexSourceType, setIndexSourceType] = useState('note');
  const [indexSourceTable, setIndexSourceTable] = useState('');
  const [indexSourceId, setIndexSourceId] = useState('');
  const [indexTitle, setIndexTitle] = useState('');
  const [indexText, setIndexText] = useState('');
  const [indexing, setIndexing] = useState(false);
  const [indexResult, setIndexResult] = useState<{ document_id: string; chunks_indexed: number } | null>(null);
  const [indexError, setIndexError] = useState<string | null>(null);

  // Query form
  const [question, setQuestion] = useState('');
  const [querySourceType, setQuerySourceType] = useState('');
  const [querying, setQuerying] = useState(false);
  const [queryResult, setQueryResult] = useState<KbQueryResponse | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
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
        router.replace(`/login?next=${encodeURIComponent('/kb')}`);
        return;
      }
      setAuthChecked(true);
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleIndex = async (e: React.FormEvent) => {
    e.preventDefault();
    setIndexError(null);
    setIndexResult(null);
    if (!indexText.trim()) {
      setIndexError('Please enter text to index.');
      return;
    }
    setIndexing(true);
    try {
      const res = await indexKnowledgeDocument({
        source_type: indexSourceType,
        source_table: indexSourceTable.trim() || undefined,
        source_id: indexSourceId.trim() || undefined,
        title: indexTitle.trim() || undefined,
        text: indexText.trim(),
      });
      setIndexResult({ document_id: res.document_id, chunks_indexed: res.chunks_indexed });
      setIndexText('');
    } catch (err) {
      setIndexError(err instanceof Error ? err.message : 'Failed to index document.');
    } finally {
      setIndexing(false);
    }
  };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    setQueryError(null);
    setQueryResult(null);
    if (!question.trim()) {
      setQueryError('Please enter a question.');
      return;
    }
    setQuerying(true);
    try {
      const res = await queryKnowledge({
        question: question.trim(),
        source_type: querySourceType.trim() || undefined,
        max_chunks: 10,
      });
      setQueryResult(res);
    } catch (err) {
      setQueryError(err instanceof Error ? err.message : 'Query failed.');
    } finally {
      setQuerying(false);
    }
  };

  if (!authChecked) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 container max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center gap-2 mb-8">
          <Brain className="h-8 w-8 text-foreground" />
          <h1 className="text-2xl font-semibold tracking-tight">Second Brain</h1>
        </div>
        <p className="text-muted-foreground mb-8">
          Index your notes and artifacts, then ask questions. Answers are grounded in your stored content with citations.
        </p>

        {/* Index */}
        <section className="mb-12">
          <h2 className="text-lg font-medium flex items-center gap-2 mb-4">
            <FileUp className="h-4 w-4" />
            Index a document
          </h2>
          <form onSubmit={handleIndex} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Source type</label>
                <input
                  type="text"
                  value={indexSourceType}
                  onChange={(e) => setIndexSourceType(e.target.value)}
                  placeholder="e.g. note, resume"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Title (optional)</label>
                <input
                  type="text"
                  value={indexTitle}
                  onChange={(e) => setIndexTitle(e.target.value)}
                  placeholder="Document title"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Source table (optional)</label>
                <input
                  type="text"
                  value={indexSourceTable}
                  onChange={(e) => setIndexSourceTable(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Source ID (optional)</label>
                <input
                  type="text"
                  value={indexSourceId}
                  onChange={(e) => setIndexSourceId(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Text to index</label>
              <textarea
                value={indexText}
                onChange={(e) => setIndexText(e.target.value)}
                rows={6}
                placeholder="Paste or type the content you want to add to your knowledge base..."
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-y"
              />
            </div>
            {indexError && (
              <div className="flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {indexError}
              </div>
            )}
            {indexResult && (
              <p className="text-sm text-muted-foreground">
                Indexed {indexResult.chunks_indexed} chunk(s). Document ID: {indexResult.document_id}
              </p>
            )}
            <button
              type="submit"
              disabled={indexing}
              className="px-4 py-2 rounded-lg bg-foreground text-background text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
            >
              {indexing ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
              {indexing ? 'Indexing…' : 'Index'}
            </button>
          </form>
        </section>

        {/* Query */}
        <section>
          <h2 className="text-lg font-medium flex items-center gap-2 mb-4">
            <MessageCircle className="h-4 w-4" />
            Ask a question
          </h2>
          <form onSubmit={handleQuery} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Question</label>
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g. What did I note about project X?"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Filter by source type (optional)</label>
              <input
                type="text"
                value={querySourceType}
                onChange={(e) => setQuerySourceType(e.target.value)}
                placeholder="e.g. note"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            {queryError && (
              <div className="flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {queryError}
              </div>
            )}
            <button
              type="submit"
              disabled={querying}
              className="px-4 py-2 rounded-lg bg-foreground text-background text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
            >
              {querying ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}
              {querying ? 'Searching…' : 'Ask'}
            </button>
          </form>

          {queryResult && (
            <div className="mt-8 p-4 rounded-lg border border-border bg-muted/30">
              <h3 className="text-sm font-medium mb-2">Answer</h3>
              <p className="text-sm whitespace-pre-wrap mb-4">{queryResult.answer}</p>
              {queryResult.citations.length > 0 && (
                <>
                  <h3 className="text-sm font-medium mb-2">Citations</h3>
                  <ul className="space-y-2">
                    {queryResult.citations.map((c: KbCitation, i: number) => (
                      <li key={c.chunk_id} className="text-xs border-l-2 border-muted-foreground/30 pl-2 py-1">
                        <span className="text-muted-foreground">
                          [{i + 1}] {c.source_type}
                          {c.source_id ? ` · ${c.source_id}` : ''}
                          {c.page != null ? ` · p.${c.page}` : ''}
                          {' '}(score {c.score.toFixed(2)})
                        </span>
                        <p className="mt-0.5 text-foreground/90 truncate max-w-full">{c.snippet}</p>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </section>
      </main>
      <Footer />
    </div>
  );
}
