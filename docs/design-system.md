# Aithena Design System

_Last updated:_ v1.8.0 (2026-03-19)

The Aithena design system provides a cohesive set of design tokens, component patterns, and accessibility guidelines to ensure consistency across the user interface.

## Design Tokens

Design tokens are CSS custom properties (variables) defined in the frontend application. They can be overridden via CSS or updated programmatically to implement theming.

### Color Palette

#### Primary Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--color-primary` | `#2563eb` | Primary actions, links, focus states |
| `--color-primary-dark` | `#1e40af` | Hover states, darker context |
| `--color-primary-light` | `#3b82f6` | Light backgrounds, secondary actions |

#### Semantic Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--color-success` | `#10b981` | Success messages, completed actions |
| `--color-warning` | `#f59e0b` | Warning messages, caution states |
| `--color-error` | `#ef4444` | Error messages, destructive actions |
| `--color-info` | `#0ea5e9` | Informational messages, hints |

#### Neutral Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--color-neutral-50` | `#f9fafb` | Lightest backgrounds |
| `--color-neutral-100` | `#f3f4f6` | Light backgrounds |
| `--color-neutral-500` | `#6b7280` | Default text, secondary elements |
| `--color-neutral-700` | `#374151` | Primary text |
| `--color-neutral-900` | `#111827` | Darkest text |

### Typography

| Token | Value | Usage |
|-------|-------|-------|
| `--font-family-base` | `-apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", sans-serif` | All text |
| `--font-size-xs` | `0.75rem` (12px) | Small labels, captions |
| `--font-size-sm` | `0.875rem` (14px) | Body text, small components |
| `--font-size-base` | `1rem` (16px) | Default body text |
| `--font-size-lg` | `1.125rem` (18px) | Larger text, section headers |
| `--font-size-xl` | `1.25rem` (20px) | Page titles, main headers |
| `--font-size-2xl` | `1.5rem` (24px) | Hero headers |
| `--font-weight-normal` | `400` | Body text, regular weight |
| `--font-weight-medium` | `500` | Emphasized text, buttons |
| `--font-weight-semibold` | `600` | Headings, strong emphasis |
| `--font-weight-bold` | `700` | Bold headings, labels |
| `--line-height-tight` | `1.25` | Compact headings |
| `--line-height-normal` | `1.5` | Body text, paragraphs |
| `--line-height-relaxed` | `1.75` | Longer form content |

### Spacing

Spacing tokens follow an 8px base unit:

| Token | Value | Usage |
|-------|-------|-------|
| `--space-0` | `0` | No spacing |
| `--space-1` | `0.25rem` (4px) | Tight spacing |
| `--space-2` | `0.5rem` (8px) | Default spacing |
| `--space-3` | `0.75rem` (12px) | Moderate spacing |
| `--space-4` | `1rem` (16px) | Component padding |
| `--space-6` | `1.5rem` (24px) | Section padding |
| `--space-8` | `2rem` (32px) | Large section spacing |
| `--space-12` | `3rem` (48px) | Page-level spacing |

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | `0.25rem` (4px) | Subtle curves |
| `--radius-md` | `0.5rem` (8px) | Standard border radius |
| `--radius-lg` | `1rem` (16px) | Large, prominent elements |
| `--radius-full` | `9999px` | Fully rounded (pills, circles) |

### Shadows

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle elevation |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Standard elevation |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | High elevation |

## Icon System

Aithena uses **Lucide React** for all icons. Lucide provides:

- 600+ professionally designed SVG icons
- Consistent stroke width and sizing
- Full accessibility support with ARIA labels
- Customizable color and size via CSS classes and React props

### Common Icons

| Icon | Usage | Component |
|------|-------|-----------|
| `Search` | Search input, search results | SearchPage |
| `Library` | Library navigation, book collections | LibraryPage |
| `Upload` | File upload, document submission | UploadPage |
| `CheckCircle` | Success states, completed items | Alerts |
| `AlertCircle` | Error states, warnings | Error messages |
| `Loader` | Loading states, spinners | Skeleton screens |
| `Settings` | Configuration, admin options | AdminPage |
| `LogOut` | Logout action, session end | Header |

### Using Lucide Icons

```tsx
import { Search, Library, AlertCircle } from 'lucide-react';

export function SearchForm() {
  return (
    <button>
      <Search size={20} strokeWidth={2} />
      Search
    </button>
  );
}
```

## Component Patterns

### Button

**States:**
- Default (primary color, solid)
- Hover (darker primary color)
- Active (pressed appearance)
- Disabled (reduced opacity)

**Variants:**
- Primary: `--color-primary` background
- Secondary: Outlined with primary color
- Danger: `--color-error` background

### Input Fields

**States:**
- Idle (border in neutral-200)
- Focus (border in primary color, shadow)
- Error (border in error color)
- Disabled (reduced opacity)

**Features:**
- Clear labeling with associated `<label>`
- Error message display below field
- Placeholder text for guidance

### Loading States

**Skeleton Screens:**
- Placeholder blocks matching content structure
- Subtle animation (pulse effect)
- Used during initial data fetch

**Loading Spinners:**
- Animated Lucide `Loader` icon
- Centered in content area
- With optional loading text

### Empty States

**Display:**
- Centered illustration or icon (e.g., `Search`)
- Headline describing the empty state
- Optional action button or guidance text

**Example:** "No books found. Try a different search or browse the library."

### Error States

**Display:**
- Lucide `AlertCircle` icon in error color
- Clear error message
- Optional action button to retry or go back

## Responsive Design

### Breakpoints

| Name | Min Width | Usage |
|------|-----------|-------|
| Mobile | 0px | Phones (375px–480px) |
| Tablet | 768px | Tablets and large phones |
| Desktop | 1024px | Desktops and large screens |

### Mobile-First CSS

All styles use mobile-first approach:

```css
/* Mobile (default) */
.component {
  width: 100%;
  font-size: var(--font-size-base);
}

/* Tablet and up */
@media (min-width: 768px) {
  .component {
    width: 50%;
  }
}

/* Desktop and up */
@media (min-width: 1024px) {
  .component {
    width: 33%;
  }
}
```

### Touch-Friendly Sizing

- Minimum touch target: 44px × 44px (for buttons, links)
- Spacing between touch targets: 8px minimum
- Font sizes on mobile: ≥16px for form inputs (prevents auto-zoom on iOS)

## Accessibility Guidelines

### Color Contrast

- Primary text on light backgrounds: ≥4.5:1 WCAG AA
- Secondary text: ≥3:1 WCAG AA
- All interactive elements: ≥3:1 contrast ratio

### Keyboard Navigation

- All interactive elements focusable via Tab key
- Focus outline visible (via `--color-primary`)
- Logical tab order (left-to-right, top-to-bottom)

### Screen Readers

- Semantic HTML (`<button>`, `<label>`, `<nav>`, etc.)
- Icons paired with `aria-label` or wrapped in labeled context
- Form inputs associated with `<label>` elements
- Loading states announced via `aria-busy` or `role="status"`

### Motion

- Animations respect `prefers-reduced-motion`
- Loading spinners and transitions disabled if requested
- No auto-playing videos or animations

## Customization

### CSS Variables

Override design tokens at runtime by setting CSS variables:

```css
:root {
  --color-primary: #ff0000;
  --font-size-base: 18px;
}
```

### Dark Mode (Future)

A dark mode is planned for v1.9.0. It will use a separate set of color tokens with media query detection:

```css
@media (prefers-color-scheme: dark) {
  :root {
    --color-primary: #60a5fa;
    --color-neutral-900: #f9fafb;
  }
}
```

## Testing

All design system features are tested:

- **Token tests:** Verify CSS variables are defined and inherit correctly
- **Icon tests:** Ensure Lucide icons render and are accessible
- **Component tests:** Validate states, responsive breakpoints, and keyboard navigation
- **Accessibility tests:** Check contrast ratios, semantic HTML, and ARIA attributes
- **Responsive tests:** Verify layout at all breakpoints (375px, 768px, 1024px)

Run tests with:

```bash
cd src/aithena-ui
npm test  # Run all design system tests
```

## Contributing

When adding new components or tokens:

1. Add the design token to `src/aithena-ui/src/styles/tokens.css`
2. Use the token consistently in all related components
3. Test at all three breakpoints (mobile, tablet, desktop)
4. Verify accessibility with keyboard navigation and screen readers
5. Add test cases to the component test file
6. Document the token or component in this file

## References

- **Lucide React:** https://lucide.dev
- **WCAG 2.1:** https://www.w3.org/WAI/WCAG21/quickref/
- **Keep a Changelog:** https://keepachangelog.com/en/1.0.0/

---

For questions or contributions, please open an issue or reach out to the Aithena team.
