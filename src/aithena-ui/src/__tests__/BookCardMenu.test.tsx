import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';

import BookCard from '../Components/BookCard';
import { BookResult } from '../hooks/search';
import { IntlWrapper } from './test-intl-wrapper';

const mockBook: BookResult = {
  id: 'doc-1',
  title: 'React Patterns',
  author: 'Jane Doe',
  year: 2022,
  category: 'Programming',
  series: 'Tech',
  document_url: '/documents/react.pdf',
};

describe('BookCard – admin menu', () => {
  it('does not show menu button when isAdmin is false', () => {
    render(
      <IntlWrapper>
        <BookCard book={mockBook} isAdmin={false} onEditMetadata={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.queryByRole('button', { name: /actions for/i })).not.toBeInTheDocument();
  });

  it('does not show menu button when onEditMetadata is not provided', () => {
    render(
      <IntlWrapper>
        <BookCard book={mockBook} isAdmin={true} />
      </IntlWrapper>
    );

    expect(screen.queryByRole('button', { name: /actions for/i })).not.toBeInTheDocument();
  });

  it('shows ⋮ menu button when isAdmin and onEditMetadata are both set', () => {
    render(
      <IntlWrapper>
        <BookCard book={mockBook} isAdmin={true} onEditMetadata={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.getByRole('button', { name: /actions for react patterns/i })).toBeInTheDocument();
  });

  it('opens menu with "Edit metadata" option on click', async () => {
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <BookCard book={mockBook} isAdmin={true} onEditMetadata={vi.fn()} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /actions for/i }));

    expect(screen.getByRole('menuitem', { name: /edit metadata/i })).toBeInTheDocument();
  });

  it('calls onEditMetadata with the book when "Edit metadata" is clicked', async () => {
    const user = userEvent.setup();
    const onEditMetadata = vi.fn();
    render(
      <IntlWrapper>
        <BookCard book={mockBook} isAdmin={true} onEditMetadata={onEditMetadata} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /actions for/i }));
    await user.click(screen.getByRole('menuitem', { name: /edit metadata/i }));

    expect(onEditMetadata).toHaveBeenCalledWith(mockBook);
  });

  it('closes menu when clicking outside', async () => {
    const user = userEvent.setup();
    render(
      <IntlWrapper>
        <BookCard book={mockBook} isAdmin={true} onEditMetadata={vi.fn()} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /actions for/i }));
    expect(screen.getByRole('menuitem', { name: /edit metadata/i })).toBeInTheDocument();

    // Click outside (on the article body)
    await user.click(screen.getByText('React Patterns'));

    expect(screen.queryByRole('menuitem', { name: /edit metadata/i })).not.toBeInTheDocument();
  });
});
