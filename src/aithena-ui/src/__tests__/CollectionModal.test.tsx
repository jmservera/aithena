import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';
import CollectionModal from '../Components/CollectionModal';
import { IntlWrapper } from './test-intl-wrapper';

describe('CollectionModal', () => {
  it('does not render when open is false', () => {
    render(
      <IntlWrapper>
        <CollectionModal
          open={false}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
          titleId="collections.createTitle"
          submitLabelId="collections.create"
        />
      </IntlWrapper>
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders the modal when open', () => {
    render(
      <IntlWrapper>
        <CollectionModal
          open={true}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
          titleId="collections.createTitle"
          submitLabelId="collections.create"
        />
      </IntlWrapper>
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Create Collection')).toBeInTheDocument();
  });

  it('pre-fills initial values', () => {
    render(
      <IntlWrapper>
        <CollectionModal
          open={true}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
          initialName="My Collection"
          initialDescription="Some description"
          titleId="collections.editTitle"
          submitLabelId="collections.save"
        />
      </IntlWrapper>
    );

    expect(screen.getByDisplayValue('My Collection')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Some description')).toBeInTheDocument();
  });

  it('calls onSubmit with name and description', async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <CollectionModal
          open={true}
          onClose={vi.fn()}
          onSubmit={onSubmit}
          titleId="collections.createTitle"
          submitLabelId="collections.create"
        />
      </IntlWrapper>
    );

    await user.type(screen.getByLabelText(/name/i), 'New Collection');
    await user.type(screen.getByLabelText(/description/i), 'A description');
    await user.click(screen.getByRole('button', { name: /create/i }));

    expect(onSubmit).toHaveBeenCalledWith('New Collection', 'A description');
  });

  it('disables submit when name is empty', () => {
    render(
      <IntlWrapper>
        <CollectionModal
          open={true}
          onClose={vi.fn()}
          onSubmit={vi.fn()}
          titleId="collections.createTitle"
          submitLabelId="collections.create"
        />
      </IntlWrapper>
    );

    const submitBtn = screen.getByRole('button', { name: /create/i });
    expect(submitBtn).toBeDisabled();
  });

  it('calls onClose when cancel is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <CollectionModal
          open={true}
          onClose={onClose}
          onSubmit={vi.fn()}
          titleId="collections.createTitle"
          submitLabelId="collections.create"
        />
      </IntlWrapper>
    );

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });
});
