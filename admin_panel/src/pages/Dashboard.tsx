import { ArrowRight, Bot, BookOpenText, Cable, RefreshCw, ShieldCheck, Waves } from 'lucide-react';
import type { ReactNode } from 'react';

import { LatencyWaterfall } from '../components/LatencyWaterfall';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { useDashboard } from '../hooks/useAdminApi';

interface DashboardProps {
  onOpenProviders: () => void;
}

/** Live operational overview for the active enterprise voice deployment. */
export function Dashboard({ onOpenProviders }: DashboardProps) {
  const dashboard = useDashboard();

  if (dashboard.isLoading) {
    return <DashboardLoading />;
  }

  if (dashboard.isError || !dashboard.data) {
    return (
      <FailureState
        title="The command center could not reach the Admin API"
        detail={dashboard.error instanceof Error ? dashboard.error.message : 'Start the backend on port 8000, then refresh the console.'}
        onRetry={() => void dashboard.refetch()}
      />
    );
  }

  const data = dashboard.data;
  return (
    <div className="mx-auto max-w-7xl animate-in fade-in duration-500">
      <header className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold text-indigo-300">OPERATIONS OVERVIEW</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Voice operations, at a glance.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">Monitor the active model, confirmation safeguards, knowledge readiness, and every measured voice-turn milestone.</p>
        </div>
        <Button variant="secondary" onClick={() => void dashboard.refetch()}><RefreshCw className="h-4 w-4" />Refresh</Button>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Active model" value={data.active_provider.model} detail={data.active_provider.provider} icon={<Bot className="h-5 w-5" />} tone="indigo" />
        <MetricCard label="Latest turn" value={data.latest_latency ? `${Math.round(data.latest_latency.total_ms)} ms` : 'No turns yet'} detail={data.latest_latency ? 'Measured end to end' : 'Waiting for telemetry'} icon={<Waves className="h-5 w-5" />} tone="cyan" />
        <MetricCard label="Knowledge documents" value={String(data.knowledge_documents)} detail="Grand Meridian tenant" icon={<BookOpenText className="h-5 w-5" />} tone="violet" />
        <MetricCard label="MCP calls" value={String(data.tool_calls_last_hour)} detail="Past 60 minutes" icon={<Cable className="h-5 w-5" />} tone="emerald" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.45fr_0.9fr]">
        <Card className="p-5 sm:p-7">
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h2 className="section-title">Latency waterfall</h2>
              <p className="section-copy">Every stage contributes to the 800 ms operational target.</p>
            </div>
            <Badge tone="accent">Live polling</Badge>
          </div>
          <LatencyWaterfall metrics={data.latest_latency} targetMs={data.target_latency_ms} />
        </Card>

        <Card className="p-5 sm:p-7">
          <h2 className="section-title">Service readiness</h2>
          <p className="section-copy">Configuration state is checked without revealing keys.</p>
          <ul className="mt-6 space-y-3">
            {data.services.map((service) => (
              <li key={service.name} className="rounded-xl border border-slate-800 bg-slate-950/45 p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-slate-100">{service.name}</span>
                  <Badge tone={service.status === 'ready' ? 'success' : 'warning'}>{service.status === 'ready' ? 'Ready' : 'Attention'}</Badge>
                </div>
                <p className="mt-2 text-sm leading-5 text-slate-500">{service.detail}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="mt-6 flex flex-col justify-between gap-4 border-indigo-400/20 bg-gradient-to-r from-indigo-500/[0.12] via-slate-950/60 to-cyan-500/[0.08] p-5 sm:flex-row sm:items-center sm:p-6">
        <div className="flex gap-3">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" aria-hidden="true" />
          <div>
            <h2 className="font-semibold text-white">Writes stay confirmation-gated</h2>
            <p className="mt-1 text-sm leading-6 text-slate-400">Changing a model affects future sessions only. Bookings, cancellations, payments, and messages still require the caller’s spoken confirmation.</p>
          </div>
        </div>
        <Button variant="secondary" onClick={onOpenProviders}>Manage providers <ArrowRight className="h-4 w-4" /></Button>
      </Card>
    </div>
  );
}

function MetricCard({ label, value, detail, icon, tone }: { label: string; value: string; detail: string; icon: ReactNode; tone: 'indigo' | 'cyan' | 'violet' | 'emerald' }) {
  const tones = {
    indigo: 'border-indigo-400/20 bg-indigo-400/10 text-indigo-200',
    cyan: 'border-cyan-400/20 bg-cyan-400/10 text-cyan-200',
    violet: 'border-violet-400/20 bg-violet-400/10 text-violet-200',
    emerald: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200',
  };
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3"><span className="text-sm font-medium text-slate-400">{label}</span><span className={`rounded-lg border p-2 ${tones[tone]}`}>{icon}</span></div>
      <p className="mt-5 truncate text-2xl font-semibold tracking-tight text-white" title={value}>{value}</p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </Card>
  );
}

function DashboardLoading() {
  return <div className="mx-auto max-w-7xl"><div className="h-10 w-80 animate-pulse rounded-lg bg-slate-800" /><div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((item) => <div key={item} className="h-36 animate-pulse rounded-2xl border border-slate-800 bg-slate-900/60" />)}</div><div className="mt-6 h-96 animate-pulse rounded-2xl border border-slate-800 bg-slate-900/50" /></div>;
}

function FailureState({ title, detail, onRetry }: { title: string; detail: string; onRetry: () => void }) {
  return <Card className="mx-auto mt-24 max-w-xl p-7 text-center"><h1 className="text-xl font-semibold text-white">{title}</h1><p className="mt-3 text-sm leading-6 text-slate-400">{detail}</p><Button className="mt-6" onClick={onRetry}>Try again</Button></Card>;
}
