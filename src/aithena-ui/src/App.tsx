import { Suspense, lazy, type ReactNode } from 'react';
import { useIntl } from 'react-intl';
import './App.css';
import { Navigate, Route, Routes } from 'react-router-dom';
import Footer from './Components/Footer';
import { RouteErrorBoundary } from './Components/ErrorBoundary';
import LoadingSpinner from './Components/LoadingSpinner';
import ProtectedRoute from './Components/ProtectedRoute';
import TabNav from './Components/TabNav';

const SearchPage = lazy(() => import('./pages/SearchPage'));
const LibraryPage = lazy(() => import('./pages/LibraryPage'));
const UploadPage = lazy(() => import('./pages/UploadPage'));
const StatusPage = lazy(() => import('./pages/StatusPage'));
const StatsPage = lazy(() => import('./pages/StatsPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));

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
  return (
    <div className="App">
      <div className="app-header">
        <div className="app-branding">
          <h1 className="sidebar-title">📚 {intl.formatMessage({ id: 'app.title' })}</h1>
          <p className="sidebar-subtitle">{intl.formatMessage({ id: 'app.subtitle' })}</p>
        </div>
        <TabNav />
      </div>
      <div className="app-content">
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
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      <Footer />
    </div>
  );
}

export default App;
