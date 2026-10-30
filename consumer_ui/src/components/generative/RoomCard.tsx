import { BedDouble, Check, Sparkles } from 'lucide-react';

import type { RoomCardModel } from '../../types';

interface RoomCardProps {
  room: RoomCardModel;
  selected: boolean;
  onSelect: (room: RoomCardModel) => void;
}

/** A visual room recommendation that syncs a tap back to the voice agent. */
export function RoomCard({ room, selected, onSelect }: RoomCardProps) {
  const price = new Intl.NumberFormat('en-US', { style: 'currency', currency: room.currency, maximumFractionDigits: 0 }).format(room.price_per_night);
  return (
    <article className={`overflow-hidden rounded-[1.45rem] border bg-white transition-all ${selected ? 'border-violet-400 shadow-[0_12px_30px_rgba(109,40,217,0.16)]' : 'border-slate-200 shadow-sm hover:-translate-y-0.5 hover:shadow-lift'}`}>
      <div className="relative h-28 overflow-hidden bg-gradient-to-br from-slate-950 via-violet-950 to-indigo-700">
        {room.image_url ? <img className="h-full w-full object-cover" src={room.image_url} alt="" /> : <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_20%,rgba(196,181,253,0.75),transparent_18%),radial-gradient(circle_at_28%_110%,rgba(45,212,191,0.42),transparent_32%)]" />}
        <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur">
          <Sparkles className="h-3 w-3" /> Curated for you
        </span>
        <span className="absolute bottom-3 right-3 rounded-lg bg-white px-2.5 py-1 text-sm font-bold text-slate-950">{price}<span className="ml-0.5 text-[10px] font-medium text-slate-500">/ night</span></span>
      </div>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-slate-950">{room.name}</h3>
            <p className="mt-1 flex items-center gap-1.5 text-xs text-slate-500"><BedDouble className="h-3.5 w-3.5" />{room.bed_label}</p>
          </div>
          {room.availability_label && <span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-700">{room.availability_label}</span>}
        </div>
        <p className="mt-3 line-clamp-2 text-sm leading-5 text-slate-600">{room.description}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {room.amenities.slice(0, 3).map((amenity) => <span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-medium text-slate-600" key={amenity}>{amenity}</span>)}
        </div>
        <button className={`mt-4 flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${selected ? 'bg-violet-100 text-violet-800' : 'bg-slate-950 text-white hover:bg-violet-700'}`} onClick={() => onSelect(room)} type="button">
          {selected ? <><Check className="h-4 w-4" /> Selected — tell Elena</> : 'Choose this room'}
        </button>
      </div>
    </article>
  );
}
