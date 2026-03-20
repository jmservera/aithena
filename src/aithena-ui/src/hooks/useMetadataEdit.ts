import { useCallback, useEffect, useState } from 'react';

import { apiFetch, buildApiUrl } from '../api';
import { BookResult, FacetValue } from './search';

export interface MetadataFormValues {
  title: string;
  author: string;
  year: string;
  category: string;
  series: string;
}

export interface MetadataFieldErrors {
  title?: string;
  author?: string;
  year?: string;
  category?: string;
  series?: string;
}

export interface FacetOptions {
  category: string[];
  series: string[];
}

interface FacetsResponse {
  facets: {
    category?: FacetValue[];
    series?: FacetValue[];
  };
}

const TITLE_MAX = 255;
const AUTHOR_MAX = 255;
const CATEGORY_MAX = 100;
const SERIES_MAX = 100;
const YEAR_MIN = 1000;
const YEAR_MAX = 2099;

export function initialFormValues(book: BookResult): MetadataFormValues {
  return {
    title: book.title ?? '',
    author: book.author ?? '',
    year: book.year != null ? String(book.year) : '',
    category: book.category ?? '',
    series: book.series ?? '',
  };
}

export function validateMetadata(values: MetadataFormValues): MetadataFieldErrors {
  const errors: MetadataFieldErrors = {};

  if (values.title.length > TITLE_MAX) {
    errors.title = `Title must be ${TITLE_MAX} characters or fewer`;
  }

  if (values.author.length > AUTHOR_MAX) {
    errors.author = `Author must be ${AUTHOR_MAX} characters or fewer`;
  }

  if (values.year.trim() !== '') {
    const yearNum = Number(values.year);
    if (!Number.isInteger(yearNum) || yearNum < YEAR_MIN || yearNum > YEAR_MAX) {
      errors.year = `Year must be between ${YEAR_MIN} and ${YEAR_MAX}`;
    }
  }

  if (values.category.length > CATEGORY_MAX) {
    errors.category = `Category must be ${CATEGORY_MAX} characters or fewer`;
  }

  if (values.series.length > SERIES_MAX) {
    errors.series = `Series must be ${SERIES_MAX} characters or fewer`;
  }

  return errors;
}

export function hasChanges(current: MetadataFormValues, original: MetadataFormValues): boolean {
  return (Object.keys(current) as (keyof MetadataFormValues)[]).some(
    (key) => current[key] !== original[key]
  );
}

function buildPatchBody(
  current: MetadataFormValues,
  original: MetadataFormValues
): Record<string, string | number> {
  const body: Record<string, string | number> = {};
  if (current.title !== original.title) body.title = current.title;
  if (current.author !== original.author) body.author = current.author;
  if (current.year !== original.year) {
    body.year = current.year.trim() === '' ? 0 : Number(current.year);
  }
  if (current.category !== original.category) body.category = current.category;
  if (current.series !== original.series) body.series = current.series;
  return body;
}

const facetsUrl = buildApiUrl('/v1/facets');

export function useMetadataEdit(book: BookResult, onSuccess: (updated: BookResult) => void) {
  const original = initialFormValues(book);
  const [values, setValues] = useState<MetadataFormValues>(original);
  const [errors, setErrors] = useState<MetadataFieldErrors>({});
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [facetOptions, setFacetOptions] = useState<FacetOptions>({ category: [], series: [] });

  useEffect(() => {
    let cancelled = false;

    async function loadFacets() {
      try {
        const response = await apiFetch(`${facetsUrl}?q=`);
        if (!response.ok) return;
        const data: FacetsResponse = await response.json();
        if (cancelled) return;
        setFacetOptions({
          category: (data.facets?.category ?? []).map((f) => f.value),
          series: (data.facets?.series ?? []).map((f) => f.value),
        });
      } catch {
        // Facet loading is best-effort; combobox still works for free-text input
      }
    }

    void loadFacets();
    return () => {
      cancelled = true;
    };
  }, []);

  const setField = useCallback((field: keyof MetadataFormValues, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
    setApiError(null);
  }, []);

  const changed = hasChanges(values, original);

  const save = useCallback(async () => {
    const fieldErrors = validateMetadata(values);
    if (Object.keys(fieldErrors).length > 0) {
      setErrors(fieldErrors);
      return;
    }
    if (!changed) return;

    setSaving(true);
    setApiError(null);
    try {
      const body = buildPatchBody(values, original);
      const response = await apiFetch(
        `/v1/admin/documents/${encodeURIComponent(book.id)}/metadata`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const detail =
          typeof data?.detail === 'string' ? data.detail : `Save failed (${response.status})`;
        throw new Error(detail);
      }

      const updated: BookResult = {
        ...book,
        title: values.title || book.title,
        author: values.author || undefined,
        year: values.year.trim() ? Number(values.year) : undefined,
        category: values.category || undefined,
        series: values.series || undefined,
      };

      onSuccess(updated);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : 'Failed to save metadata');
    } finally {
      setSaving(false);
    }
  }, [values, original, changed, book, onSuccess]);

  return {
    values,
    errors,
    saving,
    apiError,
    changed,
    facetOptions,
    setField,
    save,
  };
}
