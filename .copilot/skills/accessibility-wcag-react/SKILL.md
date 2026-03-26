---
name: "accessibility-wcag-react"
description: "WCAG 2.1 AA accessibility patterns for React applications"
domain: "frontend, accessibility, wcag, a11y"
confidence: "high"
source: "earned — aithena WCAG 2.1 AA audit and fixes (Dallas, PR #597, 2026)"
author: "Dallas"
created: "2026-03-20"
last_validated: "2026-03-20"
---

## Overview

Accessibility patterns established in the aithena frontend to achieve WCAG 2.1 AA compliance. Covers skip navigation, focus management, color contrast, motion preferences, ARIA attributes, and static analysis.

## Skip-to-Content Link

```tsx
// App.tsx — first child inside BrowserRouter
<a href="#main-content" className="skip-link">
  {intl.formatMessage({ id: 'app.skipToContent' })}
</a>
<main id="main-content" ref={mainRef} tabIndex={-1}>
  {/* page content */}
</main>
```

```css
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  z-index: 100;
  padding: 8px 16px;
  background: #7ec8e3;
  color: #000;
}
.skip-link:focus {
  top: 0;
}
```

**i18n:** Add `app.skipToContent` key to all 4 locale files.

## Focus Management on Route Changes

```tsx
import { useLocation } from 'react-router-dom';

function App() {
  const mainRef = useRef<HTMLElement>(null);
  const location = useLocation();

  useEffect(() => {
    mainRef.current?.focus();
  }, [location.pathname]);

  return <main ref={mainRef} tabIndex={-1}>{/* routes */}</main>;
}
```

**Why:** Screen readers need focus moved to main content when routes change in SPAs.

## Color Contrast (WCAG AA 4.5:1)

### Minimum Opacity Rules
- **Primary text:** `rgba(255, 255, 255, 1.0)` on dark backgrounds
- **Secondary text:** `rgba(255, 255, 255, 0.7)` minimum (never below 0.65)
- **Tertiary/muted text:** `rgba(255, 255, 255, 0.65)` minimum

**Before (failing):** `color: rgba(255, 255, 255, 0.3)` — fails 4.5:1 ratio  
**After (passing):** `color: rgba(255, 255, 255, 0.65)` — passes 4.5:1 ratio

### Checking Contrast
Use browser DevTools color picker or https://webaim.org/resources/contrastchecker/

## Media Queries for User Preferences

### Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### High Contrast
```css
@media (prefers-contrast: more) {
  body {
    background-color: #000;
    color: #fff;
  }
  .book-card, .facet-panel {
    border-color: rgba(255, 255, 255, 0.5);
  }
  /* Raise all secondary text to full opacity */
  .meta-text, .secondary-text {
    opacity: 1;
  }
}
```

## ARIA Attributes

### Modal Dialogs
```tsx
<div role="dialog" aria-modal="true" aria-labelledby="dialog-title">
  <h2 id="dialog-title">Edit User</h2>
  {/* dialog content */}
</div>
```

### Health Indicator Dots
```tsx
<span className="service-dot" role="img" aria-label={`${serviceName} status: ${status}`}>
  ●
</span>
```

### Table Headers
```tsx
<thead>
  <tr>
    <th scope="col">Name</th>
    <th scope="col">Status</th>
  </tr>
</thead>
```

### Redundant Roles to Remove
- ❌ `<section role="region">` — `<section>` already has implicit region role
- ❌ `<nav role="navigation">` — `<nav>` already has implicit navigation role

## Static Analysis: eslint-plugin-jsx-a11y

```bash
npm install --save-dev eslint-plugin-jsx-a11y
```

In `eslint.config.js` (flat config):
```javascript
import jsxA11y from 'eslint-plugin-jsx-a11y';

export default [
  // ... other configs
  jsxA11y.flatConfigs.recommended,
];
```

### What It Catches (~70%)
- Missing `alt` on images
- Redundant ARIA roles
- Missing keyboard handlers on interactive elements
- Invalid ARIA attributes
- Missing form labels

### What It Can't Catch (~30%)
- Color contrast violations
- Focus management correctness
- Screen reader announcement quality
- Keyboard navigation flow
- Visual layout accessibility

**For the remaining 30%:** Use axe DevTools in browser, or @axe-core/react as dev dependency.

## Checklist for New Components

1. ☐ Keyboard navigable (Tab, Enter, Escape)
2. ☐ Appropriate ARIA roles and labels
3. ☐ Color contrast ≥ 4.5:1 (text) or ≥ 3:1 (large text/UI)
4. ☐ No information conveyed by color alone
5. ☐ Animations respect `prefers-reduced-motion`
6. ☐ Focus visible on interactive elements
7. ☐ Form inputs have associated labels
8. ☐ Error messages announced to screen readers

## References

- **eslint-plugin-jsx-a11y:** Integrated in `eslint.config.js`
- **@axe-core/react:** Dev dependency for runtime a11y checks
- **PR #597:** Original WCAG 2.1 AA implementation
- **WCAG 2.1 Quick Reference:** https://www.w3.org/WAI/WCAG21/quickref/
