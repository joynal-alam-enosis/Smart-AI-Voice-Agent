import { useState, type ReactElement } from 'react';

import { AppShell, type AdminView } from './components/AppShell';
import { Dashboard } from './pages/Dashboard';
import { KnowledgeHub } from './pages/KnowledgeHub';
import { ProviderSettings } from './pages/ProviderSettings';
import { VoiceStudio } from './pages/VoiceStudio';

/** Root application that preserves navigation locally and delegates server state to TanStack Query. */
export function App() {
  const [activeView, setActiveView] = useState<AdminView>('dashboard');
  const content = {
    dashboard: <Dashboard onOpenProviders={() => setActiveView('provider-settings')} />,
    'voice-studio': <VoiceStudio />,
    'knowledge-hub': <KnowledgeHub />,
    'provider-settings': <ProviderSettings />,
  } satisfies Record<AdminView, ReactElement>;

  return <AppShell activeView={activeView} onViewChange={setActiveView}>{content[activeView]}</AppShell>;
}
