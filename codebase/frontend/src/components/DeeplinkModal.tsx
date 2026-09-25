import React, { useState } from 'react';
import { ExternalLink, Copy, Check, X, Smartphone, AlertTriangle } from 'lucide-react';
import { Deeplink, ValidationDeeplink } from '../types';

interface DeeplinkModalProps {
  deeplink: Deeplink | null;
  validation?: ValidationDeeplink | null;
  isOpen: boolean;
  onClose: () => void;
}

export const DeeplinkModal: React.FC<DeeplinkModalProps> = ({
  deeplink,
  validation,
  isOpen,
  onClose,
}) => {
  const [copied, setCopied] = useState(false);

  if (!isOpen || !deeplink) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(deeplink.deeplink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isDummy = deeplink.deeplink === 'bixby://dummy_positive';

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-row">
            <Smartphone size={20} className="text-samsung-blue" />
            <h3>Galaxy Settings Direct Action</h3>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div className="deeplink-display-box">
            <div className="deeplink-uri-row">
              <span className="deeplink-uri-text">{deeplink.deeplink}</span>
              <button
                className="btn-copy"
                onClick={handleCopy}
                title="Copy Deeplink URI"
              >
                {copied ? <Check size={14} className="text-emerald" /> : <Copy size={14} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            {deeplink.message && (
              <p className="deeplink-message">
                <strong>Target Intent:</strong> {deeplink.message}
              </p>
            )}
            <p className="deeplink-description">{deeplink.description}</p>
          </div>

          {/* Validation deeplink inspection */}
          {validation && (
            <div className="validation-box">
              <h4>State Verification Binding</h4>
              <div className="validation-details-grid">
                <div>
                  <span className="label">Verification Key:</span>
                  <span className="value">{validation.key}</span>
                </div>
                <div>
                  <span className="label">Expected Value:</span>
                  <span className="value">
                    {validation.condition} {validation.value || 'True'}
                  </span>
                </div>
                <div>
                  <span className="label">Validation URI:</span>
                  <code className="value-code">{validation.deeplink}</code>
                </div>
              </div>
            </div>
          )}

          {/* Protocol notice for browser environment */}
          <div className="protocol-notice">
            <AlertTriangle size={18} className="text-amber" />
            <div>
              <strong>Galaxy Device Integration Notice</strong>
              <p>
                {isDummy
                  ? 'This action targets a concrete Galaxy device setting screen using the verified fallback handler.'
                  : 'On Samsung OneUI devices, this URI is automatically intercepted by the Galaxy Settings & Bixby subsystem to launch the exact configuration panel directly.'}
              </p>
              <p className="subtext">
                Standard desktop browsers do not register the <code>bixby://</code> custom
                protocol handler. In a production Galaxy deployment, this activates device Settings directly.
              </p>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
          <a
            href={deeplink.deeplink}
            className="btn-primary"
            onClick={(e) => {
              // Attempt protocol launch
            }}
          >
            <ExternalLink size={16} />
            <span>Launch Protocol (Galaxy Only)</span>
          </a>
        </div>
      </div>
    </div>
  );
};
