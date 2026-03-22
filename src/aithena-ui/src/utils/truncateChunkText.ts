/**
 * Truncate text for compact display in search result cards.
 *
 * - If the text contains `<em>` highlighted terms (keyword search), truncation
 *   centers around the first highlighted term, preserving the `<em>` tags.
 *   The `<em>`/`</em>` tags do NOT count toward the character limit.
 * - If no highlights, truncation starts from the beginning.
 *
 * @param text - The text to truncate (may contain `<em>…</em>` tags).
 * @param maxChars - Maximum **visible** characters (HTML tags excluded). Default 20.
 * @returns Truncated text with "…" where content was trimmed, or the original
 *          text when it already fits within the limit.
 */
export function truncateChunkText(text: string, maxChars: number = 20): string {
  if (!text) return text;

  // Strip <em>/</ em> to measure visible length.
  const visible = text.replace(/<\/?em>/g, '');

  if (visible.length <= maxChars) return text;

  // --- Highlighted text (keyword / text search) ---
  const emMatch = text.match(/<em>(.*?)<\/em>/);

  if (emMatch && emMatch.index !== undefined) {
    // Compute highlight position in visible-character space.
    const beforeHighlight = text.slice(0, emMatch.index).replace(/<\/?em>/g, '');
    const highlightText = emMatch[1];
    const highlightStart = beforeHighlight.length;
    const highlightEnd = highlightStart + highlightText.length;

    // If the highlight alone exceeds maxChars, truncate the highlight itself.
    if (highlightText.length >= maxChars) {
      return `…<em>${highlightText.slice(0, maxChars)}</em>…`;
    }

    // Distribute remaining budget around the highlight.
    const remaining = maxChars - highlightText.length;
    const beforeBudget = Math.floor(remaining / 2);
    const afterBudget = remaining - beforeBudget;

    const sliceStart = Math.max(0, highlightStart - beforeBudget);
    const sliceEnd = Math.min(visible.length, highlightEnd + afterBudget);

    let result = '';
    if (sliceStart > 0) result += '…';
    result += visible.slice(sliceStart, highlightStart);
    result += `<em>${highlightText}</em>`;
    result += visible.slice(highlightEnd, sliceEnd);
    if (sliceEnd < visible.length) result += '…';

    return result;
  }

  // --- Plain text (semantic search) ---
  return visible.slice(0, maxChars) + '…';
}
