import { useIntl } from 'react-intl';
import { useI18n, type Locale } from '../contexts/I18nContext';

const LANGUAGES: Array<{ code: Locale; flag: string }> = [
  { code: 'en', flag: '🇬🇧' },
  { code: 'es', flag: '🇪🇸' },
  { code: 'ca', flag: '🇨🇦' },
  { code: 'fr', flag: '🇫🇷' },
];

function LanguageSwitcher() {
  const intl = useIntl();
  const { locale, setLocale } = useI18n();

  return (
    <div className="language-switcher">
      <label htmlFor="language-select" className="language-switcher-label">
        {intl.formatMessage({ id: 'language.select' })}:
      </label>
      <select
        id="language-select"
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
        className="language-switcher-select"
        aria-label={intl.formatMessage({ id: 'language.select' })}
      >
        {LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.flag} {intl.formatMessage({ id: `language.${lang.code}` })}
          </option>
        ))}
      </select>
    </div>
  );
}

export default LanguageSwitcher;
