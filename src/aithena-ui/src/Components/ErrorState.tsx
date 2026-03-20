import { ReactNode } from 'react';
import { FormattedMessage } from 'react-intl';
import { AlertTriangle, WifiOff, ServerCrash, Clock } from 'lucide-react';
import './ErrorState.css';

export type ErrorCategory = 'network' | 'server' | 'timeout' | 'generic';

export interface ErrorStateProps {
  error: Error | string;
  category?: ErrorCategory;
  onRetry?: () => void;
  children?: ReactNode;
}

function categorizeError(error: Error | string): ErrorCategory {
  const message = typeof error === 'string' ? error : error.message;
  const lowerMessage = message.toLowerCase();

  if (lowerMessage.includes('network') || lowerMessage.includes('fetch')) {
    return 'network';
  }

  if (lowerMessage.includes('timeout') || lowerMessage.includes('timed out')) {
    return 'timeout';
  }

  if (
    lowerMessage.includes('500') ||
    lowerMessage.includes('502') ||
    lowerMessage.includes('503') ||
    lowerMessage.includes('server')
  ) {
    return 'server';
  }

  return 'generic';
}

const ERROR_ICONS = {
  network: WifiOff,
  server: ServerCrash,
  timeout: Clock,
  generic: AlertTriangle,
};

const ERROR_TITLE_IDS = {
  network: 'error.networkTitle',
  server: 'error.serverTitle',
  timeout: 'error.timeoutTitle',
  generic: 'error.genericTitle',
};

const ERROR_DESCRIPTION_IDS = {
  network: 'error.networkDescription',
  server: 'error.serverDescription',
  timeout: 'error.timeoutDescription',
  generic: 'error.genericDescription',
};

function ErrorState({ error, category, onRetry, children }: ErrorStateProps) {
  const detectedCategory = category ?? categorizeError(error);
  const Icon = ERROR_ICONS[detectedCategory];
  const titleId = ERROR_TITLE_IDS[detectedCategory];
  const descriptionId = ERROR_DESCRIPTION_IDS[detectedCategory];

  return (
    <div className="error-state" role="alert">
      <div className="error-state__icon" aria-hidden="true">
        <Icon size={64} />
      </div>
      <h3 className="error-state__title">
        <FormattedMessage id={titleId} />
      </h3>
      <p className="error-state__description">
        <FormattedMessage id={descriptionId} />
      </p>
      {onRetry && (
        <div className="error-state__action">
          <button type="button" className="error-state__button" onClick={onRetry}>
            <FormattedMessage id="error.retryButton" />
          </button>
        </div>
      )}
      {children}
    </div>
  );
}

export default ErrorState;
