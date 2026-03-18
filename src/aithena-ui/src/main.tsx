import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './design-tokens.css';
import './normal.css';
import App from './App.tsx';
import { RouteErrorBoundary } from './Components/ErrorBoundary';
import { AuthProvider } from './contexts/AuthContext';
import { I18nProvider } from './contexts/I18nContext';

async function bootstrap() {
  if (import.meta.env.DEV) {
    const [{ default: axe }, ReactDOMRuntime] = await Promise.all([
      import('@axe-core/react'),
      import('react-dom'),
    ]);

    await axe(React, ReactDOMRuntime, 1000);
  }

  const rootElement = document.getElementById('root');
  if (!rootElement) {
    throw new Error('Root element not found');
  }

  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <I18nProvider>
        <BrowserRouter>
          <AuthProvider>
            <RouteErrorBoundary>
              <App />
            </RouteErrorBoundary>
          </AuthProvider>
        </BrowserRouter>
      </I18nProvider>
    </React.StrictMode>
  );
}

void bootstrap();
