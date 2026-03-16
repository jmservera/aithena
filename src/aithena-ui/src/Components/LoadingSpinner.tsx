import './LoadingSpinner.css';

interface LoadingSpinnerProps {
  title?: string;
  message?: string;
}

function LoadingSpinner({
  title = 'Loading page…',
  message = 'Please wait while Aithena prepares this view.',
}: LoadingSpinnerProps) {
  return (
    <div className="loading-spinner" role="status" aria-live="polite">
      <div className="loading-spinner__indicator" aria-hidden="true" />
      <div className="loading-spinner__content">
        <h2 className="loading-spinner__title">{title}</h2>
        <p className="loading-spinner__message">{message}</p>
      </div>
    </div>
  );
}

export default LoadingSpinner;
