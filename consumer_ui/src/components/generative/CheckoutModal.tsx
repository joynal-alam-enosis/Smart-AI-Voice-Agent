import { ArrowUpRight, CreditCard, LockKeyhole, ShieldCheck, X } from 'lucide-react';
import { useEffect, useRef } from 'react';

interface CheckoutModalProps {
  open: boolean;
  amount?: number;
  currency?: string;
  description?: string;
  paymentCollectionAvailable: boolean;
  onClose: () => void;
  onRequestSecureCheckout: () => void;
}

/**
 * A PCI-safe handoff surface. It intentionally has no card-number fields:
 * payment providers must supply their own hosted UI in a later integration.
 */
export function CheckoutModal({
  open,
  amount,
  currency = 'USD',
  description,
  paymentCollectionAvailable,
  onClose,
  onRequestSecureCheckout,
}: CheckoutModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (!open) return undefined;
    closeButtonRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [onClose, open]);
  if (!open) return null;
  const formattedAmount = amount === undefined ? null : new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-4 backdrop-blur-sm" role="presentation">
      <section aria-describedby="checkout-description" aria-labelledby="checkout-heading" aria-modal="true" className="w-full max-w-md rounded-[1.8rem] border border-white/40 bg-white p-6 shadow-2xl" role="dialog">
        <div className="flex items-start justify-between gap-4">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-emerald-100 text-emerald-700"><LockKeyhole className="h-5 w-5" /></div>
          <button aria-label="Close secure checkout" className="rounded-xl p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900" onClick={onClose} ref={closeButtonRef} type="button"><X className="h-5 w-5" /></button>
        </div>
        <p className="eyebrow mt-5">Protected checkout</p>
        <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950" id="checkout-heading">Payment stays private</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600" id="checkout-description">{description ?? 'When available, a secure provider opens its own payment experience here while Elena stays with you.'}</p>
        <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center justify-between gap-4"><span className="text-sm font-medium text-slate-600">Deposit</span><strong className="text-lg text-slate-950">{formattedAmount ?? 'To be confirmed'}</strong></div>
          <div className="mt-4 flex items-center gap-2 border-t border-slate-200 pt-3 text-xs leading-5 text-slate-500"><ShieldCheck className="h-4 w-4 shrink-0 text-emerald-600" />Never say or type a card number, CVV, or bank details into this conversation.</div>
        </div>
        {paymentCollectionAvailable ? (
          <button className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-violet-700" onClick={onRequestSecureCheckout} type="button"><CreditCard className="h-4 w-4" /> Continue in secure checkout <ArrowUpRight className="h-4 w-4" /></button>
        ) : (
          <div className="mt-5 rounded-xl bg-amber-50 px-4 py-3 text-sm leading-5 text-amber-900">Secure payment handoff is not configured in this local environment. Elena can still help you review the reservation.</div>
        )}
      </section>
    </div>
  );
}
