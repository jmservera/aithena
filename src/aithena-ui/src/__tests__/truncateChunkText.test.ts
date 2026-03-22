import { describe, it, expect } from 'vitest';

import { truncateChunkText } from '../utils/truncateChunkText';

describe('truncateChunkText', () => {
  // ---- edge / no-op cases ----

  it('returns empty string unchanged', () => {
    expect(truncateChunkText('')).toBe('');
  });

  it('returns undefined/null-ish input unchanged', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(truncateChunkText(undefined as any)).toBeUndefined();
  });

  it('returns text unchanged when already within limit', () => {
    expect(truncateChunkText('Short text')).toBe('Short text');
  });

  it('returns text unchanged when exactly at limit', () => {
    const exact = 'A'.repeat(20);
    expect(truncateChunkText(exact)).toBe(exact);
  });

  // ---- plain text (semantic search) ----

  it('truncates plain text to 20 chars by default and adds ellipsis', () => {
    const long = 'Neural networks learn hierarchical representations of data';
    const result = truncateChunkText(long);
    // visible chars (before ellipsis) should be exactly 20
    expect(result.replace('…', '').length).toBe(20);
    expect(result.endsWith('…')).toBe(true);
  });

  it('respects a custom maxChars limit', () => {
    const text = 'The quick brown fox jumps over the lazy dog';
    const result = truncateChunkText(text, 10);
    expect(result).toBe('The quick …');
  });

  // ---- highlighted text (keyword search) ----

  it('centers truncation around the <em> highlight', () => {
    const text = 'many words before the <em>highlight</em> and many words after it';
    const result = truncateChunkText(text, 20);

    // <em> tags must survive
    expect(result).toContain('<em>highlight</em>');

    // visible char count (excluding tags) should be ≤ 20
    const visibleLength = result.replace(/<\/?em>/g, '').replace(/…/g, '').length;
    expect(visibleLength).toBeLessThanOrEqual(20);
  });

  it('adds leading ellipsis when content is trimmed before highlight', () => {
    const text = 'lots of text before the <em>match</em> end';
    const result = truncateChunkText(text, 14);
    expect(result.startsWith('…')).toBe(true);
    expect(result).toContain('<em>match</em>');
  });

  it('adds trailing ellipsis when content is trimmed after highlight', () => {
    const text = '<em>match</em> and then lots more text following it';
    const result = truncateChunkText(text, 14);
    expect(result.endsWith('…')).toBe(true);
    expect(result).toContain('<em>match</em>');
  });

  it('handles highlight at the very start of text', () => {
    const text = '<em>start</em> then a bunch more words here that are long';
    const result = truncateChunkText(text, 15);
    expect(result).toContain('<em>start</em>');
    expect(result.startsWith('…')).toBe(false); // nothing before to trim
  });

  it('handles highlight at the very end of text', () => {
    const text = 'a bunch of words appearing before the <em>end</em>';
    const result = truncateChunkText(text, 15);
    expect(result).toContain('<em>end</em>');
    expect(result.endsWith('…')).toBe(false); // nothing after to trim
  });

  it('truncates the highlight itself when it exceeds maxChars', () => {
    const longHighlight = 'A'.repeat(30);
    const text = `before <em>${longHighlight}</em> after`;
    const result = truncateChunkText(text, 20);
    expect(result).toBe(`…<em>${longHighlight.slice(0, 20)}</em>…`);
  });

  it('preserves short highlighted text without wrapping ellipses', () => {
    const text = 'hi <em>ok</em> end';
    // visible: "hi ok end" = 9 chars, within default 20
    expect(truncateChunkText(text)).toBe(text);
  });
});
