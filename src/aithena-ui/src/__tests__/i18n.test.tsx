import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, beforeEach, afterEach, expect } from 'vitest';
import { FormattedMessage } from 'react-intl';
import { I18nProvider, useI18n, type Locale } from '../contexts/I18nContext';
import LanguageSwitcher from '../Components/LanguageSwitcher';
import enMessages from '../locales/en.json';
import esMessages from '../locales/es.json';
import caMessages from '../locales/ca.json';
import frMessages from '../locales/fr.json';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const LOCALE_FILES: Record<string, Record<string, string>> = {
  en: enMessages,
  es: esMessages,
  ca: caMessages,
  fr: frMessages,
};

const LOCALE_STORAGE_KEY = 'aithena-locale';

/** Simple component that displays a translated message so we can assert text. */
function TranslatedLabel() {
  return (
    <span data-testid="label">
      <FormattedMessage id="app.subtitle" />
    </span>
  );
}

/** Exposes the current locale from the I18n context for assertions. */
function LocaleDisplay() {
  const { locale } = useI18n();
  return <span data-testid="current-locale">{locale}</span>;
}

/** Exposes a button to programmatically set locale. */
function LocaleSetter({ target }: { target: Locale }) {
  const { setLocale } = useI18n();
  return <button onClick={() => setLocale(target)}>switch</button>;
}

// ---------------------------------------------------------------------------
// 1. Translation completeness — every key in en.json exists in other locales
// ---------------------------------------------------------------------------

describe('Translation completeness', () => {
  const enKeys = Object.keys(enMessages).sort();

  it.each([
    ['es', esMessages],
    ['ca', caMessages],
    ['fr', frMessages],
  ])('%s locale has all keys from en.json', (_locale, messages) => {
    const localeKeys = Object.keys(messages).sort();
    expect(localeKeys).toEqual(enKeys);
  });

  it.each([
    ['es', esMessages],
    ['ca', caMessages],
    ['fr', frMessages],
  ])('%s locale has no extra keys beyond en.json', (_locale, messages) => {
    const extraKeys = Object.keys(messages).filter((k) => !(k in enMessages));
    expect(extraKeys).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// 2. No empty translations
// ---------------------------------------------------------------------------

describe('No empty translations', () => {
  it.each(Object.entries(LOCALE_FILES))(
    '%s locale has no empty string values',
    (_locale, messages) => {
      const emptyKeys = Object.entries(messages)
        .filter(([, value]) => value.trim() === '')
        .map(([key]) => key);
      expect(emptyKeys).toEqual([]);
    }
  );
});

// ---------------------------------------------------------------------------
// 3. Locale switching via I18nContext
// ---------------------------------------------------------------------------

describe('Locale switching via I18nContext', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('defaults to English', () => {
    render(
      <I18nProvider>
        <LocaleDisplay />
        <TranslatedLabel />
      </I18nProvider>
    );

    expect(screen.getByTestId('current-locale')).toHaveTextContent('en');
    expect(screen.getByTestId('label')).toHaveTextContent(enMessages['app.subtitle']);
  });

  it('switches from en to es and updates displayed text', async () => {
    const user = userEvent.setup();

    render(
      <I18nProvider>
        <LocaleDisplay />
        <TranslatedLabel />
        <LocaleSetter target="es" />
      </I18nProvider>
    );

    expect(screen.getByTestId('label')).toHaveTextContent(enMessages['app.subtitle']);

    await user.click(screen.getByRole('button', { name: /switch/i }));

    expect(screen.getByTestId('current-locale')).toHaveTextContent('es');
    expect(screen.getByTestId('label')).toHaveTextContent(esMessages['app.subtitle']);
  });

  it('switches to every supported locale', async () => {
    const user = userEvent.setup();

    function MultiSwitcher() {
      const { setLocale, locale } = useI18n();
      return (
        <>
          <span data-testid="loc">{locale}</span>
          <button onClick={() => setLocale('ca')}>ca</button>
          <button onClick={() => setLocale('fr')}>fr</button>
        </>
      );
    }

    render(
      <I18nProvider>
        <MultiSwitcher />
        <TranslatedLabel />
      </I18nProvider>
    );

    await user.click(screen.getByRole('button', { name: 'ca' }));
    expect(screen.getByTestId('loc')).toHaveTextContent('ca');
    expect(screen.getByTestId('label')).toHaveTextContent(caMessages['app.subtitle']);

    await user.click(screen.getByRole('button', { name: 'fr' }));
    expect(screen.getByTestId('loc')).toHaveTextContent('fr');
    expect(screen.getByTestId('label')).toHaveTextContent(frMessages['app.subtitle']);
  });
});

// ---------------------------------------------------------------------------
// 4. LanguageSwitcher component
// ---------------------------------------------------------------------------

describe('LanguageSwitcher', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a select with all 4 language options', () => {
    render(
      <I18nProvider>
        <LanguageSwitcher />
      </I18nProvider>
    );

    const select = screen.getByRole('combobox', { name: /language/i });
    expect(select).toBeInTheDocument();

    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(4);

    const optionValues = options.map((o) => (o as HTMLOptionElement).value);
    expect(optionValues).toEqual(['en', 'es', 'ca', 'fr']);
  });

  it('updates the locale when a different language is selected', async () => {
    const user = userEvent.setup();

    render(
      <I18nProvider>
        <LanguageSwitcher />
        <LocaleDisplay />
      </I18nProvider>
    );

    expect(screen.getByTestId('current-locale')).toHaveTextContent('en');

    await user.selectOptions(screen.getByRole('combobox', { name: /language/i }), 'fr');

    expect(screen.getByTestId('current-locale')).toHaveTextContent('fr');
  });

  it('displays the label text from the current locale', async () => {
    const user = userEvent.setup();

    render(
      <I18nProvider>
        <LanguageSwitcher />
      </I18nProvider>
    );

    // Initially English
    expect(screen.getByText(/Language:/i)).toBeInTheDocument();

    // Switch to Spanish
    await user.selectOptions(screen.getByRole('combobox', { name: /language/i }), 'es');

    expect(screen.getByText(/Idioma:/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 5. localStorage persistence
// ---------------------------------------------------------------------------

describe('localStorage persistence', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('persists locale to localStorage when changed', async () => {
    const user = userEvent.setup();

    render(
      <I18nProvider>
        <LocaleSetter target="fr" />
      </I18nProvider>
    );

    await user.click(screen.getByRole('button', { name: /switch/i }));

    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('fr');
  });

  it('restores locale from localStorage on mount', () => {
    localStorage.setItem(LOCALE_STORAGE_KEY, 'ca');

    render(
      <I18nProvider>
        <LocaleDisplay />
      </I18nProvider>
    );

    expect(screen.getByTestId('current-locale')).toHaveTextContent('ca');
  });

  it('ignores invalid values in localStorage and falls back to default', () => {
    localStorage.setItem(LOCALE_STORAGE_KEY, 'xx');

    render(
      <I18nProvider>
        <LocaleDisplay />
      </I18nProvider>
    );

    expect(screen.getByTestId('current-locale')).toHaveTextContent('en');
  });
});

// ---------------------------------------------------------------------------
// 6. Browser locale detection
// ---------------------------------------------------------------------------

describe('Browser locale detection', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('detects exact browser locale match (e.g. "fr")', () => {
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('fr');

    render(
      <I18nProvider>
        <LocaleDisplay />
      </I18nProvider>
    );

    expect(screen.getByTestId('current-locale')).toHaveTextContent('fr');
  });

  it('detects browser locale by prefix (e.g. "es-MX" → "es")', () => {
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('es-MX');

    render(
      <I18nProvider>
        <LocaleDisplay />
      </I18nProvider>
    );

    expect(screen.getByTestId('current-locale')).toHaveTextContent('es');
  });

  it('falls back to English for unsupported browser locale', () => {
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('ja');

    render(
      <I18nProvider>
        <LocaleDisplay />
      </I18nProvider>
    );

    expect(screen.getByTestId('current-locale')).toHaveTextContent('en');
  });

  it('localStorage preference takes priority over browser locale', () => {
    localStorage.setItem(LOCALE_STORAGE_KEY, 'ca');
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('fr');

    render(
      <I18nProvider>
        <LocaleDisplay />
      </I18nProvider>
    );

    expect(screen.getByTestId('current-locale')).toHaveTextContent('ca');
  });
});
