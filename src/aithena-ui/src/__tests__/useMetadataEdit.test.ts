import { describe, it, expect } from 'vitest';

import {
  validateMetadata,
  hasChanges,
  initialFormValues,
  MetadataFormValues,
} from '../hooks/useMetadataEdit';
import { BookResult } from '../hooks/search';

describe('initialFormValues', () => {
  it('extracts all fields from a complete book', () => {
    const book: BookResult = {
      id: 'doc-1',
      title: 'My Book',
      author: 'Author',
      year: 2020,
      category: 'Fiction',
      series: 'Series A',
    };

    expect(initialFormValues(book)).toEqual({
      title: 'My Book',
      author: 'Author',
      year: '2020',
      category: 'Fiction',
      series: 'Series A',
    });
  });

  it('uses empty strings for missing optional fields', () => {
    const book: BookResult = { id: 'doc-2', title: 'Minimal' };

    expect(initialFormValues(book)).toEqual({
      title: 'Minimal',
      author: '',
      year: '',
      category: '',
      series: '',
    });
  });
});

describe('validateMetadata', () => {
  const base: MetadataFormValues = {
    title: 'OK Title',
    author: 'OK Author',
    year: '2020',
    category: 'OK',
    series: 'OK',
  };

  it('returns no errors for valid values', () => {
    expect(validateMetadata(base)).toEqual({});
  });

  it('returns no errors when year is empty (optional)', () => {
    expect(validateMetadata({ ...base, year: '' })).toEqual({});
  });

  it('rejects year below 1000', () => {
    const errors = validateMetadata({ ...base, year: '999' });
    expect(errors.year).toMatch(/between 1000 and 2099/);
  });

  it('rejects year above 2099', () => {
    const errors = validateMetadata({ ...base, year: '2100' });
    expect(errors.year).toMatch(/between 1000 and 2099/);
  });

  it('rejects non-integer year', () => {
    const errors = validateMetadata({ ...base, year: '20.5' });
    expect(errors.year).toMatch(/between 1000 and 2099/);
  });

  it('rejects non-numeric year', () => {
    const errors = validateMetadata({ ...base, year: 'abc' });
    expect(errors.year).toMatch(/between 1000 and 2099/);
  });

  it('accepts boundary year 1000', () => {
    expect(validateMetadata({ ...base, year: '1000' })).toEqual({});
  });

  it('accepts boundary year 2099', () => {
    expect(validateMetadata({ ...base, year: '2099' })).toEqual({});
  });

  it('rejects title over 255 chars', () => {
    const errors = validateMetadata({ ...base, title: 'A'.repeat(256) });
    expect(errors.title).toMatch(/255 characters/);
  });

  it('accepts title at exactly 255 chars', () => {
    expect(validateMetadata({ ...base, title: 'A'.repeat(255) })).toEqual({});
  });

  it('rejects author over 255 chars', () => {
    const errors = validateMetadata({ ...base, author: 'A'.repeat(256) });
    expect(errors.author).toMatch(/255 characters/);
  });

  it('rejects category over 100 chars', () => {
    const errors = validateMetadata({ ...base, category: 'A'.repeat(101) });
    expect(errors.category).toMatch(/100 characters/);
  });

  it('accepts category at exactly 100 chars', () => {
    expect(validateMetadata({ ...base, category: 'A'.repeat(100) })).toEqual({});
  });

  it('rejects series over 100 chars', () => {
    const errors = validateMetadata({ ...base, series: 'A'.repeat(101) });
    expect(errors.series).toMatch(/100 characters/);
  });

  it('returns multiple errors at once', () => {
    const errors = validateMetadata({
      title: 'A'.repeat(256),
      author: 'B'.repeat(256),
      year: '500',
      category: 'C'.repeat(101),
      series: 'D'.repeat(101),
    });

    expect(Object.keys(errors)).toHaveLength(5);
  });
});

describe('hasChanges', () => {
  const original: MetadataFormValues = {
    title: 'Original',
    author: 'Author',
    year: '2020',
    category: 'Cat',
    series: 'Ser',
  };

  it('returns false when values are identical', () => {
    expect(hasChanges({ ...original }, original)).toBe(false);
  });

  it('returns true when title differs', () => {
    expect(hasChanges({ ...original, title: 'Changed' }, original)).toBe(true);
  });

  it('returns true when year differs', () => {
    expect(hasChanges({ ...original, year: '2025' }, original)).toBe(true);
  });

  it('returns true when category differs', () => {
    expect(hasChanges({ ...original, category: 'New Category' }, original)).toBe(true);
  });
});
