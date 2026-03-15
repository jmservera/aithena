import { useState, useRef, DragEvent, ChangeEvent } from 'react';
import { Link } from 'react-router-dom';
import { useUpload } from '../hooks/upload';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

        {!result && !error && (
          <div
            className={`upload-dropzone ${dragOver ? 'upload-dropzone--drag-over' : ''} ${uploading ? 'upload-dropzone--uploading' : ''}`}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              onChange={handleFileInputChange}
              style={{ display: 'none' }}
              disabled={uploading}
            />

            {!uploading && (
              <div className="upload-dropzone-content">
                <div className="upload-icon">📄</div>
                <p className="upload-prompt">
                  Drag and drop a PDF file here, or{' '}
                  <button
                    type="button"
                    className="upload-browse-button"
                    onClick={handleBrowseClick}
                  >
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
            <button className="upload-result-button" onClick={handleReset}>
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
              <button className="upload-result-button" onClick={handleReset}>
                Upload Another
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default UploadPage;
