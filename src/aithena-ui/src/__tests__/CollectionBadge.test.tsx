import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import CollectionBadge from '../Components/CollectionBadge';
import { IntlWrapper } from './test-intl-wrapper';

describe('CollectionBadge', () => {
  it('renders nothing when count is 0', () => {
    const { container } = render(
      <IntlWrapper>
        <CollectionBadge count={0} />
      </IntlWrapper>
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when count is negative', () => {
    const { container } = render(
      <IntlWrapper>
        <CollectionBadge count={-1} />
      </IntlWrapper>
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders badge with count 1', () => {
    render(
      <IntlWrapper>
        <CollectionBadge count={1} />
      </IntlWrapper>
    );
    const badge = screen.getByText(/in 1/i);
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass('collection-badge');
  });

  it('renders badge with count 5', () => {
    render(
      <IntlWrapper>
        <CollectionBadge count={5} />
      </IntlWrapper>
    );
    expect(screen.getByText(/in 5/i)).toBeInTheDocument();
  });

  it('has accessible label', () => {
    render(
      <IntlWrapper>
        <CollectionBadge count={3} />
      </IntlWrapper>
    );
    const badge = screen.getByLabelText(/in 3 collection/i);
    expect(badge).toBeInTheDocument();
  });
});
