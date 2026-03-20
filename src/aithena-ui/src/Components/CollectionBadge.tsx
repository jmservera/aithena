import { useIntl } from 'react-intl';
import { FolderHeart } from 'lucide-react';

interface CollectionBadgeProps {
  count: number;
}

function CollectionBadge({ count }: CollectionBadgeProps) {
  const intl = useIntl();

  if (count <= 0) return null;

  return (
    <span
      className="collection-badge"
      title={intl.formatMessage({ id: 'collections.inCollections' }, { count })}
      aria-label={intl.formatMessage({ id: 'collections.inCollections' }, { count })}
    >
      <FolderHeart size={12} aria-hidden="true" />
      {intl.formatMessage({ id: 'collections.inCollectionsShort' }, { count })}
    </span>
  );
}

export default CollectionBadge;
