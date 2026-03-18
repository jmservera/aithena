import { type ReactNode } from 'react';
import { IntlProvider } from 'react-intl';
import enMessages from '../locales/en.json';

export function IntlWrapper({ children }: { children: ReactNode }) {
  return (
    <IntlProvider locale="en" messages={enMessages} defaultLocale="en">
      {children}
    </IntlProvider>
  );
}
