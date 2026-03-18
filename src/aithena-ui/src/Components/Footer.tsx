import { useIntl } from 'react-intl';

import styles from './Footer.module.css';

function Footer() {
  const intl = useIntl();

  return (
    <footer className={styles.appFooter} role="contentinfo" aria-label="Application version">
      <span className={styles.appFooterText}>
        {intl.formatMessage({ id: 'footer.version' }, { version: __APP_VERSION__ })}
      </span>
    </footer>
  );
}

export default Footer;
