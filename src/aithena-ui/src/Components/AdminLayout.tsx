import { Suspense } from 'react';
import { Outlet } from 'react-router-dom';
import { useIntl } from 'react-intl';
import AdminSidebar from './AdminSidebar';
import LoadingSpinner from './LoadingSpinner';
import { RouteErrorBoundary } from './ErrorBoundary';

function AdminLayout() {
  const intl = useIntl();

  return (
    <div className="admin-layout">
      <AdminSidebar />
      <main className="admin-layout-content">
        <RouteErrorBoundary>
          <Suspense
            fallback={
              <LoadingSpinner
                title={intl.formatMessage({ id: 'loading.admin' })}
                message={intl.formatMessage({ id: 'loading.adminMessage' })}
              />
            }
          >
            <Outlet />
          </Suspense>
        </RouteErrorBoundary>
      </main>
    </div>
  );
}

export default AdminLayout;
