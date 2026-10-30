import { Keyboard, Mic, Send, Square, Volume2 } from 'lucide-react';
import { useState, type KeyboardEvent, type PointerEvent } from 'react';

import type { ConnectionStatus } from '../types';

interface DualInputBarProps {
  status: ConnectionStatus;
  onPushToTalk: (active: boolean) => void;
  onSendText: (text: string) => void;
}

/** Provides noise-friendly hold-to-talk and accessible typed fallback controls. */
export function DualInputBar({ status, onPushToTalk, onSendText }: DualInputBarProps) {
  const [message, setMessage] = useState('');
  const [isTalking, setIsTalking] = useState(false);
  const isConnected = status === 'connected';

  const setTalking = (active: boolean) => {
    if (!isConnected) return;
    setIsTalking(active);
    onPushToTalk(active);
  };
  const send = () => {
    const text = message.trim();
    if (!text || !isConnected) return;
    onSendText(text);
    setMessage('');
  };
  const onTextKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };
  const onPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    setTalking(true);
  };
  const onPointerEnd = () => setTalking(false);

  return (
    <section className="rounded-[1.6rem] border border-slate-200 bg-white p-3 shadow-lift" aria-label="Speak or type to your concierge">
      <div className="flex gap-2">
        <button
          aria-label={isTalking ? 'Release to stop talking' : 'Hold to talk'}
          aria-pressed={isTalking}
          className={`group relative grid h-12 w-12 shrink-0 place-items-center rounded-2xl transition focus:outline-none ${isTalking ? 'bg-violet-700 text-white shadow-[0_0_0_5px_rgba(139,92,246,0.18)]' : 'bg-slate-950 text-white hover:bg-violet-700'} disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400`}
          disabled={!isConnected}
          onKeyDown={(event) => { if (event.key === ' ' || event.key === 'Enter') { event.preventDefault(); setTalking(true); } }}
          onKeyUp={(event) => { if (event.key === ' ' || event.key === 'Enter') { event.preventDefault(); setTalking(false); } }}
          onPointerCancel={onPointerEnd}
          onPointerDown={onPointerDown}
          onPointerLeave={(event) => { if (event.buttons > 0) onPointerEnd(); }}
          onPointerUp={onPointerEnd}
          type="button"
        >
          {isTalking ? <Square className="h-4 w-4 fill-current" /> : <Mic className="h-5 w-5" />}
          {isTalking && <span className="absolute inset-0 -z-10 animate-pulse-ring rounded-2xl bg-violet-500" />}
        </button>
        <div className="relative min-w-0 flex-1">
          <Keyboard className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-400" />
          <input aria-label="Type a message for Elena" className="h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 pl-10 pr-10 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-violet-400 focus:bg-white focus:ring-4 focus:ring-violet-100" disabled={!isConnected} onChange={(event) => setMessage(event.target.value)} onKeyDown={onTextKeyDown} placeholder={isConnected ? 'Type a message, name, or special request…' : 'Connect to start a conversation'} value={message} />
          <button aria-label="Send typed message" className="absolute right-1.5 top-1.5 grid h-9 w-9 place-items-center rounded-xl bg-violet-600 text-white transition hover:bg-violet-700 disabled:bg-slate-200" disabled={!isConnected || !message.trim()} onClick={send} type="button"><Send className="h-4 w-4" /></button>
        </div>
      </div>
      <p className="mt-2 flex items-center gap-1.5 px-1 text-[11px] text-slate-500"><Volume2 className="h-3.5 w-3.5" />Hold the microphone to talk in busy spaces, or type privately. Press and hold only while speaking.</p>
    </section>
  );
}
