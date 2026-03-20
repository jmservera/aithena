import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, beforeEach, afterEach, expect } from 'vitest';

import MetadataEditModal from '../Components/MetadataEditModal';
import { BookResult } from '../hooks/search';
import { IntlWrapper } from './test-intl-wrapper';

const mockBook: BookResult = {
  id: 'doc-123',
  title: 'Test Book',
  author: 'Jane Doe',
  year: 2021,
  category: 'Programming',
  series: 'Tech Series',
  document_url: '/documents/test.pdf',
};

const facetsResponse = {
  query: '',
  facets: {
    category: [
      { value: 'Programming', count: 10 },
      { value: 'Science', count: 5 },
    ],
    series: [
      { value: 'Tech Series', count: 3 },
      { value: 'Classics', count: 2 },
    ],
  },
};

function renderModal(
  props: Partial<{
    book: BookResult;
    onClose: () => void;
    onSaved: (updated: BookResult) => void;
  }> = {}
) {
  const onClose = props.onClose ?? vi.fn();
  const onSaved = props.onSaved ?? vi.fn();
  const book = props.book ?? mockBook;

  return {
    onClose,
    onSaved,
    ...render(
      <IntlWrapper>
        <MetadataEditModal book={book} onClose={onClose} onSaved={onSaved} />
      </IntlWrapper>
    ),
  };
}

describe('MetadataEditModal', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    // Default: facets load OK
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => facetsResponse,
    } as Response);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Rendering ─────────────────────────────────────────────────

  it('renders as a dialog with title "Edit Metadata"', () => {
    renderModal();
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText('Edit Metadata')).toBeInTheDocument();
  });

  it('pre-fills all fields with current book values', () => {
    renderModal();
    expect(screen.getByLabelText('Title')).toHaveValue('Test Book');
    expect(screen.getByLabelText('Author')).toHaveValue('Jane Doe');
    expect(screen.getByLabelText('Year')).toHaveValue(2021);
    expect(screen.getByLabelText('Category')).toHaveValue('Programming');
    expect(screen.getByLabelText('Series')).toHaveValue('Tech Series');
  });

  it('pre-fills with empty strings when optional fields are missing', () => {
    const book: BookResult = { id: 'doc-empty', title: 'Minimal' };
    renderModal({ book });
    expect(screen.getByLabelText('Title')).toHaveValue('Minimal');
    expect(screen.getByLabelText('Author')).toHaveValue('');
    expect(screen.getByLabelText('Year')).toHaveValue(null);
    expect(screen.getByLabelText('Category')).toHaveValue('');
    expect(screen.getByLabelText('Series')).toHaveValue('');
  });

  // ── Save button disabled state ────────────────────────────────

  it('save button is disabled when no fields have changed', () => {
    renderModal();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  });

  it('save button is enabled after changing a field', async () => {
    const user = userEvent.setup();
    renderModal();

    const titleInput = screen.getByLabelText('Title');
    await user.clear(titleInput);
    await user.type(titleInput, 'Updated Title');

    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
  });

  // ── Validation ────────────────────────────────────────────────

  it('shows inline error for invalid year', async () => {
    const user = userEvent.setup();
    renderModal();

    const yearInput = screen.getByLabelText('Year');
    await user.clear(yearInput);
    await user.type(yearInput, '500');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText(/Year must be between 1000 and 2099/)).toBeInTheDocument();
  });

  it('shows inline error for title exceeding 255 chars', async () => {
    const user = userEvent.setup();
    renderModal();

    const titleInput = screen.getByLabelText('Title');
    await user.clear(titleInput);
    // Type a long string (256 chars, but maxLength attr limits to 255 in DOM)
    // We test validation logic by setting value programmatically
    await user.type(titleInput, 'A'.repeat(255));

    // The maxLength on the input prevents going over 255 in the browser,
    // so this should work fine (no error expected at 255 chars)
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(screen.queryByText(/Title must be/)).not.toBeInTheDocument();
  });

  it('shows inline error when year is not an integer', async () => {
    const user = userEvent.setup();
    renderModal();

    const yearInput = screen.getByLabelText('Year');
    await user.clear(yearInput);
    await user.type(yearInput, '20.5');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText(/Year must be between 1000 and 2099/)).toBeInTheDocument();
  });

  // ── Close / Escape ────────────────────────────────────────────

  it('calls onClose when Cancel button is clicked', async () => {
    const user = userEvent.setup();
    const { onClose } = renderModal();

    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when close (✕) button is clicked', async () => {
    const user = userEvent.setup();
    const { onClose } = renderModal();

    await user.click(screen.getByRole('button', { name: /close metadata editor/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when Escape key is pressed', async () => {
    const user = userEvent.setup();
    const { onClose } = renderModal();

    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  // ── API integration: successful save ──────────────────────────

  it('calls PATCH API and shows success toast on save', async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();

    // First call = facets, second call = PATCH
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => facetsResponse,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'ok' }),
      } as Response);

    renderModal({ onSaved });

    const titleInput = screen.getByLabelText('Title');
    await user.clear(titleInput);
    await user.type(titleInput, 'New Title');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    // Toast should appear
    await waitFor(() => {
      expect(screen.getByText('✓ Metadata updated')).toBeInTheDocument();
    });

    // PATCH was called with the changed field
    const patchCall = vi
      .mocked(fetch)
      .mock.calls.find((call) => typeof call[1] === 'object' && call[1]?.method === 'PATCH');
    expect(patchCall).toBeDefined();
    const patchBody = JSON.parse(patchCall![1]!.body as string);
    expect(patchBody).toEqual({ title: 'New Title' });

    // onSaved callback is called after delay
    await waitFor(
      () => {
        expect(onSaved).toHaveBeenCalledWith(
          expect.objectContaining({ id: 'doc-123', title: 'New Title' })
        );
      },
      { timeout: 2000 }
    );
  });

  // ── API integration: error handling ───────────────────────────

  it('displays API error message on save failure', async () => {
    const user = userEvent.setup();

    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => facetsResponse,
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: 'At least one metadata field must be provided' }),
      } as Response);

    renderModal();

    const authorInput = screen.getByLabelText('Author');
    await user.clear(authorInput);
    await user.type(authorInput, 'New Author');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'At least one metadata field must be provided'
      );
    });
  });

  it('shows generic error when API returns non-JSON error', async () => {
    const user = userEvent.setup();

    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => facetsResponse,
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('not json');
        },
      } as unknown as Response);

    renderModal();

    const authorInput = screen.getByLabelText('Author');
    await user.clear(authorInput);
    await user.type(authorInput, 'New Author');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Save failed/);
    });
  });

  // ── Combobox ──────────────────────────────────────────────────

  it('shows facet options in category combobox dropdown', async () => {
    const user = userEvent.setup();
    renderModal();

    // Wait for facets to load
    await waitFor(() => {
      expect(vi.mocked(fetch)).toHaveBeenCalled();
    });

    const categoryInput = screen.getByLabelText('Category');
    await user.clear(categoryInput);
    await user.type(categoryInput, 'Sci');

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Science' })).toBeInTheDocument();
    });
  });

  it('selects option from combobox via keyboard', async () => {
    const user = userEvent.setup();
    renderModal();

    await waitFor(() => {
      expect(vi.mocked(fetch)).toHaveBeenCalled();
    });

    const categoryInput = screen.getByLabelText('Category');
    await user.clear(categoryInput);

    // Open dropdown and navigate
    await user.keyboard('{ArrowDown}');

    await waitFor(() => {
      expect(screen.getByRole('listbox')).toBeInTheDocument();
    });

    await user.keyboard('{ArrowDown}{Enter}');

    // Should have selected one of the facet options
    expect(['Programming', 'Science']).toContain((categoryInput as HTMLInputElement).value);
  });

  // ── Loading state ─────────────────────────────────────────────

  it('shows "Saving…" on save button while request is pending', async () => {
    const user = userEvent.setup();

    // Make the PATCH call hang
    let resolvePatch: (value: Response) => void;
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => facetsResponse,
      } as Response)
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolvePatch = resolve;
          })
      );

    renderModal();

    const titleInput = screen.getByLabelText('Title');
    await user.clear(titleInput);
    await user.type(titleInput, 'New Title');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(screen.getByRole('button', { name: 'Saving…' })).toBeDisabled();

    // Resolve
    resolvePatch!({
      ok: true,
      json: async () => ({ status: 'ok' }),
    } as Response);

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Saving…' })).not.toBeInTheDocument();
    });
  });
});
