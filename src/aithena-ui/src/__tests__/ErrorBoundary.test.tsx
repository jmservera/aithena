import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Outlet, RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ErrorBoundary, { RouteErrorBoundary } from '../Components/ErrorBoundary';

const originalLocation = window.location;

function HealthyChild() {
  return <div>Healthy child content</div>;
}

function BrokenChild(): JSX.Element {
  throw new Error('Kaboom');
}

describe('ErrorBoundary', () => {
  let consoleSpy: ReturnType<typeof vi.spyOn>;
  let reloadSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    reloadSpy = vi.fn();
    consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...originalLocation,
        reload: reloadSpy,
      },
    });
  });

  afterEach(() => {
    consoleSpy.mockRestore();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('renders children when no error is thrown', () => {
    render(
      <ErrorBoundary>
        <HealthyChild />
      </ErrorBoundary>
    );

    expect(screen.getByText('Healthy child content')).toBeInTheDocument();
  });

  it('shows the fallback UI and logs the error when a child throws', () => {
    render(
      <ErrorBoundary>
        <BrokenChild />
      </ErrorBoundary>
    );

    expect(
      screen.getByRole('heading', { name: /aithena ran into a problem/i })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reload aithena/i })).toBeInTheDocument();
    expect(consoleSpy.mock.calls.some((call: unknown[]) => call[0] === 'Unhandled UI error')).toBe(
      true
    );
  });

  it('calls window.location.reload when the reload button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <ErrorBoundary>
        <BrokenChild />
      </ErrorBoundary>
    );

    await user.click(screen.getByRole('button', { name: /reload aithena/i }));

    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });

  it('resets after a route change when wrapped with RouteErrorBoundary', async () => {
    const router = createMemoryRouter(
      [
        {
          path: '/',
          element: (
            <RouteErrorBoundary>
              <Outlet />
            </RouteErrorBoundary>
          ),
          children: [
            { path: 'broken', element: <BrokenChild /> },
            { path: 'safe', element: <div>Recovered route content</div> },
          ],
        },
      ],
      { initialEntries: ['/broken'] }
    );

    render(<RouterProvider router={router} />);

    expect(
      screen.getByRole('heading', { name: /aithena ran into a problem/i })
    ).toBeInTheDocument();

    await act(async () => {
      await router.navigate('/safe');
    });

    expect(await screen.findByText('Recovered route content')).toBeInTheDocument();
  });
});
