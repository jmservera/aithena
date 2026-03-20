import { FormEvent, useState } from 'react';
import { useIntl } from 'react-intl';
import { Link } from 'react-router-dom';
import { useChangePassword } from '../hooks/users';

function ChangePasswordPage() {
  const intl = useIntl();
  const { loading, error, success, changePassword, reset } = useChangePassword();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [clientError, setClientError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setClientError(null);
    reset();

    if (newPassword !== confirmPassword) {
      setClientError(intl.formatMessage({ id: 'changePassword.mismatch' }));
      return;
    }
    if (newPassword.length < 10) {
      setClientError(intl.formatMessage({ id: 'changePassword.tooShort' }));
      return;
    }

    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch {
      // Error is exposed via the hook's error state
    }
  }

  const displayError = clientError || error;

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="change-password-title">
        <div className="login-card-header">
          <h2 id="change-password-title" className="login-title">
            {intl.formatMessage({ id: 'changePassword.title' })}
          </h2>
          <p className="login-description">
            {intl.formatMessage({ id: 'changePassword.description' })}
          </p>
        </div>

        {success && (
          <div className="users-toast" role="status" style={{ marginBottom: 16 }}>
            {intl.formatMessage({ id: 'changePassword.success' })}
          </div>
        )}

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-label" htmlFor="current-password">
            {intl.formatMessage({
              id: 'changePassword.currentPassword',
            })}
          </label>
          <input
            id="current-password"
            className="login-input"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />

          <label className="login-label" htmlFor="new-password">
            {intl.formatMessage({ id: 'changePassword.newPassword' })}
          </label>
          <input
            id="new-password"
            className="login-input"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={10}
          />

          <label className="login-label" htmlFor="confirm-password">
            {intl.formatMessage({
              id: 'changePassword.confirmPassword',
            })}
          </label>
          <input
            id="confirm-password"
            className="login-input"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={10}
          />

          {displayError && (
            <div className="login-error" role="alert">
              {displayError}
            </div>
          )}

          <button
            className="login-button"
            type="submit"
            disabled={loading || !currentPassword || !newPassword || !confirmPassword}
          >
            {loading
              ? intl.formatMessage({ id: 'changePassword.saving' })
              : intl.formatMessage({ id: 'changePassword.submit' })}
          </button>

          <Link to="/profile" className="change-password-back-link">
            {intl.formatMessage({
              id: 'changePassword.backToProfile',
            })}
          </Link>
        </form>
      </section>
    </main>
  );
}

export default ChangePasswordPage;
