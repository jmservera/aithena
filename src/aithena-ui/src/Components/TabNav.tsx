import { NavLink } from 'react-router-dom';
import { useIntl } from 'react-intl';

import { useAuth } from '../contexts/AuthContext';
import LanguageSwitcher from './LanguageSwitcher';

const TABS = [
  { to: '/search', labelId: 'nav.search', emoji: '🔍' },
  { to: '/library', labelId: 'nav.library', emoji: '📖' },
  { to: '/upload', labelId: 'nav.upload', emoji: '📤' },
  { to: '/status', labelId: 'nav.status', emoji: '🟢' },
  { to: '/stats', labelId: 'nav.stats', emoji: '📊' },
  { to: '/admin', labelId: 'nav.admin', emoji: '🛠️' },
];

function TabNav() {
  const intl = useIntl();
  const { isAuthenticated, isLoading, logout, user } = useAuth();

  return (
    <nav className="tab-nav" aria-label={intl.formatMessage({ id: 'nav.mainNavigation' })}>
      {isAuthenticated ? (
        <>
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                'tab-nav-link' + (isActive ? ' tab-nav-link--active' : '')
              }
            >
              {tab.emoji} {intl.formatMessage({ id: tab.labelId })}
            </NavLink>
          ))}
          <div className="tab-nav-actions">
            <LanguageSwitcher />
            <span className="tab-nav-user">
              👤 {user?.username ?? intl.formatMessage({ id: 'nav.signedIn' })}
            </span>
            <button
              type="button"
              className="tab-nav-button"
              onClick={() => {
                void logout();
              }}
              disabled={isLoading}
            >
              {intl.formatMessage({ id: 'nav.signOut' })}
            </button>
          </div>
        </>
      ) : (
        <NavLink
          to="/login"
          className={({ isActive }) => 'tab-nav-link' + (isActive ? ' tab-nav-link--active' : '')}
        >
          🔐 {intl.formatMessage({ id: 'nav.login' })}
        </NavLink>
      )}
    </nav>
  );
}

export default TabNav;
