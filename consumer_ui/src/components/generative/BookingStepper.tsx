import { CalendarDays, Check, CircleUserRound, Hotel, ShieldCheck } from 'lucide-react';

import type { BookingStepId, BookingStepState } from '../../types';

interface BookingStepperProps {
  booking: BookingStepState | null;
  onAskForConfirmation: () => void;
}

const steps: Array<{ id: BookingStepId; label: string; icon: typeof CalendarDays }> = [
  { id: 'dates', label: 'Dates', icon: CalendarDays },
  { id: 'room', label: 'Room', icon: Hotel },
  { id: 'guest', label: 'Guest', icon: CircleUserRound },
  { id: 'confirmation', label: 'Confirm', icon: ShieldCheck },
];

/** Shows the current reservation state without ever presenting screen confirmation as a booking commit. */
export function BookingStepper({ booking, onAskForConfirmation }: BookingStepperProps) {
  const currentIndex = booking ? steps.findIndex((step) => step.id === booking.current_step) : -1;
  const total = booking?.total && booking.currency ? new Intl.NumberFormat('en-US', { style: 'currency', currency: booking.currency }).format(booking.total) : null;
  return (
    <section className="rounded-[1.6rem] border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="booking-heading">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Reservation</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950" id="booking-heading">Your stay, in view</h2>
        </div>
        <span className="rounded-full bg-violet-50 px-3 py-1.5 text-xs font-semibold text-violet-700">{booking ? 'In progress' : 'Waiting for details'}</span>
      </div>
      <ol className="mt-6 grid grid-cols-4 gap-1" aria-label="Reservation progress">
        {steps.map((step, index) => {
          const Icon = step.icon;
          const isComplete = currentIndex > index;
          const isCurrent = currentIndex === index;
          return <li className="relative text-center" key={step.id}>
            {index !== 0 && <span className={`absolute right-1/2 top-4 -z-0 h-px w-full ${isComplete || isCurrent ? 'bg-violet-400' : 'bg-slate-200'}`} />}
            <span className={`relative z-10 mx-auto grid h-8 w-8 place-items-center rounded-full border ${isComplete ? 'border-violet-600 bg-violet-600 text-white' : isCurrent ? 'border-violet-500 bg-violet-50 text-violet-700' : 'border-slate-200 bg-white text-slate-400'}`}>
              {isComplete ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
            </span>
            <span className={`mt-2 block text-[10px] font-semibold ${isCurrent ? 'text-violet-700' : 'text-slate-500'}`}>{step.label}</span>
          </li>;
        })}
      </ol>
      {booking ? <div className="mt-6 rounded-2xl bg-slate-50 p-4 text-sm">
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-slate-600">
          <p><span className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400">Stay</span>{booking.check_in && booking.check_out ? `${booking.check_in} — ${booking.check_out}` : 'Dates not set'}</p>
          <p><span className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400">Guests</span>{booking.guest_count ? `${booking.guest_count} guest${booking.guest_count === 1 ? '' : 's'}` : 'Not set'}</p>
          <p className="col-span-2"><span className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400">Room</span>{booking.room_name ?? 'Not selected'}</p>
        </div>
        {total && <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3"><span className="font-medium text-slate-600">Estimated total</span><strong className="text-slate-950">{total}</strong></div>}
      </div> : <p className="mt-6 rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">As Elena confirms dates, room, and guest details, each verified item will appear here.</p>}
      <button className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-violet-200 bg-violet-50 px-4 py-2.5 text-sm font-semibold text-violet-800 transition hover:bg-violet-100" onClick={onAskForConfirmation} type="button">
        <ShieldCheck className="h-4 w-4" /> Ask Elena about voice confirmation
      </button>
      <p className="mt-2 text-center text-[11px] leading-4 text-slate-500">For your security, reservations only finalize after your clear spoken confirmation.</p>
    </section>
  );
}
