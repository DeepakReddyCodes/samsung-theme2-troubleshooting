import React from 'react';
import { Zap, Clock, Database, GitBranch, ShieldCheck, Sparkles } from 'lucide-react';
import { TelemetryMetadata } from '../types';

interface TelemetryHUDProps {
  telemetry: TelemetryMetadata | null;
  score?: number;
}

export const TelemetryHUD: React.FC<TelemetryHUDProps> = ({ telemetry, score }) => {
  if (!telemetry) return null;

  const isCacheHit = telemetry.cacheHit;
  const isExact = telemetry.cacheType === 'exact';
  const isSemantic = telemetry.cacheType === 'semantic';

  return (
    <div className="telemetry-hud">
      <div className="telemetry-badge-group">
        {/* Cache status badge */}
        <div
          className={`telemetry-item ${
            isCacheHit ? 'telemetry-item-hit' : 'telemetry-item-miss'
          }`}
        >
          <Zap size={14} />
          <span>
            {isCacheHit
              ? `Cache HIT (${isExact ? 'Tier 1 Exact' : 'Tier 2 Semantic'})`
              : 'Cache MISS (Cold Path)'}
          </span>
        </div>

        {/* Process time */}
        <div className="telemetry-item">
          <Clock size={14} />
          <span>
            Backend Latency: <strong>{telemetry.processTimeMs} ms</strong>
          </span>
        </div>

        {/* Roundtrip */}
        <div className="telemetry-item">
          <Database size={14} />
          <span>
            E2E Socket: <strong>{telemetry.roundtripMs} ms</strong>
          </span>
        </div>

        {/* Extraction path */}
        <div className="telemetry-item">
          <GitBranch size={14} />
          <span>
            Path: <strong>{telemetry.extractionPath}</strong>
          </span>
        </div>

        {/* NBE Information Gain / Entropy Badge */}
        {telemetry.nbeEntropy !== undefined && (
          <div className="telemetry-item telemetry-item-nbe" title="Next-Best-Evidence Information Theoretic Disambiguation">
            <Sparkles size={14} className="text-purple" />
            <span>
              NBE Entropy: <strong>{telemetry.nbeEntropy.toFixed(2)} bits</strong> (EIG: {telemetry.nbeEig?.toFixed(3) || '0.000'})
            </span>
          </div>
        )}

        {/* Score */}
        {score !== undefined && (
          <div className="telemetry-item telemetry-item-score">
            <ShieldCheck size={14} className="text-samsung-blue" />
            <span>
              Confidence: <strong>{Math.round(score * 100)}%</strong>
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
