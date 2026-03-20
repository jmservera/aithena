import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';
import NoteEditor from '../Components/NoteEditor';
import { IntlWrapper } from './test-intl-wrapper';

describe('NoteEditor', () => {
  it('renders textarea with initial note', () => {
    render(
      <IntlWrapper>
        <NoteEditor
          itemId="item-1"
          collectionId="col-1"
          initialNote="Hello world"
          onSave={vi.fn()}
        />
      </IntlWrapper>
    );

    const textarea = screen.getByRole('textbox', { name: /note/i });
    expect(textarea).toHaveValue('Hello world');
  });

  it('calls onSave when text changes', async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <NoteEditor itemId="item-1" collectionId="col-1" initialNote="" onSave={onSave} />
      </IntlWrapper>
    );

    const textarea = screen.getByRole('textbox', { name: /note/i });
    await user.type(textarea, 'New note');

    // onSave called for each character
    expect(onSave).toHaveBeenCalled();
    expect(onSave).toHaveBeenLastCalledWith('item-1', 'New note');
  });

  it('shows character count', () => {
    render(
      <IntlWrapper>
        <NoteEditor itemId="item-1" collectionId="col-1" initialNote="Hi" onSave={vi.fn()} />
      </IntlWrapper>
    );

    expect(screen.getByText('2/5000')).toBeInTheDocument();
  });

  it('enforces max length of 5000 characters', async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();

    render(
      <IntlWrapper>
        <NoteEditor itemId="item-1" collectionId="col-1" initialNote="" onSave={onSave} />
      </IntlWrapper>
    );

    const textarea = screen.getByRole('textbox', { name: /note/i });
    expect(textarea).toHaveAttribute('maxLength', '5000');
    // Type normally - the maxLength attribute is set on the textarea
    await user.type(textarea, 'A');
    expect(onSave).toHaveBeenLastCalledWith('item-1', 'A');
  });

  it('shows saving indicator when saving prop is true', () => {
    render(
      <IntlWrapper>
        <NoteEditor
          itemId="item-1"
          collectionId="col-1"
          initialNote=""
          onSave={vi.fn()}
          saving={true}
        />
      </IntlWrapper>
    );

    expect(screen.getByText(/saving/i)).toBeInTheDocument();
  });
});
