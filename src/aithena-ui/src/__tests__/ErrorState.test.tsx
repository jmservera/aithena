import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { IntlProvider } from 'react-intl';
import ErrorState from '../Components/ErrorState';
import enMessages from '../locales/en.json';

function renderWithIntl(component: React.ReactElement) {
  return render(
    <IntlProvider locale="en" messages={enMessages}>
      {component}
    </IntlProvider>
  );
}

describe('ErrorState', () => {
  it('categorizes network errors correctly', () => {
    renderWithIntl(<ErrorState error="Network request failed" />);

    expect(screen.getByText('Connection error')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Unable to connect to the server. Please check your network connection and try again.'
      )
    ).toBeInTheDocument();
  });

  it('categorizes server errors correctly', () => {
    renderWithIntl(<ErrorState error="500 Internal Server Error" />);

    expect(screen.getByText('Server error')).toBeInTheDocument();
    expect(
      screen.getByText('The server encountered an error. Please try again in a few moments.')
    ).toBeInTheDocument();
  });

  it('categorizes timeout errors correctly', () => {
    renderWithIntl(<ErrorState error="Request timed out" />);

    expect(screen.getByText('Request timeout')).toBeInTheDocument();
    expect(
      screen.getByText('The request took too long to complete. Please try again.')
    ).toBeInTheDocument();
  });

  it('categorizes generic errors correctly', () => {
    renderWithIntl(<ErrorState error="Something unexpected happened" />);

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(
      screen.getByText('An unexpected error occurred. Please try again or reload the page.')
    ).toBeInTheDocument();
  });

  it('accepts Error objects', () => {
    const error = new Error('Network failure');
    renderWithIntl(<ErrorState error={error} />);

    expect(screen.getByText('Connection error')).toBeInTheDocument();
  });

  it('respects explicit category override', () => {
    renderWithIntl(<ErrorState error="Some error" category="server" />);

    expect(screen.getByText('Server error')).toBeInTheDocument();
  });

  it('renders retry button when onRetry is provided', () => {
    const handleRetry = vi.fn();
    renderWithIntl(<ErrorState error="Network error" onRetry={handleRetry} />);

    const button = screen.getByRole('button', { name: 'Retry' });
    expect(button).toBeInTheDocument();
    button.click();
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it('does not render retry button when onRetry is not provided', () => {
    renderWithIntl(<ErrorState error="Network error" />);

    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });

  it('renders children when provided', () => {
    renderWithIntl(
      <ErrorState error="Network error">
        <div data-testid="custom-content">Custom content</div>
      </ErrorState>
    );

    expect(screen.getByTestId('custom-content')).toBeInTheDocument();
  });

  it('has correct ARIA role', () => {
    const { container } = renderWithIntl(<ErrorState error="Network error" />);

    expect(container.querySelector('[role="alert"]')).toBeInTheDocument();
  });
});
