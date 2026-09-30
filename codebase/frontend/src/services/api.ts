/**
 * API Service Layer for Samsung Smart Guided Troubleshooting Engine.
 * Interacts with:
 * - GET /health
 * - POST /v1/troubleshoot
 */
import {
  ContextDeeplinkResponse,
  HealthResponse,
  TelemetryMetadata,
  TroubleshootRequest,
  TroubleshootingResult,
} from '../types';

const API_BASE = ''; // Uses Vite proxy or relative path when hosted from backend

export class ApiError extends Error {
  status: number;
  details?: any;

  constructor(message: string, status: number, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

// In-memory telemetry log for Engineering Dashboard
let telemetryHistory: TelemetryMetadata[] = [];

export const getTelemetryHistory = (): TelemetryMetadata[] => {
  return [...telemetryHistory];
};

export const clearTelemetryHistory = (): void => {
  telemetryHistory = [];
};

export async function fetchHealth(): Promise<HealthResponse> {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!res.ok) {
      if (res.status === 503) {
        throw new ApiError('Engine is initializing and prewarming cache. Please wait...', 503);
      }
      throw new ApiError(`Health check failed with status ${res.status}`, res.status);
    }

    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      `Cannot connect to backend server: ${err.message || 'Network error'}`,
      0
    );
  }
}

export async function executeTroubleshoot(
  request: TroubleshootRequest
): Promise<TroubleshootingResult> {
  const t0 = performance.now();

  try {
    const res = await fetch(`${API_BASE}/v1/troubleshoot`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(request),
    });

    const roundtripMs = Math.round((performance.now() - t0) * 10) / 10;

    // Handle HTTP error responses
    if (!res.ok) {
      let errorData: any = null;
      try {
        errorData = await res.json();
      } catch {
        // Not JSON
      }

      if (res.status === 422) {
        const detailMsg = errorData?.detail
          ? errorData.detail.map((d: any) => `${d.field}: ${d.message}`).join(', ')
          : 'Invalid request payload';
        throw new ApiError(`Validation error (422): ${detailMsg}`, 422, errorData);
      }

      if (res.status === 503) {
        throw new ApiError(
          'Engine is currently initializing models and prewarming cache. Please retry shortly.',
          503
        );
      }

      if (res.status === 400) {
        throw new ApiError('Malformed request JSON or bad parameters (400).', 400);
      }

      throw new ApiError(
        errorData?.message || `Server responded with error status ${res.status}`,
        res.status,
        errorData
      );
    }

    // Extract performance telemetry from custom response headers
    const rawProcessMs = parseFloat(res.headers.get('X-Process-Time-Ms') || '0');
    const cacheHitHeader = res.headers.get('X-Cache-Hit') === 'true';
    const cacheTypeHeader = (res.headers.get('X-Cache-Type') || 'miss') as 'exact' | 'semantic' | 'miss';
    const extractionPathHeader = (res.headers.get('X-Extraction-Path') || 'cold_path') as 'cache' | 'cold_path';
    const nbeSufficient = res.headers.get('X-NBE-Sufficient') === 'true';
    const nbeEntropy = parseFloat(res.headers.get('X-NBE-Entropy') || '0');
    const nbeConfidence = parseFloat(res.headers.get('X-NBE-Confidence') || '1.0');
    const nbeEig = parseFloat(res.headers.get('X-NBE-EIG') || '0');

    const telemetry: TelemetryMetadata = {
      processTimeMs: Math.round(rawProcessMs * 1000) / 1000,
      cacheHit: cacheHitHeader,
      cacheType: cacheTypeHeader,
      extractionPath: extractionPathHeader,
      roundtripMs,
      timestamp: new Date().toLocaleTimeString(),
      nbeSufficient,
      nbeEntropy,
      nbeConfidence,
      nbeEig,
    };

    // Store in telemetry history (keep latest 50 entries)
    telemetryHistory = [telemetry, ...telemetryHistory.slice(0, 49)];

    const response: ContextDeeplinkResponse = await res.json();

    return {
      response,
      telemetry,
    };
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      `Network connection failed. Ensure the FastAPI backend is running: ${err.message}`,
      0
    );
  }
}
