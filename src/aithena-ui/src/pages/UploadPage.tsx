import { ChangeEvent, DragEvent, Profiler, RefObject, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useIntl, FormattedMessage } from 'react-intl';
import { FileText, XCircle, CircleCheck, Loader } from 'lucide-react';
import ErrorBoundary, { ErrorBoundaryFallbackProps } from '../Components/ErrorBoundary';
import { useUpload, UploadProgress, UploadResult } from '../hooks/upload';
import { onRenderCallback } from '../utils/profiler';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface UploadContentProps {
  dragOver: boolean;
  error: string | null;
  fileInputId: string;
  fileInputRef: RefObject<HTMLInputElement | null>;
  progress: UploadProgress | null;
  result: UploadResult | null;
  uploadHintId: string;
  uploadStatusId: string;
  uploading: boolean;
  onBrowseClick: () => void;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onDragEnter: (event: DragEvent<HTMLDivElement>) => void;
  onDragLeave: (event: DragEvent<HTMLDivElement>) => void;
  onDragOver: (event: DragEvent<HTMLDivElement>) => void;
  onFileInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onReset: () => void;
}

function renderUploadFallback({ reset, reload }: ErrorBoundaryFallbackProps) {
  return (
    <section className="error-boundary error-boundary--section" role="alert" aria-live="assertive">
      <h2 className="error-boundary__title error-boundary__title--section">
        <FormattedMessage id="upload.errorTitle" />
      </h2>
      <p className="error-boundary__message">
        <FormattedMessage id="upload.errorMessage" />
      </p>
      <div className="error-boundary__actions">
        <button type="button" className="error-boundary__button" onClick={reset}>
          <FormattedMessage id="upload.errorRetry" />
        </button>
        <button
          type="button"
          className="error-boundary__button error-boundary__button--secondary"
          onClick={reload}
        >
          <FormattedMessage id="upload.errorReload" />
        </button>
      </div>
    </section>
  );
}

function UploadContent({
  dragOver,
  error,
  fileInputId,
  fileInputRef,
  progress,
  result,
  uploadHintId,
  uploadStatusId,
  uploading,
  onBrowseClick,
  onDrop,
  onDragEnter,
  onDragLeave,
  onDragOver,
  onFileInputChange,
  onReset,
}: UploadContentProps) {
  const intl = useIntl();
  return (
    <>
      {!result && !error && (
        <div
          className={`upload-dropzone ${dragOver ? 'upload-dropzone--drag-over' : ''} ${uploading ? 'upload-dropzone--uploading' : ''}`}
          onDragEnter={onDragEnter}
          onDragLeave={onDragLeave}
          onDragOver={onDragOver}
          onDrop={onDrop}
          aria-busy={uploading}
        >
          <label className="visually-hidden" htmlFor={fileInputId}>
            {intl.formatMessage({ id: 'upload.fileInputLabel' })}
          </label>
          <input
            id={fileInputId}
            ref={fileInputRef}
            className="visually-hidden"
            type="file"
            accept="application/pdf,.pdf"
            onChange={onFileInputChange}
            aria-describedby={uploadHintId}
            disabled={uploading}
          />

          {!uploading && (
            <div className="upload-dropzone-content">
              <div className="upload-icon" aria-hidden="true">
                <FileText size={20} />
              </div>
              <p className="upload-prompt">
                {intl.formatMessage({ id: 'upload.dragPrompt' })}{' '}
                <button
                  type="button"
                  className="upload-browse-button"
                  onClick={onBrowseClick}
                  aria-describedby={uploadHintId}
                >
                  {intl.formatMessage({ id: 'upload.browse' })}
                </button>
              </p>
              <p id={uploadHintId} className="upload-hint">
                {intl.formatMessage({ id: 'upload.maxFileSize' })}
              </p>
            </div>
          )}

          {uploading && progress && (
            <div
              id={uploadStatusId}
              className="upload-progress"
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              <div className="upload-progress-spinner" aria-hidden="true">
                <Loader size={20} />
              </div>
              <p className="upload-progress-text">
                {intl.formatMessage({ id: 'upload.uploading' })}
              </p>
              <div
                className="upload-progress-bar"
                role="progressbar"
                aria-label={intl.formatMessage({ id: 'upload.progressLabel' })}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(progress.percentage)}
              >
                <div
                  className="upload-progress-bar-fill"
                  style={{ width: `${progress.percentage}%` }}
                />
              </div>
              <p className="upload-progress-stats">
                {formatFileSize(progress.loaded)} / {formatFileSize(progress.total)} (
                {progress.percentage}%)
              </p>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="upload-result upload-result--error" role="alert">
          <div className="upload-result-icon" aria-hidden="true">
            <XCircle size={20} />
          </div>
          <h3 className="upload-result-title">
            {intl.formatMessage({ id: 'upload.failedTitle' })}
          </h3>
          <p className="upload-result-message">{error}</p>
          <button type="button" className="upload-result-button" onClick={onReset}>
            Try Again
          </button>
        </div>
      )}

      {result && (
        <div className="upload-result upload-result--success" role="status" aria-live="polite">
          <div className="upload-result-icon" aria-hidden="true">
            <CircleCheck size={20} />
          </div>
          <h3 className="upload-result-title">
            {intl.formatMessage({ id: 'upload.successTitle' })}
          </h3>
          <p className="upload-result-message">{result.message}</p>
          <div className="upload-result-details">
            <p>
              <strong>{intl.formatMessage({ id: 'upload.filenameLabel' })}</strong>{' '}
              {result.filename}
            </p>
            <p>
              <strong>{intl.formatMessage({ id: 'upload.sizeLabel' })}</strong>{' '}
              {formatFileSize(result.size)}
            </p>
            <p>
              <strong>{intl.formatMessage({ id: 'upload.statusLabel' })}</strong> {result.status}
            </p>
          </div>
          <div className="upload-result-actions">
            <Link to="/search" className="upload-result-button upload-result-button--primary">
              Back to Search
            </Link>
            <button type="button" className="upload-result-button" onClick={onReset}>
              Upload Another
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function UploadPage() {
  const intl = useIntl();
  const { uploading, progress, result, error, uploadFile, reset } = useUpload();
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const fileInputId = useId();
  const uploadHintId = useId();
  const uploadStatusId = useId();

  const handleDragEnter = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setDragOver(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setDragOver(false);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setDragOver(false);

    const files = event.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelected(files[0]);
    }
  };

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      handleFileSelected(files[0]);
    }
  };

  const handleFileSelected = (file: File) => {
    uploadFile(file).catch(() => {
      // Error is already handled by the upload hook's error state.
    });
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleReset = () => {
    reset();
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="upload-page">
      <div className="upload-container">
        <h2 className="upload-title">{intl.formatMessage({ id: 'upload.title' })}</h2>
        <p className="upload-description">{intl.formatMessage({ id: 'upload.description' })}</p>

        <ErrorBoundary fallback={renderUploadFallback}>
          <Profiler id="UploadForm" onRender={onRenderCallback}>
            <UploadContent
              dragOver={dragOver}
              error={error}
              fileInputId={fileInputId}
              fileInputRef={fileInputRef}
              progress={progress}
              result={result}
              uploadHintId={uploadHintId}
              uploadStatusId={uploadStatusId}
              uploading={uploading}
              onBrowseClick={handleBrowseClick}
              onDrop={handleDrop}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onFileInputChange={handleFileInputChange}
              onReset={handleReset}
            />
          </Profiler>
        </ErrorBoundary>
      </div>
    </div>
  );
}

export default UploadPage;
