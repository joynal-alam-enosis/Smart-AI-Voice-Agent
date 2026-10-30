import { CircleAlert, Timer } from 'lucide-react';

import { formatMilliseconds } from '../lib/utils';
import type { LatencyBreakdown } from '../types/api';
import { Badge } from './ui/badge';

interface LatencyWaterfallProps {
  metrics: LatencyBreakdown | null;
  targetMs: number;
}

const segments = [
  { key: 'vad_ms', label: 'VAD', color: 'bg-sky-400' },
  { key: 'stt_ms', label: 'STT', color: 'bg-cyan-400' },
  { key: 'rag_ms', label: 'RAG', color: 'bg-violet-400' },
  { key: 'llm_ms', label: 'LLM', color: 'bg-amber-400' },
  { key: 'tts_ms', label: 'TTS', color: 'bg-emerald-400' },
] as const;

/** Visualizes one measured voice turn, with an honest empty state before calls run. */
export function LatencyWaterfall({ metrics, targetMs }: LatencyWaterfallProps) {
  if (!metrics) {
    return (
      <div className="flex min-h-56 flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-950/35 px-6 text-center">
        <Timer className="h-7 w-7 text-slate-500" aria-hidden="true" />
        <p className="mt-3 text-sm font-semibold text-slate-200">Waiting for the first completed voice turn</p>
        <p className="mt-1 max-w-sm text-sm leading-6 text-slate-500">The waterfall will appear as soon as the pipeline records VAD, transcription, retrieval, model, and speech timings.</p>
      </div>
    );
  }

  const isOptimal = metrics.total_ms < targetMs;
  const total = Math.max(metrics.total_ms, 1);
  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-3xl font-semibold tracking-tight text-white">{formatMilliseconds(metrics.total_ms)}</p>
          <p className="mt-1 text-sm text-slate-400">End-to-end turn latency</p>
        </div>
        <Badge tone={isOptimal ? 'success' : 'warning'}>{isOptimal ? `Optimal under ${targetMs} ms` : `Above ${targetMs} ms target`}</Badge>
      </div>
      <div className="flex h-4 overflow-hidden rounded-full bg-slate-800" aria-label="Latency waterfall breakdown">
        {segments.map(({ key, label, color }) => {
          const value = metrics[key];
          return <div key={key} className={`${color} transition-all`} style={{ width: `${(value / total) * 100}%` }} title={`${label}: ${formatMilliseconds(value)}`} />;
        })}
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-x-5 gap-y-4 sm:grid-cols-5">
        {segments.map(({ key, label, color }) => (
          <div key={key}>
            <dt className="flex items-center gap-1.5 text-xs font-medium text-slate-500"><span className={`h-2 w-2 rounded-full ${color}`} />{label}</dt>
            <dd className="mt-1 text-sm font-semibold text-slate-100">{formatMilliseconds(metrics[key])}</dd>
          </div>
        ))}
      </dl>
      {!isOptimal && <p className="mt-5 flex gap-2 text-sm leading-6 text-amber-200"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />Review the largest stage before changing the selected provider or speech settings.</p>}
    </div>
  );
}
