import React, { useState } from 'react';
import {
  ExternalLink,
  CheckSquare,
  Square,
  Cpu,
  UserCheck,
  AlertOctagon,
  ChevronRight,
  ShieldCheck,
  Info,
} from 'lucide-react';
import { Action, Deeplink, ValidationDeeplink } from '../types';

interface ActionCardProps {
  action: Action;
  index: number;
  onOpenDeeplink: (dl: Deeplink, val?: ValidationDeeplink | null) => void;
}

export const ActionCard: React.FC<ActionCardProps> = ({
  action,
  index,
  onOpenDeeplink,
}) => {
  const [completedSteps, setCompletedSteps] = useState<Record<number, boolean>>({});

  const toggleStep = (stepIdx: number) => {
    setCompletedSteps((prev) => ({
      ...prev,
      [stepIdx]: !prev[stepIdx],
    }));
  };

  const category = action.category || 'manual';

  const categoryConfig = {
    auto: {
      label: 'Automated Action',
      badgeClass: 'badge-auto',
      icon: <Cpu size={14} />,
      cardClass: 'card-category-auto',
    },
    manual: {
      label: 'Manual User Step',
      badgeClass: 'badge-manual',
      icon: <UserCheck size={14} />,
      cardClass: 'card-category-manual',
    },
    critical: {
      label: 'Critical / Hardware Step',
      badgeClass: 'badge-critical',
      icon: <AlertOctagon size={14} />,
      cardClass: 'card-category-critical',
    },
  }[category];

  // Calculate progress
  const allSteps = action.stepGroups.flatMap((sg) => sg.steps);
  const completedCount = allSteps.filter((_, idx) => completedSteps[idx]).length;
  const isAllComplete = allSteps.length > 0 && completedCount === allSteps.length;

  return (
    <div className={`action-card ${categoryConfig.cardClass} ${isAllComplete ? 'action-complete' : ''}`}>
      {/* Header row */}
      <div className="action-card-header">
        <div className="action-header-left">
          <span className="action-number-badge">Step {index + 1}</span>
          <span className={`category-badge ${categoryConfig.badgeClass}`}>
            {categoryConfig.icon}
            <span>{categoryConfig.label}</span>
          </span>
        </div>
        <div className="action-header-right">
          <span className="step-progress-text">
            {completedCount}/{allSteps.length} completed
          </span>
        </div>
      </div>

      {/* Action Title and Description */}
      <div className="action-content">
        <h3 className="action-title">{action.actionName}</h3>
        <p className="action-description">{action.description}</p>
      </div>

      {/* Step Groups list */}
      <div className="steps-container">
        {action.stepGroups.map((sg, sgIdx) => (
          <div key={sgIdx} className="step-group">
            <ul className="step-list">
              {sg.steps.map((stepText, sIdx) => {
                const globalIdx = sgIdx * 10 + sIdx;
                const isChecked = !!completedSteps[globalIdx];
                return (
                  <li
                    key={sIdx}
                    className={`step-item ${isChecked ? 'step-checked' : ''}`}
                    onClick={() => toggleStep(globalIdx)}
                  >
                    <button className="step-checkbox" aria-label="Toggle step">
                      {isChecked ? (
                        <CheckSquare size={18} className="text-emerald" />
                      ) : (
                        <Square size={18} />
                      )}
                    </button>
                    <span className="step-text">{stepText}</span>
                  </li>
                );
              })}
            </ul>

            {/* Actionable Deeplink CTA */}
            {sg.actionableDeeplink && (
              <div className="deeplink-cta-bar">
                <div className="deeplink-info">
                  <div className="deeplink-intent-label">
                    <span>Direct Action Available:</span>
                    <strong>{sg.actionableDeeplink.message || 'Open Settings'}</strong>
                  </div>
                  <code className="deeplink-uri-pill">
                    {sg.actionableDeeplink.deeplink}
                  </code>
                </div>
                <button
                  className="btn-launch-setting"
                  onClick={() =>
                    onOpenDeeplink(sg.actionableDeeplink!, sg.validationDeeplink)
                  }
                >
                  <span>Open Settings</span>
                  <ExternalLink size={14} />
                </button>
              </div>
            )}

            {/* Validation Deeplink Indicator */}
            {sg.validationDeeplink && (
              <div className="validation-status-pill">
                <ShieldCheck size={14} className="text-emerald" />
                <span>
                  Validation Rule: <strong>{sg.validationDeeplink.key}</strong> ({sg.validationDeeplink.condition || 'equal'} {sg.validationDeeplink.value || 'True'})
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
