import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import AdminPage from '../pages/AdminPage';

describe('AdminPage', () => {
  it('renders an iframe with the correct sandbox attribute', () => {
    const { container } = render(<AdminPage />);
    const iframe = container.querySelector('iframe');
    expect(iframe).not.toBeNull();
    expect(iframe?.getAttribute('sandbox')).toBe('allow-same-origin allow-scripts allow-forms');
  });

  it('does not include allow-popups in the sandbox attribute', () => {
    const { container } = render(<AdminPage />);
    const iframe = container.querySelector('iframe');
    expect(iframe?.getAttribute('sandbox')).not.toContain('allow-popups');
  });
});
