import { ReactNode } from 'react';
import { FormattedMessage } from 'react-intl';
import { LucideIcon } from 'lucide-react';
import './EmptyState.css';

export interface EmptyStateProps {
  icon: LucideIcon;
  titleId: string;
  descriptionId: string;
  action?: {
    labelId: string;
    onClick?: () => void;
    href?: string;
  };
  children?: ReactNode;
}

function EmptyState({ icon: Icon, titleId, descriptionId, action, children }: EmptyStateProps) {
  return (
    <div className="empty-state" role="status">
      <div className="empty-state__icon" aria-hidden="true">
        <Icon size={64} />
      </div>
      <h3 className="empty-state__title">
        <FormattedMessage id={titleId} />
      </h3>
      <p className="empty-state__description">
        <FormattedMessage id={descriptionId} />
      </p>
      {action && (
        <div className="empty-state__action">
          {action.href ? (
            <a href={action.href} className="empty-state__button">
              <FormattedMessage id={action.labelId} />
            </a>
          ) : (
            <button type="button" className="empty-state__button" onClick={action.onClick}>
              <FormattedMessage id={action.labelId} />
            </button>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

export default EmptyState;
