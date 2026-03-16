import './Footer.css';

function Footer() {
  return (
    <footer className="app-footer" role="contentinfo" aria-label="Application version">
      <span className="app-footer__text">Aithena v{__APP_VERSION__}</span>
    </footer>
  );
}

export default Footer;
