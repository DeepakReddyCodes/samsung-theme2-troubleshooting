import React from 'react';
import { Activity, ShieldCheck, AlertCircle, Wrench, BarChart3, Moon, Sun, Sparkles, Download } from 'lucide-react';
import { HealthResponse } from '../types';

interface HeaderProps {
  activeTab: 'troubleshoot' | 'dashboard';
  setActiveTab: (tab: 'troubleshoot' | 'dashboard') => void;
  health: HealthResponse | null;
  healthLoading: boolean;
  healthError: string | null;
  onRefreshHealth: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  health,
  healthLoading,
  healthError,
  onRefreshHealth,
}) => {
  return (
    <header className="header-root">
      <div className="header-container">
        {/* Brand identity */}
        <div className="header-brand">
          <div className="brand-logo-badge">
            <Sparkles className="icon-sparkle" size={20} />
          </div>
          <div>
            <div className="brand-title-row">
              <span className="brand-title">SmartGuide</span>
              <span className="brand-badge">Theme 02 Engine</span>
            </div>
            <p className="brand-subtitle">
              Samsung PRISM GenAI Hackathon Y2026 • Guided Troubleshooting
            </p>
          </div>
        </div>

        {/* Navigation tabs */}
        <nav className="header-nav">
          <button
            className={`nav-tab ${activeTab === 'troubleshoot' ? 'nav-tab-active' : ''}`}
            onClick={() => setActiveTab('troubleshoot')}
          >
            <Wrench size={16} />
            <span>Troubleshooter</span>
          </button>
          <button
            className={`nav-tab ${activeTab === 'dashboard' ? 'nav-tab-active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <BarChart3 size={16} />
            <span>Engineering Telemetry</span>
          </button>
        </nav>

        {/* Backend health status badge & Export */}
        <div className="header-status-area">
          <a
            href="/v1/export/output.json"
            download="output.json"
            className="status-pill status-pill-download"
            title="Download official output.json file"
          >
            <Download size={14} className="text-samsung-blue" />
            <span className="status-text">Export output.json</span>
          </a>
          <button
            className="status-pill"
            onClick={onRefreshHealth}
            title="Click to re-check backend health"
          >
            {healthLoading ? (
              <>
                <span className="status-dot status-dot-loading" />
                <span className="status-text">Checking API...</span>
              </>
            ) : health && health.ready ? (
              <>
                <ShieldCheck size={14} className="text-emerald" />
                <span className="status-text">
                  API Online • {health.catalog_size} Deeplinks
                </span>
              </>
            ) : (
              <>
                <AlertCircle size={14} className="text-rose" />
                <span className="status-text">
                  {healthError ? 'Backend Disconnected' : 'API Initializing'}
                </span>
              </>
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
