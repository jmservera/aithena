# Decision: WCAG 2.1 AA Accessibility Standards for Aithena UI

**Author:** Dallas (Frontend Dev)
**Date:** 2026-03-19
**Context:** Issue #514, PR #597

## Decision

The Aithena React frontend now enforces WCAG 2.1 AA accessibility standards through:

1. **Static linting:** `eslint-plugin-jsx-a11y` (recommended ruleset) is integrated into the ESLint flat config. All new components must pass these rules.

2. **Color contrast minimum:** All text on dark backgrounds must use `rgba(255, 255, 255, 0.65)` or higher. The previous pattern of 0.3–0.45 opacity fails WCAG 1.4.3 (4.5:1 contrast ratio).

3. **Skip-to-content pattern:** The app includes a skip-to-content link in App.tsx that targets `#main-content`. Future layout changes must preserve this `id`.

4. **Motion/contrast media queries:** `prefers-reduced-motion` and `prefers-contrast` are handled at the App.css level. New animations should use CSS custom properties or `transition-duration` so they're automatically disabled.

5. **Modal pattern:** All modal dialogs must include `role="dialog"`, `aria-modal="true"`, and `aria-labelledby` pointing to a heading. Backdrop click-dismiss overlays use eslint-disable comments with the `-- modal backdrop dismiss pattern` reason.

## Rationale

- Legal compliance (accessibility requirements in EU, US Section 508)
- Inclusive UX for all users
- SEO benefits from semantic HTML
- eslint-plugin-jsx-a11y catches ~70% of issues at dev time, preventing regressions

## Impact

- All squad members writing React components should be aware of jsx-a11y lint rules
- Lambert (QA) should add browser-based axe DevTools testing to the QA checklist
