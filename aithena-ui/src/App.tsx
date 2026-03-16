import './App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import TabNav from './Components/TabNav';
import Footer from './Components/Footer';
import ProtectedRoute from './Components/ProtectedRoute';
import SearchPage from './pages/SearchPage';
import LibraryPage from './pages/LibraryPage';
import UploadPage from './pages/UploadPage';
import StatusPage from './pages/StatusPage';
import StatsPage from './pages/StatsPage';
import AdminPage from './pages/AdminPage';
import LoginPage from './pages/LoginPage';

function App() {
  return (
    <BrowserRouter>
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
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<Navigate to="/search" replace />} />
              <Route path="/search" element={<SearchPage />} />
              <Route path="/library" element={<LibraryPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/status" element={<StatusPage />} />
              <Route path="/stats" element={<StatsPage />} />
              <Route path="/admin" element={<AdminPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
        <Footer />
      </div>
    </BrowserRouter>
  );
}

export default App;
