import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Footer from '../Components/Footer';
import { IntlWrapper } from './test-intl-wrapper';

describe('Footer', () => {
  it('renders the application version text', () => {
    render(
      <IntlWrapper>
        <Footer />
      </IntlWrapper>
    );

    expect(screen.getByRole('contentinfo', { name: /application version/i })).toBeInTheDocument();
    expect(screen.getByText(`Aithena v${__APP_VERSION__}`)).toBeInTheDocument();
  });
});
