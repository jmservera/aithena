import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ActiveFilters from '../Components/ActiveFilters';
import { IntlWrapper } from './test-intl-wrapper';

describe('ActiveFilters', () => {
  it('renders active filter chips', () => {
    render(
      <IntlWrapper>
        <ActiveFilters
          filters={{ author: 'Jane Doe', year: '2021' }}
          onRemove={vi.fn()}
          onClearAll={vi.fn()}
        />
      </IntlWrapper>
    );

    expect(screen.getByText('Active filters:')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('2021')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
  });

  it('calls onRemove for the selected filter chip', async () => {
    const onRemove = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <ActiveFilters filters={{ author: 'Jane Doe' }} onRemove={onRemove} onClearAll={vi.fn()} />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /remove author filter/i }));

    expect(onRemove).toHaveBeenCalledWith('author');
  });

  it('calls onClearAll when clearing multiple filters', async () => {
    const onClearAll = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <ActiveFilters
          filters={{ author: 'Jane Doe', category: 'Programming' }}
          onRemove={vi.fn()}
          onClearAll={onClearAll}
        />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /clear all/i }));

    expect(onClearAll).toHaveBeenCalledTimes(1);
  });
});
