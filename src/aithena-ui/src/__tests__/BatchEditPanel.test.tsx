import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { IntlWrapper } from './test-intl-wrapper';
import BatchEditPanel from '../Components/BatchEditPanel';

function renderPanel(props?: {
  documentIds?: string[];
  onClose?: () => void;
  onSaved?: () => void;
}) {
  return render(
    <IntlWrapper>
      <BatchEditPanel
        documentIds={props?.documentIds ?? ['doc-1', 'doc-2']}
        onClose={props?.onClose ?? vi.fn()}
        onSaved={props?.onSaved ?? vi.fn()}
      />
    </IntlWrapper>
  );
}

describe('BatchEditPanel', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ facets: { category: [], series: [] } }),
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.style.overflow = '';
  });

  it('renders with correct title showing document count', () => {
    renderPanel({ documentIds: ['a', 'b', 'c'] });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/batch edit.*3 books/i)).toBeInTheDocument();
  });

  it('renders instructions text', () => {
    renderPanel();
    expect(screen.getByText(/only fill in fields/i)).toBeInTheDocument();
  });

  it('renders 5 field toggle checkboxes', () => {
    renderPanel();
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes.length).toBeGreaterThanOrEqual(5);
  });

  it('has submit button disabled initially (no fields enabled)', () => {
    renderPanel();
    const submitBtn = screen.getByRole('button', { name: /apply changes/i });
    expect(submitBtn).toBeDisabled();
  });

  it('enables submit button when a field toggle is checked', async () => {
    const user = userEvent.setup();
    renderPanel();

    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[0]);

    const submitBtn = screen.getByRole('button', { name: /apply changes/i });
    expect(submitBtn).toBeEnabled();
  });

  it('shows preview when a field is enabled', async () => {
    const user = userEvent.setup();
    renderPanel();

    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[0]);

    await waitFor(() => {
      expect(screen.getByText(/preview/i)).toBeInTheDocument();
    });
  });

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderPanel({ onClose });

    await user.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when Escape is pressed', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderPanel({ onClose });

    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('locks body scroll when open', () => {
    renderPanel();
    expect(document.body.style.overflow).toBe('hidden');
  });

  it('submits batch edit and calls onSaved on success', async () => {
    const onSaved = vi.fn();
    const user = userEvent.setup();

    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ facets: { category: [], series: [] } }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ matched: 2, updated: 2, failed: 0, errors: [] }),
      } as Response);

    renderPanel({ documentIds: ['doc-1', 'doc-2'], onSaved });

    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[0]);

    const inputs = screen.getAllByRole('textbox');
    await user.type(inputs[0], 'New Title');

    await user.click(screen.getByRole('button', { name: /apply changes/i }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalledOnce();
    });
  });

  it('shows error when API returns failure', async () => {
    const user = userEvent.setup();

    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ facets: { category: [], series: [] } }),
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: async () => 'Internal Server Error',
      } as Response);

    renderPanel();

    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[0]);

    await user.click(screen.getByRole('button', { name: /apply changes/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('shows partial failure results', async () => {
    const user = userEvent.setup();

    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ facets: { category: [], series: [] } }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          matched: 2,
          updated: 1,
          failed: 1,
          errors: [{ document_id: 'doc-2', error: 'Not found' }],
        }),
      } as Response);

    renderPanel({ documentIds: ['doc-1', 'doc-2'] });

    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[0]);

    await user.click(screen.getByRole('button', { name: /apply changes/i }));

    await waitFor(() => {
      expect(screen.getByText(/1 failed/)).toBeInTheDocument();
    });
  });
});
