import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.tsx';
import { RouteErrorBoundary } from './Components/ErrorBoundary';
import { AuthProvider } from './contexts/AuthContext';
//import "bootstrap/dist/css/bootstrap.min.css";
import './normal.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <RouteErrorBoundary>
          <App />
        </RouteErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
