import { useCallback, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useIntl } from 'react-intl';
import { ArrowLeft } from 'lucide-react';
import { useAutoSaveNote, useCollectionDetail } from '../hooks/collections';
import CollectionDetailView from '../Components/CollectionDetailView';
import CollectionModal from '../Components/CollectionModal';
import ConfirmDialog from '../Components/ConfirmDialog';
import LoadingSpinner from '../Components/LoadingSpinner';
import ErrorState from '../Components/ErrorState';

function CollectionDetailPage() {
  const intl = useIntl();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { detail, loading, error, reload, removeItem, saveNote, updateMeta, deleteCollection } =
    useCollectionDetail(id);

  const { debouncedSave, saving } = useAutoSaveNote(saveNote);

  const [showEdit, setShowEdit] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleRemoveItem = useCallback(
    async (itemId: string) => {
      await removeItem(itemId);
    },
    [removeItem]
  );

  const handleEditSubmit = useCallback(
    async (name: string, description: string) => {
      await updateMeta({ name, description });
      setShowEdit(false);
    },
    [updateMeta]
  );

  const handleDelete = useCallback(async () => {
    await deleteCollection();
    navigate('/collections');
  }, [deleteCollection, navigate]);

  if (loading) {
    return (
      <LoadingSpinner
        title={intl.formatMessage({ id: 'collections.loading' })}
        message={intl.formatMessage({ id: 'collections.loadingMessage' })}
      />
    );
  }

  if (error || !detail) {
    return <ErrorState error={error ?? 'Collection not found'} onRetry={reload} />;
  }

  return (
    <section className="collection-detail-page">
      <button
        type="button"
        className="collection-back-btn"
        onClick={() => navigate('/collections')}
      >
        <ArrowLeft size={16} aria-hidden="true" />
        {intl.formatMessage({ id: 'collections.backToCollections' })}
      </button>

      <CollectionDetailView
        detail={detail}
        onRemoveItem={handleRemoveItem}
        onSaveNote={debouncedSave}
        onEdit={() => setShowEdit(true)}
        onDelete={() => setShowDeleteConfirm(true)}
        saving={saving}
      />

      <CollectionModal
        open={showEdit}
        onClose={() => setShowEdit(false)}
        onSubmit={handleEditSubmit}
        initialName={detail.name}
        initialDescription={detail.description}
        titleId="collections.editTitle"
        submitLabelId="collections.save"
      />

      <ConfirmDialog
        open={showDeleteConfirm}
        titleId="collections.deleteTitle"
        messageId="collections.deleteConfirm"
        messageValues={{ name: detail.name }}
        confirmLabelId="collections.delete"
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </section>
  );
}

export default CollectionDetailPage;
