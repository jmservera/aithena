# Frontend Performance — Best Practices

## React DevTools Profiler Instrumentation

The frontend includes built-in React Profiler instrumentation on performance-critical sections. This lets you measure component render times, identify unnecessary re-renders, and track regressions — all through the standard [React DevTools Profiler tab](https://react.dev/reference/react/Profiler).

### How It Works

Key component trees are wrapped with `<React.Profiler>`:

| Profiler `id`     | Component wrapped          | File                                  |
| ----------------- | -------------------------- | ------------------------------------- |
| `SearchResults`   | `SearchResultsSection`     | `src/pages/SearchPage.tsx`            |
| `UploadForm`      | `UploadContent`            | `src/pages/UploadPage.tsx`            |

Each `<Profiler>` uses a shared `onRenderCallback` from `src/utils/profiler.ts`. In **development** mode the callback logs a structured record to `console.debug`:

```
[Profiler] {
  id: "SearchResults",
  phase: "update",
  actualDuration: "3.12ms",
  baseDuration: "8.45ms",
  startTime: "1042.30ms",
  commitTime: "1045.42ms"
}
```

In **production** builds the logging branch is dead-code-eliminated by Vite, leaving a zero-cost no-op — no runtime overhead.

### Using the Profiler

1. **Install React DevTools** browser extension (Chrome / Firefox / Edge).
2. Run the dev server: `npm run dev`
3. Open DevTools → **Profiler** tab → click **Record** → interact with the UI → **Stop**.
4. Inspect the flame graph and ranked chart for render times.
5. Optionally, open the browser **Console** and filter for `[Profiler]` to see every commit logged in real time.

### Metrics Reference

| Field            | Meaning                                                               |
| ---------------- | --------------------------------------------------------------------- |
| `id`             | The `<Profiler id>` string — identifies the instrumented section      |
| `phase`          | `"mount"` (first render) or `"update"` (re-render)                    |
| `actualDuration` | Time spent rendering the committed change (smaller = faster)          |
| `baseDuration`   | Estimated time to render the entire subtree without memoization       |
| `startTime`      | When React started rendering this update                              |
| `commitTime`     | When React committed this update                                      |

### Adding Profiler to a New Component

```tsx
import { Profiler } from 'react';
import { onRenderCallback } from '../utils/profiler';

function MyPage() {
  return (
    <Profiler id="MySection" onRender={onRenderCallback}>
      <ExpensiveComponent />
    </Profiler>
  );
}
```

Choose an `id` that is descriptive and unique across the app (it appears in DevTools and console logs).

### Production Safety

The `onRenderCallback` guards all logging behind `import.meta.env.DEV`. Vite statically replaces this flag at build time:

- **`npm run dev`** → `DEV = true` → logging active
- **`npm run build`** → `DEV = false` → entire `if` block removed from bundle

You can verify this by inspecting the production build output:

```bash
npm run build
grep -r "Profiler" dist/   # Profiler elements remain (React built-in, ~0 cost)
grep -r "console.debug" dist/   # Should find nothing — logging is stripped
```
