import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { IntlProvider } from 'react-intl';
import { SearchX } from 'lucide-react';
import EmptyState from '../Components/EmptyState';
import enMessages from '../locales/en.json';

function renderWithIntl(component: React.ReactElement) {
  return render(
    <IntlProvider locale="en" messages={enMessages}>
      {component}
    </IntlProvider>
  );
}

describe('EmptyState', () => {
  it('renders icon, title, and description', () => {
    renderWithIntl(
      <EmptyState
        icon={SearchX}
        titleId="search.emptyTitle"
        descriptionId="search.emptyDescription"
      />
    );

    expect(screen.getByText('Start your search')).toBeInTheDocument();
    expect(
      screen.getByText('Use keywords, author names, or topics to find books in the library.')
    ).toBeInTheDocument();
  });

  it('renders action button when provided', () => {
    const handleClick = vi.fn();
    renderWithIntl(
      <EmptyState
        icon={SearchX}
        titleId="search.emptyTitle"
        descriptionId="search.emptyDescription"
        action={{
          labelId: 'search.browseLibrary',
          onClick: handleClick,
        }}
      />
    );

    const button = screen.getByRole('button', { name: 'Browse Library' });
    expect(button).toBeInTheDocument();
    button.click();
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders action link when href is provided', () => {
    renderWithIntl(
      <EmptyState
        icon={SearchX}
        titleId="search.emptyTitle"
        descriptionId="search.emptyDescription"
        action={{
          labelId: 'search.browseLibrary',
          href: '/',
        }}
      />
    );

    const link = screen.getByRole('link', { name: 'Browse Library' });
    expect(link).toHaveAttribute('href', '/');
  });

  it('renders children when provided', () => {
    renderWithIntl(
      <EmptyState
        icon={SearchX}
        titleId="search.emptyTitle"
        descriptionId="search.emptyDescription"
      >
        <div data-testid="custom-content">Custom content</div>
      </EmptyState>
    );

    expect(screen.getByTestId('custom-content')).toBeInTheDocument();
  });

  it('has correct ARIA role', () => {
    const { container } = renderWithIntl(
      <EmptyState
        icon={SearchX}
        titleId="search.emptyTitle"
        descriptionId="search.emptyDescription"
      />
    );

    expect(container.querySelector('[role="status"]')).toBeInTheDocument();
  });
});
