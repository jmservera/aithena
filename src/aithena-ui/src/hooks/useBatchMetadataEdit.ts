import { useCallback, useEffect, useState } from 'react';

import { apiFetch, buildApiUrl } from '../api';
import { FacetValue, SearchFilters } from './search';

export interface BatchMetadataValues {
  title: string;
  author: string;
  year: string;
  category: string;
  series: string;
}

export interface BatchFieldToggles {
  title: boolean;
  author: boolean;
  year: boolean;
  category: boolean;
  series: boolean;
}

export type BatchField = keyof BatchMetadataValues;

export interface BatchResult {
  matched: number;
  updated: number;
  failed: number;
  errors: { document_id: string; error: string }[];
}

export interface FacetOptions {
  category: string[];
  series: string[];
}

/** When set, the batch edit uses the query-based endpoint instead of IDs. */
export interface BatchQueryContext {
  query: string;
  filters: SearchFilters;
  total: number;
}

const TITLE_MAX = 255;
const AUTHOR_MAX = 255;
const CATEGORY_MAX = 100;
const SERIES_MAX = 100;
const YEAR_MIN = 1000;
const YEAR_MAX = 2099;

const INITIAL_VALUES: BatchMetadataValues = {
  title: '',
  author: '',
  year: '',
  category: '',
  series: '',
};

const INITIAL_TOGGLES: BatchFieldToggles = {
  title: false,
  author: false,
  year: false,
  category: false,
  series: false,
};

interface FacetsResponse {
  facets: {
    category?: FacetValue[];
    series?: FacetValue[];
  };
}

export function validateBatchField(field: BatchField, value: string): string | undefined {
  switch (field) {
    case 'title':
      if (value.length > TITLE_MAX) return `Title must be ${TITLE_MAX} characters or fewer`;
      break;
    case 'author':
      if (value.length > AUTHOR_MAX) return `Author must be ${AUTHOR_MAX} characters or fewer`;
      break;
    case 'year':
      if (value !== '') {
        const num = Number(value);
        if (!Number.isInteger(num) || num < YEAR_MIN || num > YEAR_MAX) {
          return `Year must be between ${YEAR_MIN} and ${YEAR_MAX}`;
        }
      }
      break;
    case 'category':
      if (value.length > CATEGORY_MAX)
        return `Category must be ${CATEGORY_MAX} characters or fewer`;
      break;
    case 'series':
      if (value.length > SERIES_MAX) return `Series must be ${SERIES_MAX} characters or fewer`;
      break;
  }
  return undefined;
}

export function useBatchMetadataEdit(documentIds: string[], queryContext?: BatchQueryContext) {
  const [values, setValues] = useState<BatchMetadataValues>({ ...INITIAL_VALUES });
  const [toggles, setToggles] = useState<BatchFieldToggles>({ ...INITIAL_TOGGLES });
  const [errors, setErrors] = useState<Partial<Record<BatchField, string>>>({});
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [result, setResult] = useState<BatchResult | null>(null);
  const [facetOptions, setFacetOptions] = useState<FacetOptions>({ category: [], series: [] });

  useEffect(() => {
    let cancelled = false;
    async function loadFacets() {
      try {
        const response = await apiFetch(buildApiUrl('/v1/facets?q='));
        if (!response.ok || cancelled) return;
        const data = (await response.json()) as FacetsResponse;
        if (cancelled) return;
        setFacetOptions({
          category: (data.facets.category ?? []).map((f) => f.value),
          series: (data.facets.series ?? []).map((f) => f.value),
        });
      } catch {
        // Facet loading is best-effort
      }
    }
    void loadFacets();
    return () => {
      cancelled = true;
    };
  }, []);

  const setField = useCallback((field: BatchField, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
    const error = validateBatchField(field, value);
    setErrors((prev) => {
      const next = { ...prev };
      if (error) {
        next[field] = error;
      } else {
        delete next[field];
      }
      return next;
    });
  }, []);

  const setToggle = useCallback((field: BatchField, enabled: boolean) => {
    setToggles((prev) => ({ ...prev, [field]: enabled }));
  }, []);

  const enabledFields = Object.entries(toggles).filter(([, on]) => on) as [BatchField, boolean][];
  const hasEnabledFields = enabledFields.length > 0;
  const enabledFieldCount = enabledFields.length;

  const hasValidationErrors = Object.keys(errors).some((key) => toggles[key as BatchField]);

  const save = useCallback(async (): Promise<boolean> => {
    setApiError(null);

    const updates: Record<string, string | number> = {};
    for (const [field] of enabledFields) {
      const val = values[field];
      if (field === 'year' && val !== '') {
        updates[field] = Number(val);
      } else {
        updates[field] = val;
      }
    }

    setSaving(true);
    try {
      let url: string;
      let body: Record<string, unknown>;

      if (queryContext) {
        url = buildApiUrl('/v1/admin/documents/batch/metadata-by-query');
        const filters: Record<string, string> = {};
        for (const [key, value] of Object.entries(queryContext.filters)) {
          if (value) filters[key] = value;
        }
        body = {
          query: queryContext.query,
          filters: Object.keys(filters).length > 0 ? filters : undefined,
          updates,
        };
      } else {
        url = buildApiUrl('/v1/admin/documents/batch/metadata');
        body = { document_ids: documentIds, updates };
      }

      const response = await apiFetch(url, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const text = await response.text();
        setApiError(text || `Request failed with status ${response.status}`);
        return false;
      }

      const data = (await response.json()) as BatchResult;
      setResult(data);
      return data.failed === 0;
    } catch (err) {
      setApiError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    } finally {
      setSaving(false);
    }
  }, [documentIds, queryContext, enabledFields, values]);

  const reset = useCallback(() => {
    setValues({ ...INITIAL_VALUES });
    setToggles({ ...INITIAL_TOGGLES });
    setErrors({});
    setApiError(null);
    setResult(null);
  }, []);

  return {
    values,
    toggles,
    errors,
    saving,
    apiError,
    result,
    facetOptions,
    hasEnabledFields,
    enabledFieldCount,
    hasValidationErrors,
    setField,
    setToggle,
    save,
    reset,
  };
}
