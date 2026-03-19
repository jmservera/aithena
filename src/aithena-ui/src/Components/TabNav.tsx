import { useId, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useIntl } from 'react-intl';
import {
  Search,
  BookOpen,
  Upload,
  CheckCircle,
  BarChart3,
  Wrench,
  User,
  Lock,
  Menu,
  X,
  type LucideIcon,
} from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';
import LanguageSwitcher from './LanguageSwitcher';

const ICON_SIZE = 20;

const TABS: { to: string; labelId: string; icon: LucideIcon }[] = [
  { to: '/search', labelId: 'nav.search', icon: Search },
  { to: '/library', labelId: 'nav.library', icon: BookOpen },
  { to: '/upload', labelId: 'nav.upload', icon: Upload },
  { to: '/status', labelId: 'nav.status', icon: CheckCircle },
  { to: '/stats', labelId: 'nav.stats', icon: BarChart3 },
  { to: '/admin', labelId: 'nav.admin', icon: Wrench },
];

function TabNav() {
  const intl = useIntl();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuId = useId();
  const { isAuthenticated, isLoading, logout, user } = useAuth();
  const menuLabel = intl.formatMessage({ id: 'nav.menuToggle' });

  const handleToggle = () => {
    setIsMenuOpen((open) => !open);
  };

  const handleClose = () => {
    setIsMenuOpen(false);
  };

  return (
    <nav className="tab-nav" aria-label={intl.formatMessage({ id: 'nav.mainNavigation' })}>
      <button
        type="button"
        className="tab-nav-toggle"
        aria-label={menuLabel}
        aria-controls={menuId}
        aria-expanded={isMenuOpen}
        title={menuLabel}
        onClick={handleToggle}
      >
        {isMenuOpen ? (
          <X size={ICON_SIZE} aria-hidden="true" />
        ) : (
          <Menu size={ICON_SIZE} aria-hidden="true" />
        )}
        <span className="visually-hidden">{menuLabel}</span>
      </button>
      <div className={`tab-nav-links${isMenuOpen ? ' tab-nav-links--open' : ''}`} id={menuId}>
        {isAuthenticated ? (
          <>
            {TABS.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                className={({ isActive }) =>
                  'tab-nav-link' + (isActive ? ' tab-nav-link--active' : '')
                }
                onClick={handleClose}
              >
                <tab.icon size={ICON_SIZE} aria-hidden="true" />{' '}
                {intl.formatMessage({ id: tab.labelId })}
              </NavLink>
            ))}
            <div className="tab-nav-actions">
              <LanguageSwitcher />
              <span className="tab-nav-user">
                <User size={ICON_SIZE} aria-hidden="true" />{' '}
                {user?.username ?? intl.formatMessage({ id: 'nav.signedIn' })}
              </span>
              <button
                type="button"
                className="tab-nav-button"
                onClick={() => {
                  handleClose();
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
            onClick={handleClose}
          >
            <Lock size={ICON_SIZE} aria-hidden="true" /> {intl.formatMessage({ id: 'nav.login' })}
          </NavLink>
        )}
      </div>
    </nav>
  );
}

export default TabNav;
