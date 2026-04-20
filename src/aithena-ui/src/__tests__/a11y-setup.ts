/**
 * Reusable axe-core accessibility test helper for WCAG 2.1 AA compliance.
 */
import axe, { type AxeResults, type RunOptions } from 'axe-core';

export interface A11yOptions {
  /** Extra axe RunOptions to merge with defaults. */
  axeOptions?: RunOptions;
  /** Override the default severity filter (default: critical + serious). */
  severities?: string[];
}

const DEFAULT_RUN_OPTIONS: RunOptions = {
  runOnly: {
    type: 'tag',
    values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'],
  },
};

/**
 * Run axe-core against an HTML element and throw if critical/serious
 * violations are found.
 */
export async function checkAccessibility(
  container: HTMLElement,
  options: A11yOptions = {}
): Promise<AxeResults> {
  const runOptions = { ...DEFAULT_RUN_OPTIONS, ...options.axeOptions };
  const results = await axe.run(container, runOptions);

  const severities = options.severities ?? ['critical', 'serious'];
  const violations = results.violations.filter((v) => severities.includes(v.impact ?? ''));

  if (violations.length > 0) {
    const msgs = violations.map(
      (v) =>
        `[${v.impact}] ${v.id}: ${v.description}\n` + v.nodes.map((n) => `  - ${n.html}`).join('\n')
    );
    throw new Error(`Accessibility violations found:\n${msgs.join('\n\n')}`);
  }

  return results;
}
