import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect } from 'vitest';
import { ToastProvider, useToast } from '../contexts/ToastContext';
import ToastContainer from '../Components/ToastContainer';
import { IntlWrapper } from './test-intl-wrapper';

function TestTrigger() {
  const { addToast } = useToast();
  return (
    <>
      <button onClick={() => addToast('Success message', 'success')}>Add Success</button>
      <button onClick={() => addToast('Error message', 'error')}>Add Error</button>
    </>
  );
}

function renderWithToast() {
  return render(
    <IntlWrapper>
      <ToastProvider>
        <TestTrigger />
        <ToastContainer />
      </ToastProvider>
    </IntlWrapper>
  );
}

describe('Toast system', () => {
  it('renders no toasts initially', () => {
    renderWithToast();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('shows a success toast when triggered', async () => {
    const user = userEvent.setup();
    renderWithToast();

    await user.click(screen.getByText('Add Success'));

    expect(screen.getByText('Success message')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveClass('toast--success');
  });

  it('shows an error toast when triggered', async () => {
    const user = userEvent.setup();
    renderWithToast();

    await user.click(screen.getByText('Add Error'));

    expect(screen.getByText('Error message')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveClass('toast--error');
  });

  it('auto-dismisses after timeout', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithToast();

    await user.click(screen.getByText('Add Success'));
    expect(screen.getByText('Success message')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.queryByText('Success message')).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it('dismisses on click of dismiss button', async () => {
    const user = userEvent.setup();
    renderWithToast();

    await user.click(screen.getByText('Add Success'));
    expect(screen.getByText('Success message')).toBeInTheDocument();

    await user.click(screen.getByLabelText('Dismiss notification 1 of 1'));
    expect(screen.queryByText('Success message')).not.toBeInTheDocument();
  });

  it('can show multiple toasts', async () => {
    const user = userEvent.setup();
    renderWithToast();

    await user.click(screen.getByText('Add Success'));
    await user.click(screen.getByText('Add Error'));

    expect(screen.getByText('Success message')).toBeInTheDocument();
    expect(screen.getByText('Error message')).toBeInTheDocument();
  });
});
