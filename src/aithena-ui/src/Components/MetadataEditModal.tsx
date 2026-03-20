import { memo, useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useIntl } from 'react-intl';

import { BookResult } from '../hooks/search';
import { useMetadataEdit } from '../hooks/useMetadataEdit';
import './MetadataEditModal.css';

interface MetadataEditModalProps {
  book: BookResult;
  onClose: () => void;
  onSaved: (updated: BookResult) => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/* ── Combobox sub-component ───────────────────────────────────── */

interface ComboboxFieldProps {
  id: string;
  label: string;
  value: string;
  options: string[];
  maxLength: number;
  error?: string;
  onChange: (value: string) => void;
}

function ComboboxField({
  id,
  label,
  value,
  options,
  maxLength,
  error,
  onChange,
}: ComboboxFieldProps) {
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const listboxId = `${id}-listbox`;

  const filtered = useMemo(
    () =>
      value.trim() ? options.filter((o) => o.toLowerCase().includes(value.toLowerCase())) : options,
    [options, value]
  );

  // Reset highlight when filtered list changes — legitimate sync-with-props pattern
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHighlightIndex(-1);
  }, [filtered.length]);

  const selectOption = useCallback(
    (option: string) => {
      onChange(option);
      setOpen(false);
    },
    [onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
        setOpen(true);
        e.preventDefault();
        return;
      }

      if (!open) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightIndex((prev) => (prev < filtered.length - 1 ? prev + 1 : 0));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightIndex((prev) => (prev > 0 ? prev - 1 : filtered.length - 1));
      } else if ((e.key === 'Enter' || e.key === 'Tab') && highlightIndex >= 0) {
        e.preventDefault();
        selectOption(filtered[highlightIndex]);
      } else if (e.key === 'Escape') {
        setOpen(false);
      }
    },
    [open, filtered, highlightIndex, selectOption]
  );

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="meta-edit-field" ref={wrapperRef}>
      <label htmlFor={id} className="meta-edit-label">
        {label}
      </label>
      <div className="meta-edit-combobox-wrapper">
        <input
          id={id}
          type="text"
          role="combobox"
          className={`meta-edit-input${error ? ' meta-edit-input--error' : ''}`}
          value={value}
          maxLength={maxLength}
          autoComplete="off"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={highlightIndex >= 0 ? `${id}-option-${highlightIndex}` : undefined}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
        />
        {open && filtered.length > 0 && (
          <ul id={listboxId} className="meta-edit-listbox" role="listbox">
            {filtered.map((option, idx) => (
              <li
                key={option}
                id={`${id}-option-${idx}`}
                role="option"
                className={`meta-edit-option${idx === highlightIndex ? ' meta-edit-option--active' : ''}`}
                aria-selected={idx === highlightIndex}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectOption(option);
                }}
                onMouseEnter={() => setHighlightIndex(idx)}
              >
                {option}
              </li>
            ))}
          </ul>
        )}
      </div>
      {error && (
        <span className="meta-edit-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

/* ── Main modal ───────────────────────────────────────────────── */

const MetadataEditModal = memo(function MetadataEditModal({
  book,
  onClose,
  onSaved,
}: MetadataEditModalProps) {
  const intl = useIntl();
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const [toast, setToast] = useState(false);

  const handleSaved = useCallback(
    (updated: BookResult) => {
      setToast(true);
      // Short delay so user sees the toast before modal closes
      setTimeout(() => {
        onSaved(updated);
      }, 600);
    },
    [onSaved]
  );

  const { values, errors, saving, apiError, changed, facetOptions, setField, save } =
    useMetadataEdit(book, handleSaved);

  // Lock body scroll and focus close button
  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, []);

  // Keyboard: Escape to close, Tab trap
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;

      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      ).filter((el) => !el.hasAttribute('disabled'));

      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      const inside = active instanceof HTMLElement && panelRef.current.contains(active);

      if (event.shiftKey) {
        if (!inside || active === first) {
          event.preventDefault();
          last.focus();
        }
      } else if (!inside || active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      void save();
    },
    [save]
  );

  return (
    <div className="meta-edit-overlay" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div ref={panelRef} className="meta-edit-panel" tabIndex={-1}>
        <div className="meta-edit-header">
          <h2 id={titleId} className="meta-edit-title">
            {intl.formatMessage({ id: 'metadataEdit.title' })}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            className="meta-edit-close"
            onClick={onClose}
            aria-label={intl.formatMessage({ id: 'metadataEdit.close' })}
          >
            ✕
          </button>
        </div>

        {toast && (
          <div className="meta-edit-toast" role="status" aria-live="polite">
            {intl.formatMessage({ id: 'metadataEdit.success' })}
          </div>
        )}

        {apiError && (
          <div className="meta-edit-api-error" role="alert">
            {apiError}
          </div>
        )}

        <form className="meta-edit-form" onSubmit={handleSubmit} noValidate>
          <TextInputField
            id="meta-edit-title"
            label={intl.formatMessage({ id: 'metadataEdit.fieldTitle' })}
            value={values.title}
            maxLength={255}
            error={errors.title}
            onChange={(v) => setField('title', v)}
          />

          <TextInputField
            id="meta-edit-author"
            label={intl.formatMessage({ id: 'metadataEdit.fieldAuthor' })}
            value={values.author}
            maxLength={255}
            error={errors.author}
            onChange={(v) => setField('author', v)}
          />

          <YearInputField
            id="meta-edit-year"
            label={intl.formatMessage({ id: 'metadataEdit.fieldYear' })}
            value={values.year}
            error={errors.year}
            onChange={(v) => setField('year', v)}
          />

          <ComboboxField
            id="meta-edit-category"
            label={intl.formatMessage({ id: 'metadataEdit.fieldCategory' })}
            value={values.category}
            options={facetOptions.category}
            maxLength={100}
            error={errors.category}
            onChange={(v) => setField('category', v)}
          />

          <ComboboxField
            id="meta-edit-series"
            label={intl.formatMessage({ id: 'metadataEdit.fieldSeries' })}
            value={values.series}
            options={facetOptions.series}
            maxLength={100}
            error={errors.series}
            onChange={(v) => setField('series', v)}
          />

          <div className="meta-edit-actions">
            <button type="button" className="meta-edit-btn-cancel" onClick={onClose}>
              {intl.formatMessage({ id: 'metadataEdit.cancel' })}
            </button>
            <button type="submit" className="meta-edit-btn-save" disabled={!changed || saving}>
              {saving
                ? intl.formatMessage({ id: 'metadataEdit.saving' })
                : intl.formatMessage({ id: 'metadataEdit.save' })}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
});

export default MetadataEditModal;

/* ── Simple sub-components ────────────────────────────────────── */

interface TextInputFieldProps {
  id: string;
  label: string;
  value: string;
  maxLength: number;
  error?: string;
  onChange: (value: string) => void;
}

function TextInputField({ id, label, value, maxLength, error, onChange }: TextInputFieldProps) {
  return (
    <div className="meta-edit-field">
      <label htmlFor={id} className="meta-edit-label">
        {label}
      </label>
      <input
        id={id}
        type="text"
        className={`meta-edit-input${error ? ' meta-edit-input--error' : ''}`}
        value={value}
        maxLength={maxLength}
        onChange={(e) => onChange(e.target.value)}
      />
      {error && (
        <span className="meta-edit-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

interface YearInputFieldProps {
  id: string;
  label: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}

function YearInputField({ id, label, value, error, onChange }: YearInputFieldProps) {
  return (
    <div className="meta-edit-field">
      <label htmlFor={id} className="meta-edit-label">
        {label}
      </label>
      <input
        id={id}
        type="number"
        className={`meta-edit-input meta-edit-input--year${error ? ' meta-edit-input--error' : ''}`}
        value={value}
        min={1000}
        max={2099}
        onChange={(e) => onChange(e.target.value)}
      />
      {error && (
        <span className="meta-edit-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
