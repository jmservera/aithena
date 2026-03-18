import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { IntlProvider as ReactIntlProvider } from 'react-intl';
import enMessages from '../locales/en.json';
import esMessages from '../locales/es.json';
import caMessages from '../locales/ca.json';
import frMessages from '../locales/fr.json';

export type Locale = 'en' | 'es' | 'ca' | 'fr';

const MESSAGES: Record<Locale, Record<string, string>> = {
  en: enMessages,
  es: esMessages,
  ca: caMessages,
  fr: frMessages,
};

const SUPPORTED_LOCALES: Locale[] = ['en', 'es', 'ca', 'fr'];
const DEFAULT_LOCALE: Locale = 'en';
const LOCALE_STORAGE_KEY = 'aithena.locale';
const LEGACY_LOCALE_STORAGE_KEY = 'aithena-locale';

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

const I18nContext = createContext<I18nContextValue | undefined>(undefined);

// eslint-disable-next-line react-refresh/only-export-components
export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
}

/**
 * Detect the user's preferred locale with fallback chain:
 * 1. localStorage preference
 * 2. Browser locale (navigator.language)
 * 3. English (default)
 */
function detectLocale(): Locale {
  // Check localStorage first
  const storedLocale = localStorage.getItem(LOCALE_STORAGE_KEY);
  if (storedLocale && SUPPORTED_LOCALES.includes(storedLocale as Locale)) {
    return storedLocale as Locale;
  }

  // Migrate from legacy key (aithena-locale → aithena.locale)
  const legacyLocale = localStorage.getItem(LEGACY_LOCALE_STORAGE_KEY);
  if (legacyLocale && SUPPORTED_LOCALES.includes(legacyLocale as Locale)) {
    localStorage.setItem(LOCALE_STORAGE_KEY, legacyLocale);
    localStorage.removeItem(LEGACY_LOCALE_STORAGE_KEY);
    return legacyLocale as Locale;
  }

  // Check browser locale
  const browserLocale = navigator.language.toLowerCase();

  // Try exact match first (e.g., 'en', 'es', 'ca', 'fr')
  if (SUPPORTED_LOCALES.includes(browserLocale as Locale)) {
    return browserLocale as Locale;
  }

  // Try language prefix match (e.g., 'en-US' -> 'en')
  const languagePrefix = browserLocale.split('-')[0] as Locale;
  if (SUPPORTED_LOCALES.includes(languagePrefix)) {
    return languagePrefix;
  }

  // Fallback to default
  return DEFAULT_LOCALE;
}

interface I18nProviderProps {
  children: ReactNode;
}

export function I18nProvider({ children }: I18nProviderProps) {
  const [locale, setLocaleState] = useState<Locale>(detectLocale);

  const setLocale = (newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem(LOCALE_STORAGE_KEY, newLocale);
  };

  // Sync locale changes to localStorage
  useEffect(() => {
    localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  }, [locale]);

  const messages = MESSAGES[locale];

  return (
    <I18nContext.Provider value={{ locale, setLocale }}>
      <ReactIntlProvider locale={locale} messages={messages} defaultLocale={DEFAULT_LOCALE}>
        {children}
      </ReactIntlProvider>
    </I18nContext.Provider>
  );
}
