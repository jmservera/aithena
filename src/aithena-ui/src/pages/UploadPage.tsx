import { useState, useRef, DragEvent, ChangeEvent, RefObject } from 'react';
import { Link } from 'react-router-dom';
import ErrorBoundary, { ErrorBoundaryFallbackProps } from '../Components/ErrorBoundary';
import { useUpload, UploadProgress, UploadResult } from '../hooks/upload';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface UploadContentProps {
  dragOver: boolean;
  error: string | null;
  fileInputRef: RefObject<HTMLInputElement>;
  progress: UploadProgress | null;
  result: UploadResult | null;
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
        The upload panel hit an unexpected problem.
      </h2>
      <p className="error-boundary__message">
        Try reloading this section first. If the issue keeps happening, reload the app and retry the
        file.
      </p>
      <div className="error-boundary__actions">
        <button type="button" className="error-boundary__button" onClick={reset}>
          Try again
        </button>
        <button
          type="button"
          className="error-boundary__button error-boundary__button--secondary"
          onClick={reload}
        >
          Reload app
        </button>
      </div>
    </section>
  );
}

function UploadContent({
  dragOver,
  error,
  fileInputRef,
  progress,
  result,
  uploading,
  onBrowseClick,
  onDrop,
  onDragEnter,
  onDragLeave,
  onDragOver,
  onFileInputChange,
  onReset,
}: UploadContentProps) {
  return (
    <>
      {!result && !error && (
        <div
          className={`upload-dropzone ${dragOver ? 'upload-dropzone--drag-over' : ''} ${uploading ? 'upload-dropzone--uploading' : ''}`}
          onDragEnter={onDragEnter}
          onDragLeave={onDragLeave}
          onDragOver={onDragOver}
          onDrop={onDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={onFileInputChange}
            style={{ display: 'none' }}
            disabled={uploading}
          />

          {!uploading && (
            <div className="upload-dropzone-content">
              <div className="upload-icon">📄</div>
              <p className="upload-prompt">
                Drag and drop a PDF file here, or{' '}
                <button type="button" className="upload-browse-button" onClick={onBrowseClick}>
                  browse
                </button>
              </p>
              <p className="upload-hint">Maximum file size: 50MB</p>
            </div>
          )}

          {uploading && progress && (
            <div className="upload-progress">
              <div className="upload-progress-spinner">⏳</div>
              <p className="upload-progress-text">Uploading...</p>
              <div className="upload-progress-bar">
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
        <div className="upload-result upload-result--error">
          <div className="upload-result-icon">❌</div>
          <h3 className="upload-result-title">Upload Failed</h3>
          <p className="upload-result-message">{error}</p>
          <button className="upload-result-button" onClick={onReset}>
            Try Again
          </button>
        </div>
      )}

      {result && (
        <div className="upload-result upload-result--success">
          <div className="upload-result-icon">✅</div>
          <h3 className="upload-result-title">Upload Successful</h3>
          <p className="upload-result-message">{result.message}</p>
          <div className="upload-result-details">
            <p>
              <strong>Filename:</strong> {result.filename}
            </p>
            <p>
              <strong>Size:</strong> {formatFileSize(result.size)}
            </p>
            <p>
              <strong>Status:</strong> {result.status}
            </p>
          </div>
          <div className="upload-result-actions">
            <Link to="/search" className="upload-result-button upload-result-button--primary">
              Back to Search
            </Link>
            <button className="upload-result-button" onClick={onReset}>
              Upload Another
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function UploadPage() {
  const { uploading, progress, result, error, uploadFile, reset } = useUpload();
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelected(files[0]);
    }
  };

  const handleFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelected(files[0]);
    }
  };

  const handleFileSelected = (file: File) => {
    uploadFile(file).catch(() => {
      // Error is already handled by the upload hook's error state
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
        <h2 className="upload-title">Upload PDF</h2>
        <p className="upload-description">
          Add a new book to the library by uploading a PDF file (max 50MB)
        </p>

        <ErrorBoundary fallback={renderUploadFallback}>
          <UploadContent
            dragOver={dragOver}
            error={error}
            fileInputRef={fileInputRef}
            progress={progress}
            result={result}
            uploading={uploading}
            onBrowseClick={handleBrowseClick}
            onDrop={handleDrop}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onFileInputChange={handleFileInputChange}
            onReset={handleReset}
          />
        </ErrorBoundary>
      </div>
    </div>
  );
}

export default UploadPage;
