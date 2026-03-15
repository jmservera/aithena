import './App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import TabNav from './Components/TabNav';
import SearchPage from './pages/SearchPage';
import LibraryPage from './pages/LibraryPage';
import StatusPage from './pages/StatusPage';
import StatsPage from './pages/StatsPage';
import AdminPage from './pages/AdminPage';

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
            <Route path="/" element={<Navigate to="/search" replace />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="/stats" element={<StatsPage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
