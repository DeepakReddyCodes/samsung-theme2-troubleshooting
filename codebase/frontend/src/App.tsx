import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { TroubleshootingView } from './components/TroubleshootingView';
import { DashboardView } from './components/DashboardView';
import { fetchHealth, executeTroubleshoot, ApiError } from './services/api';
import {
  ContextDeeplinkResponse,
  HealthResponse,
  TelemetryMetadata,
  TroubleshootRequest,
} from './types';
import './styles/index.css';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'troubleshoot' | 'dashboard'>('troubleshoot');

  // Backend Health State
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [healthError, setHealthError] = useState<string | null>(null);

  // Troubleshooting Execution State
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<ContextDeeplinkResponse | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryMetadata | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Initial health check
  const loadHealth = async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch (err: any) {
      setHealthError(err.message || 'Cannot connect to backend');
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
  }, []);

  // Handle Troubleshoot API execution
  const handleTroubleshoot = async (request: TroubleshootRequest) => {
    setLoading(true);
    setError(null);
    try {
      const res = await executeTroubleshoot(request);
      setResult(res.response);
      setTelemetry(res.telemetry);
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
      setResult(null);
      setTelemetry(null);
    } finally {
      setLoading(false);
    }
  };

  const handleClearResults = () => {
    setResult(null);
    setTelemetry(null);
    setError(null);
  };

  return (
    <div className="app-root">
      {/* Navigation Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={health}
        healthLoading={healthLoading}
        healthError={healthError}
        onRefreshHealth={loadHealth}
      />

      {/* Main Content Area */}
      <main className="main-content">
        <div className="main-container">
          {activeTab === 'troubleshoot' ? (
            <TroubleshootingView
              onTroubleshoot={handleTroubleshoot}
              loading={loading}
              result={result}
              telemetry={telemetry}
              error={error}
              onClear={handleClearResults}
            />
          ) : (
            <DashboardView
              health={health}
              healthLoading={healthLoading}
              onRefreshHealth={loadHealth}
              lastTelemetry={telemetry}
            />
          )}
        </div>
      </main>

      {/* Professional Hackathon Prototype Footer */}
      <footer className="footer-root">
        <div className="footer-container">
          <div className="footer-left">
            <span className="footer-tag">Samsung PRISM GenAI Hackathon Y2026</span>
            <span className="footer-divider">•</span>
            <span>Theme 02: Smart Guided Troubleshooting Engine</span>
          </div>
          <div className="footer-right">
            <span>Authoritative SIIS & Deeplinks Catalog Grounded</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
