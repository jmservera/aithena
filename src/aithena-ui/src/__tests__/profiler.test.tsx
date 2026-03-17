import { Profiler, PropsWithChildren } from 'react';
import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { onRenderCallback } from '../utils/profiler';

/* ------------------------------------------------------------------ */
/*  Helper: renders children inside a real React.Profiler              */
/* ------------------------------------------------------------------ */

function ProfilerWrapper({ children }: PropsWithChildren) {
  return (
    <Profiler id="Test" onRender={onRenderCallback}>
      {children}
    </Profiler>
  );
}

describe('Profiler utility', () => {
  let debugSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  /* ---------------------------------------------------------------- */
  /*  1. Children render correctly through <Profiler>                  */
  /* ---------------------------------------------------------------- */

  it('renders children without interfering with their output', () => {
    render(
      <ProfilerWrapper>
        <p>Hello from inside Profiler</p>
      </ProfilerWrapper>
    );

    expect(screen.getByText('Hello from inside Profiler')).toBeInTheDocument();
  });

  it('renders multiple children correctly', () => {
    render(
      <ProfilerWrapper>
        <h1>Title</h1>
        <p>Description</p>
        <button type="button">Action</button>
      </ProfilerWrapper>
    );

    expect(screen.getByText('Title')).toBeInTheDocument();
    expect(screen.getByText('Description')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  2. onRenderCallback fires in dev / test mode                     */
  /* ---------------------------------------------------------------- */

  it('logs profiling data via console.debug in dev mode', () => {
    // Vitest runs with import.meta.env.DEV === true by default.
    render(
      <ProfilerWrapper>
        <span>profiled</span>
      </ProfilerWrapper>
    );

    // React calls onRender at least once after the initial mount commit.
    expect(debugSpy).toHaveBeenCalled();

    const [tag, data] = debugSpy.mock.calls[0];
    expect(tag).toBe('[Profiler]');
    expect(data).toEqual(
      expect.objectContaining({
        id: 'Test',
        phase: 'mount',
        actualDuration: expect.stringMatching(/^\d+\.\d{2}ms$/),
        baseDuration: expect.stringMatching(/^\d+\.\d{2}ms$/),
        startTime: expect.stringMatching(/^\d+\.\d{2}ms$/),
        commitTime: expect.stringMatching(/^\d+\.\d{2}ms$/),
      })
    );
  });

  /* ---------------------------------------------------------------- */
  /*  3. onRenderCallback is a no-op when DEV is false                 */
  /* ---------------------------------------------------------------- */

  it('does not log when import.meta.env.DEV is false (production)', () => {
    // Temporarily override import.meta.env.DEV to simulate production.
    const original = import.meta.env.DEV;
    import.meta.env.DEV = false as unknown as boolean;

    try {
      // Call the callback directly to verify the guard.
      onRenderCallback('Prod', 'mount', 1.23, 4.56, 0, 10, new Set());
      expect(debugSpy).not.toHaveBeenCalled();
    } finally {
      import.meta.env.DEV = original;
    }
  });
});
