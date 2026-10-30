import { useEffect, useRef, useState } from 'react';
import { AudioLines, Gauge, Play, SlidersHorizontal, Sparkles, Volume2 } from 'lucide-react';

import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { useVoiceAudition, useVoices } from '../hooks/useAdminApi';
import type { VoiceProfile } from '../types/api';

const DEFAULT_AUDITION = 'Welcome to Grand Meridian. How may I make your stay exceptional today?';

/** Voice-design workbench for previewing catalog voices and acoustic parameters. */
export function VoiceStudio() {
  const voices = useVoices();
  const audition = useVoiceAudition();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>('');
  const [speed, setSpeed] = useState(1);
  const [pitch, setPitch] = useState(0);
  const [previewText, setPreviewText] = useState(DEFAULT_AUDITION);

  const selectedVoice = voices.data?.find((voice) => voice.voice_id === selectedVoiceId) ?? voices.data?.[0];

  useEffect(() => {
    if (selectedVoice && !selectedVoiceId) {
      setSelectedVoiceId(selectedVoice.voice_id);
      setSpeed(selectedVoice.recommended_speed);
    }
  }, [selectedVoice, selectedVoiceId]);

  useEffect(() => () => {
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
  }, []);

  const playAudition = () => {
    if (!selectedVoice) return;
    audition.mutate(
      { voice_id: selectedVoice.voice_id, text: previewText, speed, pitch },
      {
        onSuccess: (audio) => {
          if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
          const url = URL.createObjectURL(audio);
          audioUrlRef.current = url;
          const player = new Audio(url);
          audioRef.current = player;
          void player.play();
        },
      },
    );
  };

  if (voices.isLoading) return <LoadingState />;
  if (voices.isError || !voices.data || !selectedVoice) return <ErrorState detail={voices.error instanceof Error ? voices.error.message : 'Could not load the voice catalog.'} onRetry={() => void voices.refetch()} />;

  return (
    <div className="mx-auto max-w-7xl animate-in fade-in duration-500">
      <header className="mb-8">
        <p className="text-sm font-semibold text-indigo-300">ACOUSTIC WORKBENCH</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Voice studio</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">Design a confident, human voice for every guest-facing persona. Preview requests use the configured server-side synthesis engine.</p>
      </header>

      <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
        <Card className="overflow-hidden p-5 sm:p-7">
          <div className="flex items-start justify-between gap-4"><div><h2 className="section-title">Voice library</h2><p className="section-copy">{voices.data.length} registered voice profiles</p></div><AudioLines className="h-5 w-5 text-indigo-300" /></div>
          <div className="mt-6 max-h-[590px] space-y-2 overflow-y-auto pr-1">
            {voices.data.map((voice) => <VoiceOption key={voice.voice_id} voice={voice} selected={voice.voice_id === selectedVoice.voice_id} onSelect={() => { setSelectedVoiceId(voice.voice_id); setSpeed(voice.recommended_speed); }} />)}
          </div>
        </Card>

        <div className="space-y-6">
          <Card className="relative overflow-hidden p-5 sm:p-7">
            <div className="absolute -right-24 -top-24 h-56 w-56 rounded-full bg-indigo-500/20 blur-3xl" aria-hidden="true" />
            <div className="relative">
              <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
                <div className="flex gap-4"><div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-400 to-violet-600 text-xl font-bold text-white">{selectedVoice.name.charAt(0)}</div><div><div className="flex flex-wrap items-center gap-2"><h2 className="text-xl font-semibold text-white">{selectedVoice.name}</h2><Badge tone="accent">{selectedVoice.provider}</Badge></div><p className="mt-1 text-sm text-slate-400">{selectedVoice.gender} · {selectedVoice.accent}</p></div></div>
                <Badge tone="success">Catalog verified</Badge>
              </div>
              <p className="mt-6 max-w-2xl text-sm leading-6 text-slate-300">{selectedVoice.description}</p>
              <div className="mt-5 flex flex-wrap gap-2">{selectedVoice.role_fit.map((role) => <span key={role} className="rounded-full border border-slate-700 bg-slate-900/80 px-2.5 py-1 text-xs text-slate-400">{role.replaceAll('_', ' ')}</span>)}</div>
            </div>
          </Card>

          <Card className="p-5 sm:p-7">
            <div className="flex items-start gap-3"><SlidersHorizontal className="mt-0.5 h-5 w-5 text-indigo-300" /><div><h2 className="section-title">Audition controls</h2><p className="section-copy">Controls stay within the platform’s validated acoustic limits.</p></div></div>
            <div className="mt-7 grid gap-6 sm:grid-cols-2">
              <RangeControl label="Speaking pace" value={speed} min={0.7} max={1.4} step={0.01} suffix="×" onChange={setSpeed} />
              <RangeControl label="Pitch profile" value={pitch} min={-20} max={20} step={1} suffix=" st" onChange={setPitch} />
            </div>
            <label className="mt-7 block"><span className="field-label">Preview script</span><textarea className="field min-h-28 resize-y leading-6" value={previewText} onChange={(event) => setPreviewText(event.target.value)} maxLength={360} /><span className="mt-2 block text-right text-xs text-slate-600">{previewText.length}/360</span></label>
            {audition.isError && <p role="alert" className="mt-4 rounded-xl border border-amber-400/20 bg-amber-400/10 p-3 text-sm leading-6 text-amber-100">{audition.error instanceof Error ? audition.error.message : 'The selected voice could not be auditioned.'}</p>}
            <div className="mt-4 flex flex-col justify-between gap-4 border-t border-slate-800 pt-5 sm:flex-row sm:items-center"><p className="flex gap-2 text-xs leading-5 text-slate-500"><Sparkles className="h-4 w-4 shrink-0 text-indigo-300" />Cloud voices require their server-side audition adapter. Local Kokoro previews require locally available model files.</p><Button className="shrink-0" disabled={audition.isPending || !previewText.trim()} onClick={playAudition}>{audition.isPending ? 'Synthesizing…' : <><Play className="h-4 w-4 fill-current" />Play audition</>}</Button></div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function VoiceOption({ voice, selected, onSelect }: { voice: VoiceProfile; selected: boolean; onSelect: () => void }) {
  return <button type="button" onClick={onSelect} className={`w-full rounded-xl border p-3.5 text-left transition ${selected ? 'border-indigo-400/60 bg-indigo-500/10' : 'border-slate-800 bg-slate-950/35 hover:border-slate-600'}`}><div className="flex items-center justify-between gap-3"><div className="flex min-w-0 items-center gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-sm font-bold text-slate-200">{voice.name.charAt(0)}</span><span className="min-w-0"><span className="block truncate text-sm font-semibold text-slate-100">{voice.name}</span><span className="mt-0.5 block text-xs text-slate-500">{voice.accent} · {voice.gender}</span></span></div><Badge tone={voice.provider === 'kokoro' || voice.provider === 'piper' ? 'success' : 'neutral'}>{voice.provider}</Badge></div></button>;
}

function RangeControl({ label, value, min, max, step, suffix, onChange }: { label: string; value: number; min: number; max: number; step: number; suffix: string; onChange: (value: number) => void }) {
  return <label><span className="flex items-center justify-between gap-3"><span className="field-label">{label}</span><span className="mb-2 text-sm font-semibold text-indigo-200">{value.toFixed(step < 1 ? 2 : 0)}{suffix}</span></span><input className="h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-700 accent-indigo-400" type="range" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}

function LoadingState() { return <div className="mx-auto max-w-7xl"><div className="h-10 w-52 animate-pulse rounded-lg bg-slate-800" /><div className="mt-8 grid gap-6 xl:grid-cols-2"><div className="h-[620px] animate-pulse rounded-2xl border border-slate-800 bg-slate-900/60" /><div className="h-[620px] animate-pulse rounded-2xl border border-slate-800 bg-slate-900/60" /></div></div>; }
function ErrorState({ detail, onRetry }: { detail: string; onRetry: () => void }) { return <Card className="mx-auto mt-24 max-w-xl p-7 text-center"><Volume2 className="mx-auto h-7 w-7 text-slate-500" /><h1 className="mt-4 text-xl font-semibold text-white">Voice Studio is unavailable</h1><p className="mt-3 text-sm leading-6 text-slate-400">{detail}</p><Button className="mt-6" onClick={onRetry}>Try again</Button></Card>; }
