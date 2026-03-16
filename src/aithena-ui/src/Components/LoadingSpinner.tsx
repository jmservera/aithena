import styles from './LoadingSpinner.module.css';

interface LoadingSpinnerProps {
  title?: string;
  message?: string;
}

function LoadingSpinner({
  title = 'Loading page…',
  message = 'Please wait while Aithena prepares this view.',
}: LoadingSpinnerProps) {
  return (
    <div className={styles.loadingSpinner} role="status" aria-live="polite">
      <div className={styles.loadingSpinnerIndicator} aria-hidden="true" />
      <div className={styles.loadingSpinnerContent}>
        <h2 className={styles.loadingSpinnerTitle}>{title}</h2>
        <p className={styles.loadingSpinnerMessage}>{message}</p>
      </div>
    </div>
  );
}

export default LoadingSpinner;
