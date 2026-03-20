import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';
import ConfirmDialog from '../Components/ConfirmDialog';
import { IntlWrapper } from './test-intl-wrapper';

describe('ConfirmDialog', () => {
  it('does not render when open is false', () => {
    render(
      <IntlWrapper>
        <ConfirmDialog
          open={false}
          titleId="collections.deleteTitle"
          messageId="collections.deleteConfirm"
          messageValues={{ name: 'Test' }}
          confirmLabelId="collections.delete"
          onConfirm={vi.fn()}
          onCancel={vi.fn()}
        />
      </IntlWrapper>
    );

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('renders when open', () => {
    render(
      <IntlWrapper>
        <ConfirmDialog
          open={true}
          titleId="collections.deleteTitle"
          messageId="collections.deleteConfirm"
          messageValues={{ name: 'My Collection' }}
          confirmLabelId="collections.delete"
          onConfirm={vi.fn()}
          onCancel={vi.fn()}
        />
      </IntlWrapper>
    );

    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    expect(screen.getByText('Delete Collection')).toBeInTheDocument();
    expect(
      screen.getByText(/are you sure you want to delete "My Collection"/i)
    ).toBeInTheDocument();
  });

  it('calls onConfirm when confirm button is clicked', async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <ConfirmDialog
          open={true}
          titleId="collections.deleteTitle"
          messageId="collections.deleteConfirm"
          messageValues={{ name: 'Test' }}
          confirmLabelId="collections.delete"
          onConfirm={onConfirm}
          onCancel={vi.fn()}
        />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /delete/i }));
    expect(onConfirm).toHaveBeenCalled();
  });

  it('calls onCancel when cancel button is clicked', async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <ConfirmDialog
          open={true}
          titleId="collections.deleteTitle"
          messageId="collections.deleteConfirm"
          messageValues={{ name: 'Test' }}
          confirmLabelId="collections.delete"
          onConfirm={vi.fn()}
          onCancel={onCancel}
        />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalled();
  });
});
