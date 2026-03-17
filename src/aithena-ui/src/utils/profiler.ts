/**
 * React DevTools Profiler instrumentation.
 *
 * Provides an `onRender` callback for `<React.Profiler>` that logs component
 * render metrics to the console — but only during development.  In production
 * builds Vite tree-shakes the logging path and the callback becomes a no-op,
 * so there is zero runtime overhead.
 *
 * Usage:
 *   import { Profiler } from 'react';
 *   import { onRenderCallback } from '../utils/profiler';
 *
 *   <Profiler id="SearchResults" onRender={onRenderCallback}>
 *     <SearchResultsSection ... />
 *   </Profiler>
 *
 * @see https://react.dev/reference/react/Profiler
 */

import type { ProfilerOnRenderCallback } from 'react';

/**
 * Profiler `onRender` callback.
 *
 * In **development** (`import.meta.env.DEV === true`) it logs a structured
 * record with timing data to the console so you can inspect performance in
 * React DevTools' Profiler tab or in the browser console.
 *
 * In **production** the function body is empty — Vite's dead-code elimination
 * removes the `if (import.meta.env.DEV)` branch entirely.
 */
export const onRenderCallback: ProfilerOnRenderCallback = (
  id,
  phase,
  actualDuration,
  baseDuration,
  startTime,
  commitTime
) => {
  if (import.meta.env.DEV) {
    console.debug('[Profiler]', {
      id,
      phase,
      actualDuration: `${actualDuration.toFixed(2)}ms`,
      baseDuration: `${baseDuration.toFixed(2)}ms`,
      startTime: `${startTime.toFixed(2)}ms`,
      commitTime: `${commitTime.toFixed(2)}ms`,
    });
  }
};
