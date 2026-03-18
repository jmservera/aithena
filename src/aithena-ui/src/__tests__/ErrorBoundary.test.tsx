import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useEffect, useState } from 'react';
import { Outlet, RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ErrorBoundary, {
  RouteErrorBoundary,
  type ErrorBoundaryFallbackProps,
} from '../Components/ErrorBoundary';
import { IntlWrapper } from './test-intl-wrapper';

const originalLocation = window.location;

function HealthyChild() {
  return <div>Healthy child content</div>;
}

function BrokenChild({ message = 'Kaboom' }: { message?: string }): never {
  throw new Error(message);
}

function StringBrokenChild(): never {
  throw 'String crash';
}

function ObjectBrokenChild(): never {
  throw { reason: 'Unknown crash' };
}

function AsyncBrokenChild() {
  const [shouldThrow, setShouldThrow] = useState(false);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setShouldThrow(true);
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, []);

  if (shouldThrow) {
    throw new Error('Async crash');
  }

  return <div>Waiting for async crash</div>;
}

function RetryableBoundary() {
  const [shouldThrow, setShouldThrow] = useState(true);

  return (
    <ErrorBoundary
      fallback={({ error, reset }: ErrorBoundaryFallbackProps) => (
        <div role="alert">
          <p>Captured error: {error?.message}</p>
          <button
            type="button"
            onClick={() => {
              setShouldThrow(false);
              reset();
            }}
          >
            Retry render
          </button>
        </div>
      )}
    >
      {shouldThrow ? <BrokenChild message="Retryable crash" /> : <HealthyChild />}
    </ErrorBoundary>
  );
}

describe('ErrorBoundary', () => {
  let reloadSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    reloadSpy = vi.fn();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...originalLocation,
        reload: reloadSpy,
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('renders children when no error is thrown', () => {
    render(
      <IntlWrapper>
        <ErrorBoundary>
          <HealthyChild />
        </ErrorBoundary>
      </IntlWrapper>
    );

    expect(screen.getByText('Healthy child content')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows the fallback UI when a child throws', async () => {
    render(
      <IntlWrapper>
        <ErrorBoundary>
          <BrokenChild message="Boundary crash" />
        </ErrorBoundary>
      </IntlWrapper>
    );

    const alert = await screen.findByRole('alert');

    expect(alert).toHaveAttribute('aria-live', 'assertive');
    expect(screen.getByRole('heading', { name: /something went wrong/i })).toBeInTheDocument();
    expect(screen.getByText(/an unexpected error occurred/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reload page/i })).toBeInTheDocument();
  });

  it('displays the captured error message in a custom fallback and recovers on retry', async () => {
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <RetryableBoundary />
      </IntlWrapper>
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Captured error: Retryable crash');

    await user.click(screen.getByRole('button', { name: /retry render/i }));

    await waitFor(() => {
      expect(screen.getByText('Healthy child content')).toBeInTheDocument();
    });

    expect(screen.queryByText(/captured error/i)).not.toBeInTheDocument();
  });

  it('normalizes non-Error throw values before passing them to a custom fallback', async () => {
    render(
      <IntlWrapper>
        <>
          <ErrorBoundary
            fallback={({ error }: ErrorBoundaryFallbackProps) => (
              <div role="alert">{error?.message}</div>
            )}
          >
            <StringBrokenChild />
          </ErrorBoundary>
          <ErrorBoundary
            fallback={({ error }: ErrorBoundaryFallbackProps) => (
              <div role="alert">{error?.message}</div>
            )}
          >
            <ObjectBrokenChild />
          </ErrorBoundary>
        </>
      </IntlWrapper>
    );

    const alerts = await screen.findAllByRole('alert');

    expect(alerts[0]).toHaveTextContent('String crash');
    expect(alerts[1]).toHaveTextContent('An unknown UI error occurred.');
  });

  it('calls window.location.reload when the reload button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <ErrorBoundary>
          <BrokenChild />
        </ErrorBoundary>
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /reload page/i }));

    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });

  it('renders fallback UI for an async crash triggered after mount', async () => {
    render(
      <IntlWrapper>
        <ErrorBoundary>
          <AsyncBrokenChild />
        </ErrorBoundary>
      </IntlWrapper>
    );

    expect(screen.getByText('Waiting for async crash')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByRole('heading', { name: /something went wrong/i })).toBeInTheDocument();
  });

  it('invokes componentDidCatch with the thrown error and component stack', async () => {
    const componentDidCatchSpy = vi.spyOn(ErrorBoundary.prototype, 'componentDidCatch');

    render(
      <IntlWrapper>
        <ErrorBoundary>
          <BrokenChild message="Lifecycle crash" />
        </ErrorBoundary>
      </IntlWrapper>
    );

    await screen.findByRole('alert');

    expect(componentDidCatchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Lifecycle crash' }),
      expect.objectContaining({ componentStack: expect.any(String) })
    );
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
            { path: 'broken', element: <BrokenChild message="Route crash" /> },
            { path: 'safe', element: <div>Recovered route content</div> },
          ],
        },
      ],
      { initialEntries: ['/broken'] }
    );

    render(
      <IntlWrapper>
        <RouterProvider router={router} />
      </IntlWrapper>
    );

    expect(
      await screen.findByRole('heading', { name: /something went wrong/i })
    ).toBeInTheDocument();

    await act(async () => {
      await router.navigate('/safe');
    });

    expect(await screen.findByText('Recovered route content')).toBeInTheDocument();
  });
});
