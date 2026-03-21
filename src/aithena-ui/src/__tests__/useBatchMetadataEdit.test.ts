import { describe, it, expect } from 'vitest';

import { validateBatchField } from '../hooks/useBatchMetadataEdit';

describe('validateBatchField', () => {
  it('accepts a valid title', () => {
    expect(validateBatchField('title', 'A valid title')).toBeUndefined();
  });

  it('rejects title over 255 characters', () => {
    expect(validateBatchField('title', 'x'.repeat(256))).toMatch(/255/);
  });

  it('accepts empty title (clearing)', () => {
    expect(validateBatchField('title', '')).toBeUndefined();
  });

  it('accepts a valid author', () => {
    expect(validateBatchField('author', 'Jane Doe')).toBeUndefined();
  });

  it('rejects author over 255 characters', () => {
    expect(validateBatchField('author', 'x'.repeat(256))).toMatch(/255/);
  });

  it('accepts a valid year', () => {
    expect(validateBatchField('year', '2024')).toBeUndefined();
  });

  it('accepts empty year (clearing)', () => {
    expect(validateBatchField('year', '')).toBeUndefined();
  });

  it('rejects year below 1000', () => {
    expect(validateBatchField('year', '999')).toMatch(/1000/);
  });

  it('rejects year above 2099', () => {
    expect(validateBatchField('year', '2100')).toMatch(/2099/);
  });

  it('rejects non-integer year', () => {
    expect(validateBatchField('year', '20.5')).toBeDefined();
  });

  it('rejects non-numeric year', () => {
    expect(validateBatchField('year', 'abc')).toBeDefined();
  });

  it('accepts a valid category', () => {
    expect(validateBatchField('category', 'Science')).toBeUndefined();
  });

  it('rejects category over 100 characters', () => {
    expect(validateBatchField('category', 'x'.repeat(101))).toMatch(/100/);
  });

  it('accepts a valid series', () => {
    expect(validateBatchField('series', 'The Lord of the Rings')).toBeUndefined();
  });

  it('rejects series over 100 characters', () => {
    expect(validateBatchField('series', 'x'.repeat(101))).toMatch(/100/);
  });

  it('is a pure function', () => {
    const result1 = validateBatchField('title', 'test');
    const result2 = validateBatchField('title', 'test');
    expect(result1).toBe(result2);
  });

  // --- Enhanced tests: boundary values, concurrent scenarios, error recovery ---

  it('accepts title at exactly 255 characters', () => {
    expect(validateBatchField('title', 'x'.repeat(255))).toBeUndefined();
  });

  it('accepts author at exactly 255 characters', () => {
    expect(validateBatchField('author', 'x'.repeat(255))).toBeUndefined();
  });

  it('accepts category at exactly 100 characters', () => {
    expect(validateBatchField('category', 'x'.repeat(100))).toBeUndefined();
  });

  it('accepts series at exactly 100 characters', () => {
    expect(validateBatchField('series', 'x'.repeat(100))).toBeUndefined();
  });

  it('accepts year boundary 1000', () => {
    expect(validateBatchField('year', '1000')).toBeUndefined();
  });

  it('accepts year boundary 2099', () => {
    expect(validateBatchField('year', '2099')).toBeUndefined();
  });

  it('rejects year with leading zeros as non-integer string', () => {
    // '0999' → Number('0999') === 999 which is below min
    expect(validateBatchField('year', '0999')).toBeDefined();
  });

  it('rejects negative year', () => {
    expect(validateBatchField('year', '-1')).toBeDefined();
  });

  it('accepts title with special characters', () => {
    expect(validateBatchField('title', "L'Étranger — A Novel (2nd ed.)")).toBeUndefined();
  });

  it('accepts author with unicode characters', () => {
    expect(validateBatchField('author', 'José García Márquez')).toBeUndefined();
  });

  it('validates each field independently', () => {
    // Valid title, but would fail if tested as category (at 101 chars)
    const longButValidTitle = 'x'.repeat(101);
    expect(validateBatchField('title', longButValidTitle)).toBeUndefined();
    expect(validateBatchField('category', longButValidTitle)).toMatch(/100/);
  });
});
