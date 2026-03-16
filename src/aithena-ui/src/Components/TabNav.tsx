import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const TABS = [
  { to: '/search', label: '🔍 Search' },
  { to: '/library', label: '📖 Library' },
  { to: '/upload', label: '📤 Upload' },
  { to: '/status', label: '🟢 Status' },
  { to: '/stats', label: '📊 Stats' },
  { to: '/admin', label: '🛠️ Admin' },
];

function TabNav() {
  const { isAuthenticated, isLoading, logout, user } = useAuth();

  return (
    <nav className="tab-nav" aria-label="Main navigation">
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
              {tab.label}
            </NavLink>
          ))}
          <div className="tab-nav-actions">
            <span className="tab-nav-user">👤 {user?.username ?? 'Signed in'}</span>
            <button
              type="button"
              className="tab-nav-button"
              onClick={() => {
                void logout();
              }}
              disabled={isLoading}
            >
              Sign out
            </button>
          </div>
        </>
      ) : (
        <NavLink
          to="/login"
          className={({ isActive }) => 'tab-nav-link' + (isActive ? ' tab-nav-link--active' : '')}
        >
          🔐 Login
        </NavLink>
      )}
    </nav>
  );
}

export default TabNav;
