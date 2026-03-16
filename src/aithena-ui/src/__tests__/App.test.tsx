import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';

vi.mock('../pages/LoginPage', async () => {
  await new Promise((resolve) => setTimeout(resolve, 50));

  return {
    default: function MockLoginPage() {
      return <div>Login page ready</div>;
    },
  };
});

describe('App', () => {
  it('shows a loading state while a lazy route is being fetched', async () => {
    const { default: App } = await import('../App');

    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    );

    expect(screen.getByRole('status')).toHaveTextContent(/loading sign in/i);
    expect(await screen.findByText('Login page ready')).toBeInTheDocument();
  });
});
