export type LLMProvider = 'ollama' | 'gemini' | 'groq' | 'openai';
export type TTSProvider = 'kokoro' | 'piper' | 'cartesia' | 'elevenlabs';

export interface RuntimeProviderConfig {
  provider: LLMProvider;
  model: string;
  base_url: string | null;
}

export interface ProviderOption {
  provider: LLMProvider;
  display_name: string;
  configured: boolean;
  local: boolean;
  default_model: string;
}

export interface ProviderSettingsResponse {
  active: RuntimeProviderConfig;
  providers: ProviderOption[];
  updated_at: string;
}

export interface VoiceProfile {
  voice_id: string;
  name: string;
  provider: TTSProvider;
  gender: 'female' | 'male' | 'neutral';
  accent: string;
  recommended_speed: number;
  description: string;
  role_fit: string[];
}

export interface LatencyBreakdown {
  vad_ms: number;
  stt_ms: number;
  rag_ms: number;
  llm_ms: number;
  tts_ms: number;
  total_ms: number;
  recorded_at: string;
}

export interface ServiceHealth {
  name: string;
  status: 'ready' | 'attention';
  detail: string;
}

export interface DashboardResponse {
  active_provider: RuntimeProviderConfig;
  latest_latency: LatencyBreakdown | null;
  target_latency_ms: number;
  services: ServiceHealth[];
  tool_calls_last_hour: number;
  knowledge_documents: number;
}

export interface KnowledgeDocument {
  name: string;
  tenant_id: string;
  chunks_indexed: number;
  uploaded_at: string;
  status: 'indexed';
}

export interface KnowledgeSearchChunk {
  source: string;
  excerpt: string;
  score: number;
}

export interface KnowledgeSearchResult {
  has_context: boolean;
  chunks: KnowledgeSearchChunk[];
  fallback_spoken: string | null;
}
