import React, { useState } from 'react';
import {
  Search,
  Sparkles,
  Sliders,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  FileCode,
  Copy,
  Check,
  Send,
} from 'lucide-react';
import { CANONICAL_SCENARIOS } from '../data/canonical_scenarios';
import {
  Action,
  ContextDeeplinkResponse,
  Deeplink,
  SIISResponse,
  TelemetryMetadata,
  TroubleshootRequest,
  ValidationDeeplink,
} from '../types';
import { ActionCard } from './ActionCard';
import { DeeplinkModal } from './DeeplinkModal';
import { TelemetryHUD } from './TelemetryHUD';

// Curated sample paraphrases for canonical scenarios
const SAMPLE_PARAPHRASES: Record<string, string[]> = {
  row_1: [
    'My tablet cannot connect to email servers or load any incoming emails',
    'Email app fails to connect to server and goes blank on Galaxy tablet',
  ],
  row_2: [
    'Galaxy S22 screen is totally blank and no apps show any picture',
    'Phone display stays solid white with no text appearing on screen',
  ],
  row_4: [
    'Galaxy A15 screen went totally pitch black and will not power on',
    'My display turned completely dark and unresponsive after one month',
  ],
  row_14: [
    'Phone display is completely broken with cracked glass and need to save data',
    'Screen shattered and I need to back up my files before Samsung repair',
  ],
  row_20: [
    'How do I lock screen orientation so it stops auto rotating',
    'Screen orientation keeps rotating automatically on my Galaxy phone',
  ],
  row_21: [
    'Touch response is very laggy and slow on my Galaxy S22',
    'Screen input delay is noticeable when tapping the display',
  ],
};

interface TroubleshootingViewProps {
  onTroubleshoot: (req: TroubleshootRequest) => Promise<void>;
  loading: boolean;
  result: ContextDeeplinkResponse | null;
  telemetry: TelemetryMetadata | null;
  error: string | null;
  onClear: () => void;
}

export const TroubleshootingView: React.FC<TroubleshootingViewProps> = ({
  onTroubleshoot,
  loading,
  result,
  telemetry,
  error,
  onClear,
}) => {
  // Active inputs
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('row_1');
  const [query, setQuery] = useState<string>(CANONICAL_SCENARIOS[0].original_query);
  const [siisTitle, setSiisTitle] = useState<string>(
    CANONICAL_SCENARIOS[0].siis_response.title
  );
  const [siisContent, setSiisContent] = useState<string>(
    CANONICAL_SCENARIOS[0].siis_response.content
  );
  const [showDeveloperPanel, setShowDeveloperPanel] = useState<boolean>(false);
  const [copiedJson, setCopiedJson] = useState<boolean>(false);

  // Active Deeplink Modal State
  const [modalDeeplink, setModalDeeplink] = useState<Deeplink | null>(null);
  const [modalValidation, setModalValidation] = useState<ValidationDeeplink | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  // Handle Scenario Select
  const handleSelectScenario = (scId: string) => {
    setSelectedScenarioId(scId);
    const found = CANONICAL_SCENARIOS.find((s) => s.id === scId);
    if (found) {
      setQuery(found.original_query);
      setSiisTitle(found.siis_response.title);
      setSiisContent(found.siis_response.content);
      onClear();
    }
  };

  // Quick paraphrase select
  const handleApplyParaphrase = (paraText: string) => {
    setQuery(paraText);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    await onTroubleshoot({
      query: query.trim(),
      siis_response: {
        title: siisTitle.trim() || 'Device Support',
        content: siisContent.trim() || 'Check Samsung device settings.',
      },
    });
  };

  const handleOpenDeeplinkModal = (dl: Deeplink, val?: ValidationDeeplink | null) => {
    setModalDeeplink(dl);
    setModalValidation(val || null);
    setIsModalOpen(true);
  };

  const handleCopyJson = () => {
    if (result) {
      navigator.clipboard.writeText(JSON.stringify(result, null, 2));
      setCopiedJson(true);
      setTimeout(() => setCopiedJson(false), 2000);
    }
  };

  const activeParaphrases = SAMPLE_PARAPHRASES[selectedScenarioId] || [];
  const activeGoal = result?.contexts?.[0];

  return (
    <div className="troubleshoot-view">
      {/* Input Section */}
      <section className="input-card">
        {/* Scenario selector bar */}
        <div className="scenario-bar">
          <div className="scenario-label-group">
            <Sliders size={16} className="text-samsung-blue" />
            <span className="scenario-title">Benchmark Scenarios:</span>
          </div>
          <select
            className="scenario-select"
            value={selectedScenarioId}
            onChange={(e) => handleSelectScenario(e.target.value)}
          >
            {CANONICAL_SCENARIOS.map((sc) => (
              <option key={sc.id} value={sc.id}>
                {sc.label}
              </option>
            ))}
          </select>
        </div>

        {/* Main query input */}
        <form onSubmit={handleSubmit} className="query-form">
          <div className="query-input-wrapper">
            <label htmlFor="user-query" className="input-label">
              Describe your device issue:
            </label>
            <textarea
              id="user-query"
              className="query-textarea"
              rows={3}
              placeholder="e.g. My Galaxy screen is blank when I open Gmail, or touch inputs are delayed..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
          </div>

          {/* Quick Paraphrase Pill Buttons */}
          {activeParaphrases.length > 0 && (
            <div className="paraphrase-bar">
              <span className="paraphrase-label">
                <Sparkles size={13} className="text-samsung-blue" />
                <span>Test Paraphrase Cache:</span>
              </span>
              <div className="paraphrase-buttons">
                {activeParaphrases.map((para, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="btn-paraphrase"
                    onClick={() => handleApplyParaphrase(para)}
                    title="Load paraphrase to observe Tier 2 semantic cache hit"
                  >
                    "{para.length > 45 ? para.slice(0, 45) + '...' : para}"
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Collapsible Developer / SIIS Context toggle */}
          <div className="developer-toggle-row">
            <button
              type="button"
              className="btn-dev-toggle"
              onClick={() => setShowDeveloperPanel(!showDeveloperPanel)}
            >
              <span>SIIS Knowledge Grounding Context ({siisTitle})</span>
              {showDeveloperPanel ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
          </div>

          {showDeveloperPanel && (
            <div className="developer-panel">
              <div className="dev-input-group">
                <label className="dev-label">SIIS Document Title:</label>
                <input
                  type="text"
                  className="dev-input"
                  value={siisTitle}
                  onChange={(e) => setSiisTitle(e.target.value)}
                  placeholder="e.g. Blank or black display on a Samsung phone"
                />
              </div>
              <div className="dev-input-group">
                <label className="dev-label">SIIS Full Content (Source of Truth):</label>
                <textarea
                  className="dev-textarea"
                  rows={4}
                  value={siisContent}
                  onChange={(e) => setSiisContent(e.target.value)}
                  placeholder="Paste raw markdown troubleshooting article..."
                />
              </div>
              <p className="dev-help-text">
                The engine strictly grounds all steps and actions in this SIIS text.
                Modifying this allows testing cold-path knowledge extraction on custom scenarios.
              </p>
            </div>
          )}

          {/* Action buttons */}
          <div className="form-action-bar">
            <button
              type="button"
              className="btn-reset"
              onClick={() => {
                const found = CANONICAL_SCENARIOS.find((s) => s.id === selectedScenarioId);
                if (found) {
                  setQuery(found.original_query);
                  setSiisTitle(found.siis_response.title);
                  setSiisContent(found.siis_response.content);
                }
                onClear();
              }}
              disabled={loading}
            >
              <RotateCcw size={16} />
              <span>Reset</span>
            </button>
            <button type="submit" className="btn-submit" disabled={loading || !query.trim()}>
              {loading ? (
                <>
                  <span className="spinner" />
                  <span>Synthesizing Plan...</span>
                </>
              ) : (
                <>
                  <Send size={16} />
                  <span>Diagnose & Troubleshoot</span>
                </>
              )}
            </button>
          </div>
        </form>
      </section>

      {/* Error Banner */}
      {error && (
        <section className="error-banner">
          <AlertCircle size={20} className="text-rose" />
          <div className="error-content">
            <h4>Troubleshooting Diagnosis Failed</h4>
            <p>{error}</p>
          </div>
        </section>
      )}

      {/* Results Section */}
      {result && activeGoal && (
        <section className="results-container">
          {/* Telemetry HUD */}
          <TelemetryHUD telemetry={telemetry} score={activeGoal.score} />

          {/* Goal Overview Card */}
          <div className="goal-banner">
            <div className="goal-header-row">
              <span className="goal-label">Synthesized Resolution Plan</span>
              <button
                className="btn-copy-json"
                onClick={handleCopyJson}
                title="Copy raw JSON response conforming to ContextDeeplinkResponse"
              >
                {copiedJson ? (
                  <>
                    <Check size={14} className="text-emerald" />
                    <span>Copied JSON</span>
                  </>
                ) : (
                  <>
                    <FileCode size={14} />
                    <span>Copy API JSON</span>
                  </>
                )}
              </button>
            </div>
            <h2 className="goal-title">{activeGoal.title}</h2>
            <div className="goal-regex-row">
              <code className="goal-regex-code">{activeGoal.goal}</code>
            </div>
          </div>

          {/* Ordered Actions List */}
          <div className="actions-list">
            <div className="actions-header">
              <h3>
                Recommended Actions ({activeGoal.actions.length} Phase-Ordered Steps)
              </h3>
              <span className="action-hierarchy-hint">
                Order: Automated Settings → Manual Checks → Critical Recovery
              </span>
            </div>

            {activeGoal.actions.map((action, idx) => (
              <ActionCard
                key={idx}
                action={action}
                index={idx}
                onOpenDeeplink={handleOpenDeeplinkModal}
              />
            ))}
          </div>

          {/* Completion Celebration State */}
          <div className="all-steps-completed-box">
            <CheckCircle2 size={24} className="text-emerald" />
            <div>
              <h4>Troubleshooting Guidance Ready</h4>
              <p>
                Follow each sequential action above. Direct Settings links can be launched on supported Galaxy OneUI devices.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Deeplink Inspection Modal */}
      <DeeplinkModal
        isOpen={isModalOpen}
        deeplink={modalDeeplink}
        validation={modalValidation}
        onClose={() => setIsModalOpen(false)}
      />
    </div>
  );
};
