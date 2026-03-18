import { useEffect, useId, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import { FileText } from 'lucide-react';

import { resolveDocumentUrl } from '../api';
import { BookResult } from '../hooks/search';

interface PdfViewerProps {
  result: BookResult;
  onClose: () => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), iframe, input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const PdfViewer = ({ result, onClose }: PdfViewerProps) => {
  const intl = useIntl();
  const [loadError, setLoadError] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();

  // Reset load error when document URL changes - this is a legitimate
  // sync-with-props pattern for resetting error state on navigation
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadError(false);
  }, [result.document_url]);

  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeButtonRef.current?.focus();

    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== 'Tab' || !panelRef.current) {
        return;
      }

      const focusableElements = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      ).filter((element) => !element.hasAttribute('disabled'));

      if (focusableElements.length === 0) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement;
      const focusInsidePanel =
        activeElement instanceof HTMLElement && panelRef.current.contains(activeElement);

      if (event.shiftKey) {
        if (!focusInsidePanel || activeElement === firstElement) {
          event.preventDefault();
          lastElement.focus();
        }
        return;
      }

      if (!focusInsidePanel || activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
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
    <div className="pdf-viewer-overlay" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div ref={panelRef} className="pdf-viewer-panel" tabIndex={-1}>
        <div className="pdf-viewer-header">
          <div className="pdf-viewer-title">
            <span className="pdf-viewer-icon" aria-hidden="true">
              <FileText size={20} />
            </span>
            <div>
              <strong id={titleId}>
                {result.title || intl.formatMessage({ id: 'pdf.document' })}
              </strong>
              {result.author && (
                <span className="pdf-viewer-author">
                  {intl.formatMessage({ id: 'pdf.authorSeparator' }, { author: result.author })}
                </span>
              )}
            </div>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="pdf-viewer-close"
            onClick={onClose}
            aria-label={intl.formatMessage({ id: 'pdf.closeViewer' })}
          >
            ✕
          </button>
        </div>

        <div className="pdf-viewer-body">
          {loadError ? (
            <div className="pdf-viewer-error" role="alert">
              <p>
                {intl.formatMessage({ id: 'error.prefix' })}{' '}
                {intl.formatMessage({ id: 'pdf.loadError' })}
              </p>
              <p className="pdf-viewer-error-detail">
                {intl.formatMessage({ id: 'pdf.loadErrorDetail' })}
              </p>
              {pdfUrlWithPage && (
                <a
                  href={pdfUrlWithPage}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="pdf-viewer-fallback-link"
                >
                  {intl.formatMessage({ id: 'pdf.openInNewTab' })}
                </a>
              )}
            </div>
          ) : pdfUrlWithPage ? (
            <iframe
              className="pdf-viewer-frame"
              src={pdfUrlWithPage}
              title={result.title || intl.formatMessage({ id: 'pdf.pdfDocument' })}
              onError={() => setLoadError(true)}
            />
          ) : (
            <div className="pdf-viewer-error" role="alert">
              <p>
                {intl.formatMessage({ id: 'error.prefix' })}{' '}
                {intl.formatMessage({ id: 'pdf.noDocumentUrl' })}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PdfViewer;
