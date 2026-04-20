import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import AdminSidebar from '../Components/AdminSidebar';
import { IntlWrapper } from './test-intl-wrapper';

function renderSidebar(initialPath = '/admin') {
  return render(
    <IntlWrapper>
      <MemoryRouter initialEntries={[initialPath]}>
        <AdminSidebar />
      </MemoryRouter>
    </IntlWrapper>
  );
}

describe('AdminSidebar', () => {
  it('renders all navigation groups', () => {
    renderSidebar();

    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Documents')).toBeInTheDocument();
    expect(screen.getByText('Indexing')).toBeInTheDocument();
    expect(screen.getByText('System')).toBeInTheDocument();
    expect(screen.getByText('Management')).toBeInTheDocument();
  });

  it('renders all navigation links', () => {
    renderSidebar();

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Document Manager')).toBeInTheDocument();
    expect(screen.getByText('Reindex Library')).toBeInTheDocument();
    expect(screen.getByText('Indexing Status')).toBeInTheDocument();
    expect(screen.getByText('System Status')).toBeInTheDocument();
    expect(screen.getByText('Log Viewer')).toBeInTheDocument();
    expect(screen.getByText('Infrastructure')).toBeInTheDocument();
    expect(screen.getByText('User Management')).toBeInTheDocument();
    expect(screen.getByText('Backup Dashboard')).toBeInTheDocument();
  });

  it('highlights the active route', () => {
    renderSidebar('/admin');

    const dashboardLink = screen.getByText('Dashboard').closest('a');
    expect(dashboardLink).toHaveClass('admin-sidebar-link--active');
    expect(dashboardLink).toHaveAttribute('aria-current', 'page');
  });

  it('highlights a nested active route', () => {
    renderSidebar('/admin/users');

    const usersLink = screen.getByText('User Management').closest('a');
    expect(usersLink).toHaveClass('admin-sidebar-link--active');

    const dashboardLink = screen.getByText('Dashboard').closest('a');
    expect(dashboardLink).not.toHaveClass('admin-sidebar-link--active');
  });

  it('has accessible navigation landmark', () => {
    renderSidebar();

    expect(screen.getByRole('navigation', { name: /admin navigation/i })).toBeInTheDocument();
  });

  it('supports keyboard navigation with arrow keys', async () => {
    renderSidebar('/admin');
    const user = userEvent.setup();

    const dashboardLink = screen.getByText('Dashboard').closest('a')!;
    dashboardLink.focus();

    await user.keyboard('{ArrowDown}');
    expect(document.activeElement).toBe(screen.getByText('Document Manager').closest('a'));

    await user.keyboard('{ArrowDown}');
    expect(document.activeElement).toBe(screen.getByText('Reindex Library').closest('a'));

    await user.keyboard('{ArrowUp}');
    expect(document.activeElement).toBe(screen.getByText('Document Manager').closest('a'));
  });

  it('supports Home and End keyboard navigation', async () => {
    renderSidebar('/admin');
    const user = userEvent.setup();

    const dashboardLink = screen.getByText('Dashboard').closest('a')!;
    dashboardLink.focus();

    await user.keyboard('{End}');
    expect(document.activeElement).toBe(screen.getByText('Backup Dashboard').closest('a'));

    await user.keyboard('{Home}');
    expect(document.activeElement).toBe(screen.getByText('Dashboard').closest('a'));
  });
});
