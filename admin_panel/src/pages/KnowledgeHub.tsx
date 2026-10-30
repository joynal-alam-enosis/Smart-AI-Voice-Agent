import { useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from 'react';
import { CheckCircle2, FileSearch, FileUp, Files, Search, UploadCloud } from 'lucide-react';

import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { useKnowledgeDocuments, useKnowledgeSearch, useUploadKnowledgeDocument } from '../hooks/useAdminApi';
import { formatDateTime } from '../lib/utils';

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPTED_TYPES = ['.pdf', '.md', '.txt'];

/** Tenant-scoped upload and retrieval testing workspace for operational knowledge. */
export function KnowledgeHub() {
  const documents = useKnowledgeDocuments();
  const upload = useUploadKnowledgeDocument();
  const search = useKnowledgeSearch();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [query, setQuery] = useState('What time are check-in and check-out?');

  const chooseFile = (file: File | undefined) => {
    if (!file) return;
    const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`;
    if (!ACCEPTED_TYPES.includes(extension)) { setFileError('Choose a PDF, Markdown, or text file.'); setSelectedFile(null); return; }
    if (file.size > MAX_BYTES) { setFileError('Documents must be 10 MB or smaller.'); setSelectedFile(null); return; }
    setFileError(null);
    setSelectedFile(file);
  };

  const uploadFile = () => {
    if (!selectedFile) return;
    upload.mutate(selectedFile, { onSuccess: () => setSelectedFile(null) });
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); setIsDragging(false); chooseFile(event.dataTransfer.files[0]); };
  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => chooseFile(event.target.files?.[0]);
  const handleSearch = (event: FormEvent) => { event.preventDefault(); if (query.trim().length >= 2) search.mutate(query.trim()); };

  return (
    <div className="mx-auto max-w-7xl animate-in fade-in duration-500">
      <header className="mb-8"><p className="text-sm font-semibold text-indigo-300">RETRIEVAL OPERATIONS</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Knowledge hub</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">Stage operational knowledge for Grand Meridian, then test the exact retrieval guardrails used during voice calls.</p></header>
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-6">
          <Card className="p-5 sm:p-7"><div className="flex items-start justify-between gap-4"><div><h2 className="section-title">Add knowledge</h2><p className="section-copy">PDF, Markdown, or text · maximum 10 MB</p></div><UploadCloud className="h-5 w-5 text-indigo-300" /></div>
            <div onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop} className={`mt-6 rounded-2xl border border-dashed p-8 text-center transition ${isDragging ? 'border-indigo-400 bg-indigo-500/10' : 'border-slate-700 bg-slate-950/35'}`}><FileUp className="mx-auto h-8 w-8 text-indigo-300" /><p className="mt-4 text-sm font-semibold text-slate-100">Drop a policy document here</p><p className="mt-1 text-sm text-slate-500">or choose a file from your computer</p><Button variant="secondary" className="mt-5" onClick={() => inputRef.current?.click()}>Browse files</Button><input ref={inputRef} className="hidden" type="file" accept={ACCEPTED_TYPES.join(',')} onChange={handleFileChange} /></div>
            {selectedFile && <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] p-3"><div className="min-w-0"><p className="truncate text-sm font-medium text-emerald-100">{selectedFile.name}</p><p className="mt-1 text-xs text-emerald-200/65">{(selectedFile.size / 1024).toFixed(1)} KB · tenant: grand-meridian</p></div><Button disabled={upload.isPending} onClick={uploadFile}>{upload.isPending ? 'Indexing…' : 'Index now'}</Button></div>}
            {(fileError || upload.isError) && <p role="alert" className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm leading-6 text-rose-100">{fileError ?? (upload.error instanceof Error ? upload.error.message : 'The document could not be indexed.')}</p>}
            {upload.isSuccess && <p className="mt-4 flex items-center gap-2 text-sm text-emerald-300"><CheckCircle2 className="h-4 w-4" />Document indexed in {upload.data.chunks_indexed} voice-ready chunks.</p>}
          </Card>
          <DocumentList />
        </div>
        <Card className="p-5 sm:p-7"><div className="flex items-start justify-between gap-4"><div><h2 className="section-title">Search tester</h2><p className="section-copy">Test tenant-scoped retrieval before a guest ever hears it.</p></div><FileSearch className="h-5 w-5 text-violet-300" /></div>
          <form className="mt-6" onSubmit={handleSearch}><label><span className="field-label">Ask the knowledge base</span><div className="flex flex-col gap-3 sm:flex-row"><input className="field" value={query} minLength={2} maxLength={500} onChange={(event) => setQuery(event.target.value)} /><Button type="submit" disabled={search.isPending || query.trim().length < 2}>{search.isPending ? 'Searching…' : <><Search className="h-4 w-4" />Test search</>}</Button></div></label></form>
          <div className="mt-7 border-t border-slate-800 pt-6"><SearchResults /></div>
        </Card>
      </div>
    </div>
  );

  function DocumentList() {
    if (documents.isLoading) return <Card className="p-6"><div className="h-20 animate-pulse rounded-xl bg-slate-800" /></Card>;
    if (documents.isError) return <Card className="p-6"><p className="text-sm text-rose-200">{documents.error instanceof Error ? documents.error.message : 'Document status is unavailable.'}</p><Button variant="secondary" className="mt-4" onClick={() => void documents.refetch()}>Try again</Button></Card>;
    return <Card className="p-5 sm:p-6"><div className="flex items-center justify-between gap-3"><div><h2 className="section-title">Indexed documents</h2><p className="section-copy">Active for this tenant</p></div><Badge tone="neutral">{documents.data?.length ?? 0}</Badge></div>{documents.data?.length ? <ul className="mt-5 space-y-2">{documents.data.map((document) => <li key={`${document.name}-${document.uploaded_at}`} className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/35 p-3"><div className="min-w-0"><p className="truncate text-sm font-medium text-slate-100">{document.name}</p><p className="mt-1 text-xs text-slate-500">{document.chunks_indexed} chunks · {formatDateTime(document.uploaded_at)}</p></div><Badge tone="success">Indexed</Badge></li>)}</ul> : <div className="mt-5 rounded-xl border border-dashed border-slate-700 p-5 text-center"><Files className="mx-auto h-5 w-5 text-slate-600" /><p className="mt-2 text-sm text-slate-500">No uploaded documents yet.</p></div>}</Card>;
  }

  function SearchResults() {
    if (search.isIdle) return <div className="flex min-h-72 flex-col items-center justify-center text-center"><Search className="h-7 w-7 text-slate-600" /><p className="mt-3 text-sm font-medium text-slate-300">Run a retrieval test</p><p className="mt-1 max-w-sm text-sm leading-6 text-slate-500">Results will show the source chunks available to the voice agent, limited by the same spoken-brevity policy.</p></div>;
    if (search.isPending) return <div className="min-h-72 animate-pulse rounded-xl bg-slate-900/60" />;
    if (search.isError) return <p role="alert" className="rounded-xl border border-rose-400/20 bg-rose-400/10 p-4 text-sm leading-6 text-rose-100">{search.error instanceof Error ? search.error.message : 'Search failed.'}</p>;
    if (!search.data?.has_context) return <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.07] p-5"><Badge tone="warning">No matching context</Badge><p className="mt-4 text-sm font-medium text-amber-100">Spoken fallback</p><p className="mt-2 text-sm leading-6 text-amber-100/75">“{search.data?.fallback_spoken}”</p></div>;
    return <div><div className="flex items-center justify-between"><p className="text-sm font-medium text-emerald-300">{search.data.chunks.length} relevant source{search.data.chunks.length === 1 ? '' : 's'}</p><Badge tone="success">Voice-safe</Badge></div><div className="mt-4 space-y-3">{search.data.chunks.map((chunk, index) => <article key={`${chunk.source}-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4"><div className="flex items-center justify-between gap-3"><p className="text-sm font-semibold text-slate-200">{chunk.source}</p><span className="text-xs font-medium text-indigo-300">{Math.round(chunk.score * 100)}% match</span></div><p className="mt-3 text-sm leading-6 text-slate-400">{chunk.excerpt}</p></article>)}</div></div>;
  }
}
