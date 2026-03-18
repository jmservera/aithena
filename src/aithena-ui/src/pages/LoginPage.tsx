import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useIntl } from 'react-intl';
import { useAuth } from '../contexts/AuthContext';

interface LoginLocationState {
  from?: {
    pathname?: string;
  };
}

function LoginPage() {
  const intl = useIntl();
  const location = useLocation();
  const { login, isAuthenticated, isLoading, error, clearError } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const destination = useMemo(() => {
    const state = location.state as LoginLocationState | null;
    return state?.from?.pathname ?? '/search';
  }, [location.state]);

  useEffect(() => {
    clearError();
  }, [clearError]);

  if (isAuthenticated) {
    return <Navigate to={destination} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearError();

    try {
      await login(username, password);
    } catch {
      // The auth context exposes the error message for the form to render.
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-card-header">
          <h2 id="login-title" className="login-title">
            {intl.formatMessage({ id: 'login.title' })}
          </h2>
          <p className="login-description">{intl.formatMessage({ id: 'login.description' })}</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-label" htmlFor="username">
            {intl.formatMessage({ id: 'login.username' })}
          </label>
          <input
            id="username"
            className="login-input"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />

          <label className="login-label" htmlFor="password">
            {intl.formatMessage({ id: 'login.password' })}
          </label>
          <input
            id="password"
            className="login-input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          {error && (
            <div className="login-error" role="alert">
              {error}
            </div>
          )}

          <button
            className="login-button"
            type="submit"
            disabled={isLoading || !username.trim() || !password}
          >
            {isLoading
              ? intl.formatMessage({ id: 'login.signingIn' })
              : intl.formatMessage({ id: 'login.signIn' })}
          </button>
        </form>
      </section>
    </main>
  );
}

export default LoginPage;
