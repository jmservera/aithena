import { type FocusEvent, useCallback, useEffect, useId, useRef, useState } from 'react';
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
  ChevronDown,
  KeyRound,
  Users,
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
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const menuId = useId();
  const profileMenuId = useId();
  const profileRef = useRef<HTMLDivElement>(null);
  const { isAuthenticated, isLoading, logout, user } = useAuth();
  const menuLabel = intl.formatMessage({ id: 'nav.menuToggle' });

  const handleToggle = () => {
    setIsMenuOpen((open) => !open);
  };

  const handleClose = () => {
    setIsMenuOpen(false);
    setIsProfileOpen(false);
  };

  const handleProfileToggle = () => {
    setIsProfileOpen((open) => !open);
  };

  const handleProfileBlur = (e: FocusEvent<HTMLDivElement>) => {
    if (profileRef.current && !profileRef.current.contains(e.relatedTarget as Node)) {
      setIsProfileOpen(false);
    }
  };

  const closeProfile = useCallback(() => setIsProfileOpen(false), []);

  // Close profile dropdown on outside click or Escape key
  useEffect(() => {
    if (!isProfileOpen) return;

    const handleOutsideClick = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        closeProfile();
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeProfile();
    };

    document.addEventListener('click', handleOutsideClick);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('click', handleOutsideClick);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isProfileOpen, closeProfile]);

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
              <div className="profile-dropdown" ref={profileRef} onBlur={handleProfileBlur}>
                <button
                  type="button"
                  className="profile-dropdown-toggle"
                  aria-controls={profileMenuId}
                  aria-expanded={isProfileOpen}
                  onClick={handleProfileToggle}
                >
                  <User size={ICON_SIZE} aria-hidden="true" />{' '}
                  {user?.username ?? intl.formatMessage({ id: 'nav.signedIn' })}
                  <ChevronDown
                    size={14}
                    aria-hidden="true"
                    className={`profile-dropdown-chevron${isProfileOpen ? ' profile-dropdown-chevron--open' : ''}`}
                  />
                </button>
                {isProfileOpen && (
                  <div className="profile-dropdown-menu" id={profileMenuId} role="menu">
                    <NavLink
                      to="/profile"
                      className="profile-dropdown-item"
                      role="menuitem"
                      onClick={handleClose}
                    >
                      <User size={16} aria-hidden="true" />
                      {intl.formatMessage({ id: 'nav.profile' })}
                    </NavLink>
                    <NavLink
                      to="/profile/change-password"
                      className="profile-dropdown-item"
                      role="menuitem"
                      onClick={handleClose}
                    >
                      <KeyRound size={16} aria-hidden="true" />
                      {intl.formatMessage({ id: 'nav.changePassword' })}
                    </NavLink>
                    {user?.role === 'admin' && (
                      <NavLink
                        to="/admin/users"
                        className="profile-dropdown-item"
                        role="menuitem"
                        onClick={handleClose}
                      >
                        <Users size={16} aria-hidden="true" />
                        {intl.formatMessage({ id: 'nav.manageUsers' })}
                      </NavLink>
                    )}
                    <div className="profile-dropdown-divider" />
                    <button
                      type="button"
                      className="profile-dropdown-item profile-dropdown-item--logout"
                      role="menuitem"
                      onClick={() => {
                        handleClose();
                        void logout();
                      }}
                      disabled={isLoading}
                    >
                      {intl.formatMessage({ id: 'nav.signOut' })}
                    </button>
                  </div>
                )}
              </div>
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
