import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIntl } from 'react-intl';
import { Library, Plus } from 'lucide-react';
import { useCollections } from '../hooks/collections';
import CollectionsGrid from '../Components/CollectionsGrid';
import CollectionModal from '../Components/CollectionModal';
import LoadingSpinner from '../Components/LoadingSpinner';
import ErrorState from '../Components/ErrorState';

function CollectionsPage() {
  const intl = useIntl();
  const navigate = useNavigate();
  const { collections, loading, error, reload, create } = useCollections();
  const [showCreate, setShowCreate] = useState(false);

  const handleSelect = useCallback(
    (id: string) => {
      navigate(`/collections/${id}`);
    },
    [navigate]
  );

  const handleCreate = useCallback(
    async (name: string, description: string) => {
      const created = await create({ name, description });
      setShowCreate(false);
      navigate(`/collections/${created.id}`);
    },
    [create, navigate]
  );

  if (loading) {
    return (
      <LoadingSpinner
        title={intl.formatMessage({ id: 'collections.loading' })}
        message={intl.formatMessage({ id: 'collections.loadingMessage' })}
      />
    );
  }

  if (error) {
    return <ErrorState error={error} onRetry={reload} />;
  }

  return (
    <section className="collections-page" aria-labelledby="collections-heading">
      <header className="collections-page-header">
        <h2 id="collections-heading" className="collections-page-title">
          <Library size={22} aria-hidden="true" />
          {intl.formatMessage({ id: 'collections.title' })}
        </h2>
        <button type="button" className="collections-new-btn" onClick={() => setShowCreate(true)}>
          <Plus size={16} aria-hidden="true" />
          {intl.formatMessage({ id: 'collections.newCollection' })}
        </button>
      </header>

      <CollectionsGrid collections={collections} onSelect={handleSelect} />

      <CollectionModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
        titleId="collections.createTitle"
        submitLabelId="collections.create"
      />
    </section>
  );
}

export default CollectionsPage;
