import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AdminLayout from '../Components/AdminLayout';
import { IntlWrapper } from './test-intl-wrapper';

vi.mock('../Components/AdminSidebar', () => ({
  default: () => <nav data-testid="admin-sidebar">Sidebar</nav>,
}));

function renderLayout(initialPath = '/admin') {
  return render(
    <IntlWrapper>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={<AdminLayout />}>
            <Route path="/admin" element={<div>Dashboard Content</div>} />
            <Route path="/admin/users" element={<div>Users Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </IntlWrapper>
  );
}

describe('AdminLayout', () => {
  it('renders sidebar and child route', () => {
    renderLayout();

    expect(screen.getByTestId('admin-sidebar')).toBeInTheDocument();
    expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  });

  it('renders correct child for nested route', () => {
    renderLayout('/admin/users');

    expect(screen.getByTestId('admin-sidebar')).toBeInTheDocument();
    expect(screen.getByText('Users Content')).toBeInTheDocument();
  });
});
