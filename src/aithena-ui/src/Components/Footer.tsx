import styles from './Footer.module.css';

function Footer() {
  return (
    <footer className={styles.appFooter} role="contentinfo" aria-label="Application version">
      <span className={styles.appFooterText}>Aithena v{__APP_VERSION__}</span>
    </footer>
  );
}

export default Footer;
