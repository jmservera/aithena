import { Suspense, lazy, type ReactNode } from 'react';
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

function renderLazyRoute(element: ReactNode, title: string, message: string) {
  return (
    <RouteErrorBoundary>
      <Suspense fallback={<LoadingSpinner title={title} message={message} />}>{element}</Suspense>
    </RouteErrorBoundary>
  );
}

function App() {
  return (
    <div className="App">
      <div className="app-header">
        <div className="app-branding">
          <h1 className="sidebar-title">📚 Aithena</h1>
          <p className="sidebar-subtitle">Book Library Search</p>
        </div>
        <TabNav />
      </div>
      <div className="app-content">
        <Routes>
          <Route
            path="/login"
            element={renderLazyRoute(
              <LoginPage />,
              'Loading sign in…',
              'Getting the sign-in view ready.'
            )}
          />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Navigate to="/search" replace />} />
            <Route
              path="/search"
              element={renderLazyRoute(
                <SearchPage />,
                'Loading search…',
                'Preparing your search workspace.'
              )}
            />
            <Route
              path="/library"
              element={renderLazyRoute(
                <LibraryPage />,
                'Loading library…',
                'Fetching your library view.'
              )}
            />
            <Route
              path="/upload"
              element={renderLazyRoute(
                <UploadPage />,
                'Loading upload…',
                'Preparing the upload tools.'
              )}
            />
            <Route
              path="/status"
              element={renderLazyRoute(
                <StatusPage />,
                'Loading status…',
                'Checking indexing and service status.'
              )}
            />
            <Route
              path="/stats"
              element={renderLazyRoute(
                <StatsPage />,
                'Loading statistics…',
                'Crunching the latest library numbers.'
              )}
            />
            <Route
              path="/admin"
              element={renderLazyRoute(
                <AdminPage />,
                'Loading admin…',
                'Getting the admin dashboard ready.'
              )}
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
