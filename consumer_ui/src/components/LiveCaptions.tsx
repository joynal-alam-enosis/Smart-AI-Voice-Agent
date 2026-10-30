import { Captions, MessageCircleMore, UserRound } from 'lucide-react';

import type { CaptionLine } from '../types';

interface LiveCaptionsProps {
  captions: CaptionLine[];
}

/** Accessible live transcript with clear speaker attribution and empty-state guidance. */
export function LiveCaptions({ captions }: LiveCaptionsProps) {
  return (
    <section className="min-h-[14rem] rounded-[1.6rem] border border-slate-200/90 bg-white/80 p-5 shadow-sm backdrop-blur" aria-labelledby="captions-heading">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="eyebrow">Conversation</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950" id="captions-heading">Live captions</h2>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600">
          <Captions className="h-3.5 w-3.5" /> Live transcript
        </span>
      </div>
      <div className="mt-5 space-y-4" aria-live="polite" aria-relevant="additions text">
        {captions.length === 0 ? (
          <div className="flex min-h-24 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 px-5 text-center">
            <MessageCircleMore className="h-5 w-5 text-slate-400" />
            <p className="mt-2 text-sm font-medium text-slate-600">Captions will appear as your conversation begins.</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">You can speak, hold Push to Talk, or use the text field below.</p>
          </div>
        ) : (
          captions.map((caption) => (
            <div className="flex gap-3" key={caption.id}>
              <span className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full ${caption.speaker === 'agent' ? 'bg-violet-100 text-violet-700' : 'bg-teal-100 text-teal-700'}`}>
                {caption.speaker === 'agent' ? <span className="text-xs font-bold">E</span> : <UserRound className="h-3.5 w-3.5" />}
              </span>
              <p className="pt-1 text-sm leading-6 text-slate-700">
                <span className="mr-2 font-semibold text-slate-950">{caption.speaker === 'agent' ? 'Elena' : 'You'}</span>
                {caption.text}
                {!caption.isFinal && <span className="ml-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-violet-500" aria-label="Caption is still streaming" />}
              </p>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
