/**
 * Type definitions for Samsung Smart Guided Troubleshooting Engine Frontend.
 * Faithfully mirrors the authoritative backend Pydantic schemas.
 */

export interface Deeplink {
  deeplink: string;
  description: string;
  message?: string;
  classes?: Record<string, string>;
  originalType?: string;
}

export type ResultType = 'boolean' | 'integer' | 'str' | 'float';
export type ConditionType = 'greater' | 'equal' | 'less';

export interface ValidationDeeplink {
  deeplink: string;
  key: string;
  resultType?: ResultType;
  condition?: ConditionType;
  value?: string;
}

export interface StepGroup {
  steps: string[];
  validationDeeplink?: ValidationDeeplink | null;
  actionableDeeplink?: Deeplink | null;
}

export type ActionCategory = 'auto' | 'manual' | 'critical';

export interface Action {
  actionName: string;
  description: string;
  stepGroups: StepGroup[];
  category?: ActionCategory;
}

export interface Goal {
  goal: string;
  title: string;
  actions: Action[];
  score: number;
}

export interface ContextDeeplinkResponse {
  contexts: Goal[];
}

export interface SIISResponse {
  title: string;
  content: string;
}

export interface TroubleshootRequest {
  query: string;
  siis_response: SIISResponse;
}

export interface HealthResponse {
  status: string;
  ready: boolean;
  version: string;
  catalog_size: number;
  cache_entries: number;
  startup_time_s: number;
}

export interface TelemetryMetadata {
  processTimeMs: number;
  cacheHit: boolean;
  cacheType: 'exact' | 'semantic' | 'miss';
  extractionPath: 'cache' | 'cold_path';
  roundtripMs: number;
  timestamp: string;
  scenarioId?: string;
}

export interface TroubleshootingResult {
  response: ContextDeeplinkResponse;
  telemetry: TelemetryMetadata;
}

export interface CanonicalScenario {
  id: string;
  label: string;
  original_query: string;
  siis_response: SIISResponse;
  summary: string;
}
