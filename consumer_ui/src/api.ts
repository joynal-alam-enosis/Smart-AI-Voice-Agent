import type { ConsumerConfiguration } from './types';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? 'http://127.0.0.1:8000';

/** Retrieve safe, tenant-specific browser configuration from the local gateway. */
export async function fetchConsumerConfiguration(tenantId: string): Promise<ConsumerConfiguration> {
  const response = await fetch(`${apiBaseUrl}/api/v1/voice/config?tenant_id=${encodeURIComponent(tenantId)}`);
  if (!response.ok) throw new Error('The concierge configuration is unavailable right now.');
  return (await response.json()) as ConsumerConfiguration;
}

export function getVoiceApiBaseUrl(): string {
  return apiBaseUrl;
}
