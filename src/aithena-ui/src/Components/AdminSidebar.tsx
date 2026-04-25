import { useCallback, useRef } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useIntl } from 'react-intl';
import {
  LayoutDashboard,
  FileText,
  RefreshCw,
  Activity,
  Server,
  ScrollText,
  Link2,
  Users,
  DatabaseBackup,
  type LucideIcon,
} from 'lucide-react';

interface NavItem {
  to: string;
  labelId: string;
  icon: LucideIcon;
}

interface NavGroup {
  titleId: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    titleId: 'adminSidebar.group.overview',
    items: [{ to: '/admin', labelId: 'adminSidebar.dashboard', icon: LayoutDashboard }],
  },
  {
    titleId: 'adminSidebar.group.documents',
    items: [{ to: '/admin/documents', labelId: 'adminSidebar.documents', icon: FileText }],
  },
  {
    titleId: 'adminSidebar.group.indexing',
    items: [
      { to: '/admin/reindex', labelId: 'adminSidebar.reindex', icon: RefreshCw },
      {
        to: '/admin/indexing-status',
        labelId: 'adminSidebar.indexingStatus',
        icon: Activity,
      },
    ],
  },
  {
    titleId: 'adminSidebar.group.system',
    items: [
      { to: '/admin/system-status', labelId: 'adminSidebar.systemStatus', icon: Server },
      { to: '/admin/logs', labelId: 'adminSidebar.logs', icon: ScrollText },
      {
        to: '/admin/infrastructure',
        labelId: 'adminSidebar.infrastructure',
        icon: Link2,
      },
    ],
  },
  {
    titleId: 'adminSidebar.group.management',
    items: [
      { to: '/admin/users', labelId: 'adminSidebar.users', icon: Users },
      { to: '/admin/backups', labelId: 'adminSidebar.backups', icon: DatabaseBackup },
    ],
  },
];

const ICON_SIZE = 18;

function AdminSidebar() {
  const intl = useIntl();
  const location = useLocation();
  const navRef = useRef<HTMLElement>(null);

  const allItems = NAV_GROUPS.flatMap((g) => g.items);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLAnchorElement>) => {
      const currentHref = (e.currentTarget as HTMLAnchorElement).getAttribute('href') ?? '';
      const currentIndex = allItems.findIndex((item) => item.to === currentHref);
      if (currentIndex === -1) return;

      let nextIndex: number;

      switch (e.key) {
        case 'ArrowDown':
          nextIndex = (currentIndex + 1) % allItems.length;
          break;
        case 'ArrowUp':
          nextIndex = (currentIndex - 1 + allItems.length) % allItems.length;
          break;
        case 'Home':
          nextIndex = 0;
          break;
        case 'End':
          nextIndex = allItems.length - 1;
          break;
        default:
          return;
      }

      e.preventDefault();
      const link = navRef.current?.querySelector<HTMLAnchorElement>(
        `a[href="${allItems[nextIndex].to}"]`
      );
      link?.focus();
    },
    [allItems]
  );

  return (
    <nav
      ref={navRef}
      className="admin-sidebar"
      aria-label={intl.formatMessage({ id: 'adminSidebar.ariaLabel' })}
    >
      {NAV_GROUPS.map((group) => (
        <div key={group.titleId} className="admin-sidebar-group">
          <h3 className="admin-sidebar-group-title">{intl.formatMessage({ id: group.titleId })}</h3>
          <ul className="admin-sidebar-list">
            {group.items.map((item) => {
              const isActive =
                item.to === '/admin'
                  ? location.pathname === '/admin'
                  : location.pathname.startsWith(item.to);
              return (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/admin'}
                    className={`admin-sidebar-link${isActive ? ' admin-sidebar-link--active' : ''}`}
                    aria-current={isActive ? 'page' : undefined}
                    onKeyDown={handleKeyDown}
                  >
                    <item.icon size={ICON_SIZE} aria-hidden="true" />
                    {intl.formatMessage({ id: item.labelId })}
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export default AdminSidebar;
