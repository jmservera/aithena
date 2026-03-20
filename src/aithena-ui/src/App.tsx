import { Suspense, lazy, useEffect, useRef, type ReactNode } from 'react';
import { useIntl } from 'react-intl';
import { Library } from 'lucide-react';
import './App.css';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Footer from './Components/Footer';
import ToastContainer from './Components/ToastContainer';
import { RouteErrorBoundary } from './Components/ErrorBoundary';
import LoadingSpinner from './Components/LoadingSpinner';
import ProtectedRoute from './Components/ProtectedRoute';
import AdminRoute from './Components/AdminRoute';
import TabNav from './Components/TabNav';

const SearchPage = lazy(() => import('./pages/SearchPage'));
const LibraryPage = lazy(() => import('./pages/LibraryPage'));
const CollectionsPage = lazy(() => import('./pages/CollectionsPage'));
const CollectionDetailPage = lazy(() => import('./pages/CollectionDetailPage'));
const UploadPage = lazy(() => import('./pages/UploadPage'));
const StatusPage = lazy(() => import('./pages/StatusPage'));
const StatsPage = lazy(() => import('./pages/StatsPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const ChangePasswordPage = lazy(() => import('./pages/ChangePasswordPage'));
const UserManagementPage = lazy(() => import('./pages/UserManagementPage'));

function LazyRoute({
  element,
  titleId,
  messageId,
}: {
  element: ReactNode;
  titleId: string;
  messageId: string;
}) {
  const intl = useIntl();
  return (
    <RouteErrorBoundary>
      <Suspense
        fallback={
          <LoadingSpinner
            title={intl.formatMessage({ id: titleId })}
            message={intl.formatMessage({ id: messageId })}
          />
        }
      >
        {element}
      </Suspense>
    </RouteErrorBoundary>
  );
}

function App() {
  const intl = useIntl();
  const location = useLocation();
  const mainRef = useRef<HTMLDivElement>(null);
  const isFirstRender = useRef(true);

  // Move focus to main content on route changes for screen readers
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    mainRef.current?.focus();
  }, [location.pathname]);

  return (
    <div className="App">
      <a href="#main-content" className="skip-to-content">
        {intl.formatMessage({ id: 'app.skipToContent' })}
      </a>
      <header className="app-header">
        <div className="app-branding">
          <h1 className="sidebar-title">
            <Library size={20} aria-hidden="true" /> {intl.formatMessage({ id: 'app.title' })}
          </h1>
          <p className="sidebar-subtitle">{intl.formatMessage({ id: 'app.subtitle' })}</p>
        </div>
        <TabNav />
      </header>
      <div className="app-content" id="main-content" ref={mainRef} tabIndex={-1}>
        <Routes>
          <Route
            path="/login"
            element={
              <LazyRoute
                element={<LoginPage />}
                titleId="loading.signIn"
                messageId="loading.signInMessage"
              />
            }
          />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Navigate to="/search" replace />} />
            <Route
              path="/search"
              element={
                <LazyRoute
                  element={<SearchPage />}
                  titleId="loading.search"
                  messageId="loading.searchMessage"
                />
              }
            />
            <Route
              path="/library"
              element={
                <LazyRoute
                  element={<LibraryPage />}
                  titleId="loading.library"
                  messageId="loading.libraryMessage"
                />
              }
            />
            <Route
              path="/collections"
              element={
                <LazyRoute
                  element={<CollectionsPage />}
                  titleId="loading.collections"
                  messageId="loading.collectionsMessage"
                />
              }
            />
            <Route
              path="/collections/:id"
              element={
                <LazyRoute
                  element={<CollectionDetailPage />}
                  titleId="loading.collections"
                  messageId="loading.collectionsMessage"
                />
              }
            />
            <Route
              path="/upload"
              element={
                <LazyRoute
                  element={<UploadPage />}
                  titleId="loading.upload"
                  messageId="loading.uploadMessage"
                />
              }
            />
            <Route
              path="/status"
              element={
                <LazyRoute
                  element={<StatusPage />}
                  titleId="loading.status"
                  messageId="loading.statusMessage"
                />
              }
            />
            <Route
              path="/stats"
              element={
                <LazyRoute
                  element={<StatsPage />}
                  titleId="loading.stats"
                  messageId="loading.statsMessage"
                />
              }
            />
            <Route
              path="/admin"
              element={
                <LazyRoute
                  element={<AdminPage />}
                  titleId="loading.admin"
                  messageId="loading.adminMessage"
                />
              }
            />
            <Route
              path="/profile"
              element={
                <LazyRoute
                  element={<ProfilePage />}
                  titleId="loading.profile"
                  messageId="loading.profileMessage"
                />
              }
            />
            <Route
              path="/profile/change-password"
              element={
                <LazyRoute
                  element={<ChangePasswordPage />}
                  titleId="loading.changePassword"
                  messageId="loading.changePasswordMessage"
                />
              }
            />
          </Route>
          <Route element={<AdminRoute />}>
            <Route
              path="/admin/users"
              element={
                <LazyRoute
                  element={<UserManagementPage />}
                  titleId="loading.users"
                  messageId="loading.usersMessage"
                />
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      <Footer />
      <ToastContainer />
    </div>
  );
}

export default App;
