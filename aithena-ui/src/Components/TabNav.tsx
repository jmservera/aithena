import { NavLink } from 'react-router-dom';

const TABS = [
  { to: '/search', label: '🔍 Search' },
  { to: '/library', label: '📖 Library' },
  { to: '/upload', label: '📤 Upload' },
  { to: '/status', label: '🟢 Status' },
  { to: '/stats', label: '📊 Stats' },
  { to: '/admin', label: '🛠️ Admin' },
];

function TabNav() {
  return (
    <nav className="tab-nav" aria-label="Main navigation">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) => 'tab-nav-link' + (isActive ? ' tab-nav-link--active' : '')}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}

export default TabNav;
