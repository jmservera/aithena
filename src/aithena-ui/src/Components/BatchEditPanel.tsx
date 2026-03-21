import { memo, useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useIntl } from 'react-intl';

import {
  useBatchMetadataEdit,
  BatchField,
  validateBatchField,
} from '../hooks/useBatchMetadataEdit';
import './BatchEditPanel.css';

interface BatchEditPanelProps {
  documentIds: string[];
  onClose: () => void;
  onSaved: () => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/* ── Combobox ────────────────────────────────────────────────── */

interface ComboboxFieldProps {
  id: string;
  label: string;
  value: string;
  options: string[];
  maxLength: number;
  disabled: boolean;
  error?: string;
  onChange: (value: string) => void;
}

function ComboboxField({
  id,
  label,
  value,
  options,
  maxLength,
  disabled,
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
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  return (
    <div className="batch-field-combobox" ref={wrapperRef}>
      <label htmlFor={id} className="batch-field-label">
        {label}
      </label>
      <input
        id={id}
        type="text"
        role="combobox"
        className={`batch-field-input${error ? ' batch-field-input--error' : ''}`}
        value={value}
        maxLength={maxLength}
        disabled={disabled}
        aria-expanded={open}
        aria-autocomplete="list"
        aria-controls={listboxId}
        aria-activedescendant={highlightIndex >= 0 ? `${id}-opt-${highlightIndex}` : undefined}
        aria-invalid={!!error}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
      />
      {open && filtered.length > 0 && !disabled && (
        <ul id={listboxId} className="batch-combobox-listbox" role="listbox">
          {filtered.map((option, idx) => (
            <li
              key={option}
              id={`${id}-opt-${idx}`}
              role="option"
              className={`batch-combobox-option${idx === highlightIndex ? ' batch-combobox-option--highlight' : ''}`}
              aria-selected={idx === highlightIndex}
              onMouseDown={(e) => {
                e.preventDefault();
                selectOption(option);
              }}
            >
              {option}
            </li>
          ))}
        </ul>
      )}
      {error && <p className="batch-field-error">{error}</p>}
    </div>
  );
}

/* ── Field row ───────────────────────────────────────────────── */

interface BatchFieldRowProps {
  field: BatchField;
  label: string;
  enabled: boolean;
  value: string;
  error?: string;
  comboboxOptions?: string[];
  comboboxMaxLength?: number;
  onToggle: (enabled: boolean) => void;
  onChange: (value: string) => void;
}

function BatchFieldRow({
  field,
  label,
  enabled,
  value,
  error,
  comboboxOptions,
  comboboxMaxLength,
  onToggle,
  onChange,
}: BatchFieldRowProps) {
  const fieldId = useId();

  if (comboboxOptions) {
    return (
      <div className="batch-field-row">
        <label className="batch-field-toggle">
          <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
          <span className="batch-toggle-label">{label}</span>
        </label>
        <ComboboxField
          id={fieldId}
          label=""
          value={value}
          options={comboboxOptions}
          maxLength={comboboxMaxLength ?? 100}
          disabled={!enabled}
          error={enabled ? error : undefined}
          onChange={onChange}
        />
      </div>
    );
  }

  const inputType = field === 'year' ? 'number' : 'text';
  const maxLength =
    field === 'title' || field === 'author' ? 255 : field === 'year' ? undefined : 100;

  return (
    <div className="batch-field-row">
      <label className="batch-field-toggle">
        <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
        <span className="batch-toggle-label">{label}</span>
      </label>
      <div>
        <label htmlFor={fieldId} className="visually-hidden">
          {label}
        </label>
        <input
          id={fieldId}
          type={inputType}
          className={`batch-field-input${enabled && error ? ' batch-field-input--error' : ''}`}
          value={value}
          maxLength={maxLength}
          disabled={!enabled}
          aria-invalid={enabled && !!error}
          onChange={(e) => onChange(e.target.value)}
        />
        {enabled && error && <p className="batch-field-error">{error}</p>}
      </div>
    </div>
  );
}

/* ── Preview section ─────────────────────────────────────────── */

interface PreviewSectionProps {
  toggles: Record<BatchField, boolean>;
  values: Record<BatchField, string>;
  documentCount: number;
}

const FIELD_LABELS: Record<BatchField, string> = {
  title: 'Title',
  author: 'Author',
  year: 'Year',
  category: 'Category',
  series: 'Series',
};

function PreviewSection({ toggles, values, documentCount }: PreviewSectionProps) {
  const intl = useIntl();
  const enabledEntries = (Object.keys(toggles) as BatchField[]).filter((f) => toggles[f]);

  if (enabledEntries.length === 0) return null;

  return (
    <div className="batch-preview">
      <h3 className="batch-preview-title">{intl.formatMessage({ id: 'batchEdit.preview' })}</h3>
      <p className="batch-preview-summary">
        {intl.formatMessage(
          { id: 'batchEdit.previewSummary' },
          { fieldCount: enabledEntries.length, documentCount }
        )}
      </p>
      <ul className="batch-preview-list">
        {enabledEntries.map((field) => (
          <li key={field} className="batch-preview-item">
            <strong>{FIELD_LABELS[field]}:</strong>{' '}
            {values[field] || intl.formatMessage({ id: 'batchEdit.previewClear' })}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ── Result display ──────────────────────────────────────────── */

interface BatchResultDisplayProps {
  result: {
    matched: number;
    updated: number;
    failed: number;
    errors: { document_id: string; error: string }[];
  };
}

function BatchResultDisplay({ result }: BatchResultDisplayProps) {
  const intl = useIntl();

  if (result.failed === 0) {
    return (
      <div className="batch-result batch-result--success" role="status">
        {intl.formatMessage({ id: 'batchEdit.success' }, { count: result.updated })}
      </div>
    );
  }

  const visibleErrors = result.errors.slice(0, 5);
  const remaining = result.errors.length - visibleErrors.length;

  return (
    <div className="batch-result batch-result--partial" role="alert">
      <p>
        {intl.formatMessage(
          { id: 'batchEdit.partialFailure' },
          { updated: result.updated, failed: result.failed }
        )}
      </p>
      <ul className="batch-error-list">
        {visibleErrors.map((e) => (
          <li key={e.document_id}>
            {e.document_id}: {e.error}
          </li>
        ))}
      </ul>
      {remaining > 0 && (
        <p className="batch-error-more">
          {intl.formatMessage({ id: 'batchEdit.moreErrors' }, { count: remaining })}
        </p>
      )}
    </div>
  );
}

/* ── Main panel ──────────────────────────────────────────────── */

const BatchEditPanel = memo(function BatchEditPanel({
  documentIds,
  onClose,
  onSaved,
}: BatchEditPanelProps) {
  const intl = useIntl();
  const panelRef = useRef<HTMLDivElement>(null);
  const {
    values,
    toggles,
    errors,
    saving,
    apiError,
    result,
    facetOptions,
    hasEnabledFields,
    hasValidationErrors,
    setField,
    setToggle,
    save,
  } = useBatchMetadataEdit(documentIds);

  // Focus trap
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;

      const focusable = panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    panel.addEventListener('keydown', handleKeyDown);
    const firstFocusable = panel.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    firstFocusable?.focus();

    return () => panel.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Body scroll lock
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      let hasErrors = false;
      for (const [field, on] of Object.entries(toggles) as [BatchField, boolean][]) {
        if (on) {
          const err = validateBatchField(field, values[field]);
          if (err) {
            hasErrors = true;
          }
        }
      }
      if (hasErrors) return;

      const success = await save();
      if (success) {
        onSaved();
      }
    },
    [toggles, values, save, onSaved]
  );

  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    },
    [onClose]
  );

  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div className="batch-panel-overlay" onClick={handleOverlayClick}>
      <div
        ref={panelRef}
        className="batch-panel"
        role="dialog"
        aria-modal="true"
        aria-label={intl.formatMessage({ id: 'batchEdit.title' }, { count: documentIds.length })}
      >
        <header className="batch-panel-header">
          <h2 className="batch-panel-title">
            {intl.formatMessage({ id: 'batchEdit.title' }, { count: documentIds.length })}
          </h2>
          <button
            type="button"
            className="batch-panel-close"
            onClick={onClose}
            aria-label={intl.formatMessage({ id: 'batchEdit.close' })}
          >
            ✕
          </button>
        </header>

        <p className="batch-panel-instructions">
          {intl.formatMessage({ id: 'batchEdit.instructions' })}
        </p>

        <form onSubmit={handleSubmit} className="batch-panel-form">
          <BatchFieldRow
            field="title"
            label="Title"
            enabled={toggles.title}
            value={values.title}
            error={errors.title}
            onToggle={(on) => setToggle('title', on)}
            onChange={(v) => setField('title', v)}
          />
          <BatchFieldRow
            field="author"
            label="Author"
            enabled={toggles.author}
            value={values.author}
            error={errors.author}
            onToggle={(on) => setToggle('author', on)}
            onChange={(v) => setField('author', v)}
          />
          <BatchFieldRow
            field="year"
            label="Year"
            enabled={toggles.year}
            value={values.year}
            error={errors.year}
            onToggle={(on) => setToggle('year', on)}
            onChange={(v) => setField('year', v)}
          />
          <BatchFieldRow
            field="category"
            label="Category"
            enabled={toggles.category}
            value={values.category}
            error={errors.category}
            comboboxOptions={facetOptions.category}
            comboboxMaxLength={100}
            onToggle={(on) => setToggle('category', on)}
            onChange={(v) => setField('category', v)}
          />
          <BatchFieldRow
            field="series"
            label="Series"
            enabled={toggles.series}
            value={values.series}
            error={errors.series}
            comboboxOptions={facetOptions.series}
            comboboxMaxLength={100}
            onToggle={(on) => setToggle('series', on)}
            onChange={(v) => setField('series', v)}
          />

          <PreviewSection toggles={toggles} values={values} documentCount={documentIds.length} />

          {apiError && (
            <div className="batch-result batch-result--error" role="alert">
              {apiError}
            </div>
          )}

          {result && <BatchResultDisplay result={result} />}

          <div className="batch-panel-actions">
            <button
              type="submit"
              className="batch-panel-submit"
              disabled={!hasEnabledFields || saving || hasValidationErrors}
            >
              {saving
                ? intl.formatMessage({ id: 'batchEdit.applying' })
                : intl.formatMessage({ id: 'batchEdit.apply' })}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
});

export default BatchEditPanel;
