import { useCallback, useEffect, useRef, useState } from 'react';
import {
  type Collection,
  type CollectionCreateRequest,
  type CollectionDetail,
  type CollectionUpdateRequest,
  createCollection as apiCreate,
  deleteCollection as apiDelete,
  fetchCollectionDetail as apiFetchDetail,
  fetchCollections as apiFetchList,
  removeCollectionItem as apiRemoveItem,
  updateCollection as apiUpdate,
  updateItemNote as apiUpdateNote,
} from '../services/collectionsApi';

// ── List hook ─────────────────────────────────────────────────────

export function useCollections() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetchList();
      setCollections(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load collections');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const create = useCallback(
    async (data: CollectionCreateRequest) => {
      const created = await apiCreate(data);
      await load();
      return created;
    },
    [load]
  );

  const update = useCallback(
    async (id: string, data: CollectionUpdateRequest) => {
      const updated = await apiUpdate(id, data);
      await load();
      return updated;
    },
    [load]
  );

  const remove = useCallback(
    async (id: string) => {
      await apiDelete(id);
      await load();
    },
    [load]
  );

  return { collections, loading, error, reload: load, create, update, remove };
}

// ── Detail hook ───────────────────────────────────────────────────

export function useCollectionDetail(id: string | undefined) {
  const [detail, setDetail] = useState<CollectionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetchDetail(id);
      setDetail(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load collection');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const removeItem = useCallback(
    async (itemId: string) => {
      if (!id) return;
      await apiRemoveItem(id, itemId);
      await load();
    },
    [id, load]
  );

  const saveNote = useCallback(
    async (itemId: string, note: string) => {
      if (!id) return;
      await apiUpdateNote(id, itemId, note);
      // Optimistic update — avoid full reload for note saves
      setDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          items: prev.items.map((item) => (item.id === itemId ? { ...item, note } : item)),
        };
      });
    },
    [id]
  );

  const updateMeta = useCallback(
    async (data: CollectionUpdateRequest) => {
      if (!id) return;
      await apiUpdate(id, data);
      await load();
    },
    [id, load]
  );

  const deleteCollection = useCallback(async () => {
    if (!id) return;
    await apiDelete(id);
  }, [id]);

  return {
    detail,
    loading,
    error,
    reload: load,
    removeItem,
    saveNote,
    updateMeta,
    deleteCollection,
  };
}

// ── Auto-save hook ────────────────────────────────────────────────

export function useAutoSaveNote(
  save: (itemId: string, note: string) => Promise<void>,
  debounceMs = 800
) {
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [saving, setSaving] = useState(false);

  const debouncedSave = useCallback(
    (itemId: string, note: string) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        setSaving(true);
        void save(itemId, note).finally(() => setSaving(false));
      }, debounceMs);
    },
    [save, debounceMs]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return { debouncedSave, saving };
}
