import { useIntl } from 'react-intl';

import styles from './LoadingSpinner.module.css';

interface LoadingSpinnerProps {
  title?: string;
  message?: string;
}

function LoadingSpinner({ title, message }: LoadingSpinnerProps) {
  const intl = useIntl();
  const displayTitle = title ?? intl.formatMessage({ id: 'common.loadingPage' });
  const displayMessage = message ?? intl.formatMessage({ id: 'common.loadingMessage' });

  return (
    <div className={styles.loadingSpinner} role="status" aria-live="polite">
      <div className={styles.loadingSpinnerIndicator} aria-hidden="true" />
      <div className={styles.loadingSpinnerContent}>
        <h2 className={styles.loadingSpinnerTitle}>{displayTitle}</h2>
        <p className={styles.loadingSpinnerMessage}>{displayMessage}</p>
      </div>
    </div>
  );
}

export default LoadingSpinner;
