import axe, { type Result } from 'axe-core';

/**
 * Run axe-core accessibility checks on a rendered container.
 * Asserts zero critical or serious WCAG 2.1 AA violations.
 */
export async function checkAccessibility(
  container: HTMLElement,
  options?: { disabledRules?: string[] }
): Promise<void> {
  const results = await axe.run(container, {
    runOnly: {
      type: 'tag',
      values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'],
    },
    rules: Object.fromEntries(
      (options?.disabledRules ?? []).map((rule) => [rule, { enabled: false }])
    ),
  });

  const critical = results.violations.filter(
    (v: Result) => v.impact === 'critical' || v.impact === 'serious'
  );

  if (critical.length > 0) {
    const summary = critical
      .map(
        (v: Result) =>
          `[${v.impact}] ${v.id}: ${v.description}\n` +
          v.nodes.map((n) => `  - ${n.html}\n    ${n.failureSummary}`).join('\n')
      )
      .join('\n\n');

    throw new Error(
      `Found ${critical.length} critical/serious accessibility violation(s):\n\n${summary}`
    );
  }
}
