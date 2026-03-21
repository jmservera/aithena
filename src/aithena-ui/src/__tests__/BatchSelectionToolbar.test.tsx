import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { IntlWrapper } from './test-intl-wrapper';
import BatchSelectionToolbar from '../Components/BatchSelectionToolbar';

function renderToolbar(props: {
  selectedCount: number;
  onEdit?: () => void;
  onClearSelection?: () => void;
}) {
  return render(
    <IntlWrapper>
      <BatchSelectionToolbar
        selectedCount={props.selectedCount}
        onEdit={props.onEdit ?? vi.fn()}
        onClearSelection={props.onClearSelection ?? vi.fn()}
      />
    </IntlWrapper>
  );
}

describe('BatchSelectionToolbar', () => {
  it('renders nothing when selectedCount is 0', () => {
    const { container } = renderToolbar({ selectedCount: 0 });
    expect(container.innerHTML).toBe('');
  });

  it('renders toolbar with count when items are selected', () => {
    renderToolbar({ selectedCount: 3 });
    expect(screen.getByRole('toolbar')).toBeInTheDocument();
    expect(screen.getByText(/3 selected/)).toBeInTheDocument();
  });

  it('renders edit button with count', () => {
    renderToolbar({ selectedCount: 5 });
    expect(screen.getByText(/edit selected.*5/i)).toBeInTheDocument();
  });

  it('calls onEdit when edit button is clicked', async () => {
    const onEdit = vi.fn();
    const user = userEvent.setup();
    renderToolbar({ selectedCount: 2, onEdit });

    await user.click(screen.getByText(/edit selected/i));
    expect(onEdit).toHaveBeenCalledOnce();
  });

  it('calls onClearSelection when clear button is clicked', async () => {
    const onClearSelection = vi.fn();
    const user = userEvent.setup();
    renderToolbar({ selectedCount: 2, onClearSelection });

    await user.click(screen.getByText(/clear/i));
    expect(onClearSelection).toHaveBeenCalledOnce();
  });

  it('has correct aria-label on toolbar', () => {
    renderToolbar({ selectedCount: 1 });
    expect(screen.getByRole('toolbar')).toHaveAttribute('aria-label', 'Batch selection actions');
  });
});
