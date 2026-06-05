import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildSolrSecurityUrl } from '../hooks/useAdminInfrastructure';
import SecurityPage from '../pages/SecurityPage';
import { IntlWrapper } from './test-intl-wrapper';

const infrastructureResponse = {
  services: [
    {
      name: 'solr',
      status: 'up',
      admin_url: '/admin/solr/',
      description: 'Full-text search engine',
    },
  ],
  connections: { solr: 'solr:8983' },
};

function mockFetch(response: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => response,
  });
}

function renderPage() {
  return render(
    <IntlWrapper>
      <MemoryRouter>
        <SecurityPage />
      </MemoryRouter>
    </IntlWrapper>
  );
}

describe('SecurityPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('builds the Solr 10 security route from a proxied admin URL', () => {
    expect(buildSolrSecurityUrl('/admin/solr/')).toBe('/admin/solr/ui/#/~security');
    expect(buildSolrSecurityUrl('/admin/solr')).toBe('/admin/solr/ui/#/~security');
  });

  it('renders the Solr security CTA and app user link', async () => {
    vi.stubGlobal('fetch', mockFetch(infrastructureResponse));
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /open solr security ui/i })).toBeInTheDocument();
    });

    expect(
      screen.getByRole('heading', { level: 3, name: /simplified security ui/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 3, name: /solr users and roles/i })
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /manage aithena users/i })).toHaveAttribute(
      'href',
      '/admin/users'
    );
    expect(screen.getByRole('link', { name: /open solr security ui/i })).toHaveAttribute(
      'href',
      '/admin/solr/ui/#/~security'
    );
  });

  it('warns when Solr is reported down', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch({
        ...infrastructureResponse,
        services: [{ ...infrastructureResponse.services[0], status: 'down' }],
      })
    );
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Solr is currently reported as down/i)).toBeInTheDocument();
    });
  });

  it('refreshes infrastructure status on demand', async () => {
    const fetchMock = mockFetch(infrastructureResponse);
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    await user.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
  });
});
