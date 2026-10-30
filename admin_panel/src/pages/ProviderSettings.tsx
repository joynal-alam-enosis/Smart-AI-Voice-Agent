import { useEffect, useState } from 'react';
import { Check, Cloud, HardDrive, KeyRound, Save, ShieldCheck } from 'lucide-react';

import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { useProviderSettings, useUpdateProviderSettings } from '../hooks/useAdminApi';
import { formatDateTime } from '../lib/utils';
import type { LLMProvider, RuntimeProviderConfig } from '../types/api';

/** Configures the non-secret LLM selection that future voice sessions will receive. */
export function ProviderSettings() {
  const settings = useProviderSettings();
  const update = useUpdateProviderSettings();
  const [draft, setDraft] = useState<RuntimeProviderConfig | null>(null);

  useEffect(() => {
    if (settings.data) setDraft(settings.data.active);
  }, [settings.data]);

  if (settings.isLoading || !draft) return <LoadingState />;
  if (settings.isError || !settings.data) return <ErrorState detail={settings.error instanceof Error ? settings.error.message : 'Could not load provider settings.'} onRetry={() => void settings.refetch()} />;

  const selectedOption = settings.data.providers.find((option) => option.provider === draft.provider);
  const canSave = Boolean(selectedOption?.configured) && !update.isPending;
  const updateDraft = (changes: Partial<RuntimeProviderConfig>) => setDraft((current) => current ? { ...current, ...changes } : current);

  return (
    <div className="mx-auto max-w-6xl animate-in fade-in duration-500">
      <header className="mb-8">
        <p className="text-sm font-semibold text-indigo-300">RUNTIME CONFIGURATION</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Provider settings</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">Choose the language model for new sessions. Local Ollama remains the default; cloud credentials are resolved on the server and never appear in this browser.</p>
      </header>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="p-5 sm:p-7">
          <div className="flex items-start justify-between gap-4"><div><h2 className="section-title">Select an engine</h2><p className="section-copy">Available options are validated against server-side configuration.</p></div><Badge tone="success">No keys in browser</Badge></div>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {settings.data.providers.map((option) => {
              const active = draft.provider === option.provider;
              return (
                <button
                  key={option.provider}
                  type="button"
                  onClick={() => updateDraft({ provider: option.provider, model: option.default_model, base_url: option.local ? draft.base_url ?? 'http://localhost:11434/v1' : null })}
                  className={`relative rounded-2xl border p-4 text-left transition ${active ? 'border-indigo-400 bg-indigo-500/10 shadow-[inset_0_0_0_1px_rgba(129,140,248,0.16)]' : 'border-slate-800 bg-slate-950/45 hover:border-slate-600'}`}
                >
                  <div className="flex items-start justify-between gap-3"><span className={`rounded-lg p-2 ${option.local ? 'bg-emerald-400/10 text-emerald-300' : 'bg-sky-400/10 text-sky-300'}`}>{option.local ? <HardDrive className="h-4 w-4" /> : <Cloud className="h-4 w-4" />}</span>{active && <Check className="h-4 w-4 text-indigo-300" />}</div>
                  <p className="mt-4 font-semibold text-white">{option.display_name}</p>
                  <p className="mt-1 text-xs text-slate-500">{option.default_model}</p>
                  <div className="mt-3"><Badge tone={option.configured ? 'success' : 'warning'}>{option.configured ? 'Available' : 'Needs server key'}</Badge></div>
                </button>
              );
            })}
          </div>

          <div className="mt-7 grid gap-5 sm:grid-cols-2">
            <label><span className="field-label">Model</span><input className="field" value={draft.model} onChange={(event) => updateDraft({ model: event.target.value })} maxLength={120} /></label>
            {draft.provider === 'ollama' && <label><span className="field-label">Ollama endpoint</span><input className="field" value={draft.base_url ?? ''} onChange={(event) => updateDraft({ base_url: event.target.value })} placeholder="http://localhost:11434/v1" maxLength={500} /></label>}
          </div>
          {selectedOption && !selectedOption.configured && <p role="alert" className="mt-5 flex gap-2 rounded-xl border border-amber-400/20 bg-amber-400/10 p-3 text-sm leading-6 text-amber-100"><KeyRound className="mt-0.5 h-4 w-4 shrink-0" />Add the selected provider’s API key to the backend environment before activating it.</p>}
          {update.isError && <p role="alert" className="mt-5 rounded-xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-100">{update.error instanceof Error ? update.error.message : 'The provider selection could not be saved.'}</p>}
          {update.isSuccess && <p className="mt-5 flex items-center gap-2 text-sm text-emerald-300"><Check className="h-4 w-4" />Provider selection saved for future sessions.</p>}
          <div className="mt-7 flex items-center justify-between gap-4 border-t border-slate-800 pt-5"><p className="text-xs text-slate-500">Last saved {formatDateTime(settings.data.updated_at)}</p><Button disabled={!canSave} onClick={() => update.mutate(draft)}>{update.isPending ? 'Saving…' : <><Save className="h-4 w-4" />Save selection</>}</Button></div>
        </Card>

        <div className="space-y-6">
          <Card className="p-6"><ShieldCheck className="h-6 w-6 text-emerald-300" /><h2 className="mt-4 section-title">Safe configuration boundary</h2><p className="section-copy">The console can select a configured provider and model. API keys, tokens, and cloud credentials stay in server environment variables.</p></Card>
          <Card className="p-6"><HardDrive className="h-6 w-6 text-indigo-300" /><h2 className="mt-4 section-title">Local-first default</h2><p className="section-copy">Ollama is always available as the default option. A cloud outage never removes the local path from your deployment.</p></Card>
          <Card className="p-6"><Cloud className="h-6 w-6 text-sky-300" /><h2 className="mt-4 section-title">Session behavior</h2><p className="section-copy">The saved choice applies when a new LLM service is created. Active calls remain stable with their current provider.</p></Card>
        </div>
      </div>
    </div>
  );
}

function LoadingState() { return <div className="mx-auto max-w-6xl"><div className="h-10 w-64 animate-pulse rounded-lg bg-slate-800" /><div className="mt-8 h-[560px] animate-pulse rounded-2xl border border-slate-800 bg-slate-900/60" /></div>; }
function ErrorState({ detail, onRetry }: { detail: string; onRetry: () => void }) { return <Card className="mx-auto mt-24 max-w-xl p-7 text-center"><h1 className="text-xl font-semibold text-white">Provider settings are unavailable</h1><p className="mt-3 text-sm leading-6 text-slate-400">{detail}</p><Button className="mt-6" onClick={onRetry}>Try again</Button></Card>; }
