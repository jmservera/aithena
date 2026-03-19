import { useIntl } from 'react-intl';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

function formatTimestamp(ts?: string): string {
  if (!ts) return '\u2014';
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function ProfilePage() {
  const intl = useIntl();
  const { user } = useAuth();

  // created_at may be available on the user object from the API
  const createdAt = (user as unknown as { created_at?: string } | null)?.created_at ?? undefined;

  return (
    <main className="profile-page">
      <section className="profile-card" aria-labelledby="profile-title">
        <h2 id="profile-title" className="profile-title">
          {intl.formatMessage({ id: 'profile.title' })}
        </h2>

        <dl className="profile-details">
          <div className="profile-detail-row">
            <dt className="profile-detail-label">
              {intl.formatMessage({ id: 'profile.username' })}
            </dt>
            <dd className="profile-detail-value">{user?.username ?? '\u2014'}</dd>
          </div>
          <div className="profile-detail-row">
            <dt className="profile-detail-label">{intl.formatMessage({ id: 'profile.role' })}</dt>
            <dd className="profile-detail-value">
              <span className={`users-role-badge users-role-badge--${user?.role ?? 'user'}`}>
                {user?.role ?? '\u2014'}
              </span>
            </dd>
          </div>
          <div className="profile-detail-row">
            <dt className="profile-detail-label">
              {intl.formatMessage({ id: 'profile.createdAt' })}
            </dt>
            <dd className="profile-detail-value">{formatTimestamp(createdAt)}</dd>
          </div>
        </dl>

        <div className="profile-actions">
          <Link to="/profile/change-password" className="admin-btn admin-btn--primary">
            {intl.formatMessage({ id: 'profile.changePassword' })}
          </Link>
        </div>
      </section>
    </main>
  );
}

export default ProfilePage;
