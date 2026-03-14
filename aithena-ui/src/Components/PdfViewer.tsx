import { useState, useEffect } from 'react';
import { resolveDocumentUrl } from '../api';
import { BookResult } from '../hooks/search';

interface PdfViewerProps {
  result: BookResult;
  onClose: () => void;
}

const PdfViewer = ({ result, onClose }: PdfViewerProps) => {
  const [loadError, setLoadError] = useState(false);

  // Reset error state when a new document is opened
  useEffect(() => {
    setLoadError(false);
  }, [result.document_url]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const pdfUrl = resolveDocumentUrl(result.document_url);
  const pageStart = result.pages?.[0];
  const pdfUrlWithPage = pdfUrl
    ? pageStart !== undefined
      ? `${pdfUrl}#page=${pageStart}`
      : pdfUrl
    : null;

  return (
    <div
      className="pdf-viewer-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`PDF viewer: ${result.title || 'document'}`}
    >
      <div className="pdf-viewer-panel">
        <div className="pdf-viewer-header">
          <div className="pdf-viewer-title">
            <span className="pdf-viewer-icon">📄</span>
            <div>
              <strong>{result.title || 'Document'}</strong>
              {result.author && <span className="pdf-viewer-author"> — {result.author}</span>}
            </div>
          </div>
          <button className="pdf-viewer-close" onClick={onClose} aria-label="Close PDF viewer">
            ✕
          </button>
        </div>

        <div className="pdf-viewer-body">
          {loadError ? (
            <div className="pdf-viewer-error" role="alert">
              <p>⚠️ Could not load the PDF document.</p>
              <p className="pdf-viewer-error-detail">
                The file may be unavailable or the URL is invalid.
              </p>
              {pdfUrlWithPage && (
                <a
                  href={pdfUrlWithPage}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="pdf-viewer-fallback-link"
                >
                  Try opening in a new tab
                </a>
              )}
            </div>
          ) : pdfUrlWithPage ? (
            <iframe
              className="pdf-viewer-frame"
              src={pdfUrlWithPage}
              title={result.title || 'PDF document'}
              onError={() => setLoadError(true)}
            />
          ) : (
            <div className="pdf-viewer-error" role="alert">
              <p>⚠️ No document URL available for this result.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PdfViewer;
