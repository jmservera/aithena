/**
 * Collections API service layer.
 *
 * Placeholder endpoints backed by mock data — swap the implementations for
 * real `apiFetch` calls once the backend is available.
 */

import { apiFetch } from '../api';

// ── Domain types ──────────────────────────────────────────────────

export interface Collection {
  id: string;
  name: string;
  description: string;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionItem {
  id: string;
  document_id: string;
  title: string;
  author?: string;
  year?: number;
  cover_url?: string | null;
  note: string;
  added_at: string;
}

export interface CollectionDetail extends Collection {
  items: CollectionItem[];
}

export interface CollectionCreateRequest {
  name: string;
  description?: string;
}

export interface CollectionUpdateRequest {
  name?: string;
  description?: string;
}

// ── Mock data ─────────────────────────────────────────────────────

const MOCK_COLLECTIONS: Collection[] = [
  {
    id: 'col-1',
    name: 'Machine Learning Essentials',
    description: 'Core texts on ML algorithms and theory',
    item_count: 5,
    created_at: '2024-11-10T08:00:00Z',
    updated_at: '2025-01-15T14:30:00Z',
  },
  {
    id: 'col-2',
    name: 'Philosophy Reads',
    description: 'A curated set of philosophy classics',
    item_count: 3,
    created_at: '2024-12-01T10:00:00Z',
    updated_at: '2025-01-20T09:15:00Z',
  },
  {
    id: 'col-3',
    name: 'Science Fiction Favourites',
    description: '',
    item_count: 8,
    created_at: '2025-01-05T12:00:00Z',
    updated_at: '2025-01-22T18:45:00Z',
  },
];

const MOCK_ITEMS: CollectionItem[] = [
  {
    id: 'item-1',
    document_id: 'doc-101',
    title: 'Deep Learning',
    author: 'Ian Goodfellow',
    year: 2016,
    cover_url: null,
    note: 'Great introduction to neural networks.',
    added_at: '2025-01-10T10:00:00Z',
  },
  {
    id: 'item-2',
    document_id: 'doc-102',
    title: 'Pattern Recognition and Machine Learning',
    author: 'Christopher Bishop',
    year: 2006,
    cover_url: null,
    note: '',
    added_at: '2025-01-12T11:30:00Z',
  },
  {
    id: 'item-3',
    document_id: 'doc-103',
    title: 'Hands-On Machine Learning',
    author: 'Aurélien Géron',
    year: 2019,
    cover_url: null,
    note: 'Practical exercises with scikit-learn and TensorFlow.',
    added_at: '2025-01-14T09:00:00Z',
  },
];

let nextCollectionId = 4;
let nextItemId = 4;

// Mutable copies for create/update/delete during the session
const collections = [...MOCK_COLLECTIONS];
const itemsByCollection: Record<string, CollectionItem[]> = {
  'col-1': [...MOCK_ITEMS],
  'col-2': [],
  'col-3': [],
};

// ── Helpers ───────────────────────────────────────────────────────

function delay(ms = 120): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Normalize raw API item to match the CollectionItem interface. */
function normalizeItem(raw: Record<string, unknown>): CollectionItem {
  return {
    id: String(raw.id ?? ''),
    document_id: String(raw.document_id ?? ''),
    title: String(raw.title ?? 'Untitled'),
    author: raw.author != null ? String(raw.author) : undefined,
    year: typeof raw.year === 'number' ? raw.year : undefined,
    cover_url: raw.cover_url != null ? String(raw.cover_url) : null,
    note: raw.note != null ? String(raw.note) : '',
    added_at: String(raw.added_at ?? ''),
  };
}

/** Normalize raw API detail to match the CollectionDetail interface. */
function normalizeDetail(raw: Record<string, unknown>): CollectionDetail {
  const items = Array.isArray(raw.items) ? raw.items.map(normalizeItem) : [];
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? ''),
    description: String(raw.description ?? ''),
    item_count: typeof raw.item_count === 'number' ? raw.item_count : items.length,
    created_at: String(raw.created_at ?? ''),
    updated_at: String(raw.updated_at ?? ''),
    items,
  };
}

// ── API functions ─────────────────────────────────────────────────
// Each function contains the real `apiFetch` call (commented out) and a
// mock fallback.  Uncomment the real call and remove the mock block when
// the backend endpoints are ready.

export async function fetchCollections(): Promise<Collection[]> {
  /* istanbul ignore next -- real endpoint */
  if (import.meta.env.VITE_COLLECTIONS_API === 'real') {
    const res = await apiFetch('/v1/collections');
    if (!res.ok) throw new Error('Failed to fetch collections');
    return (await res.json()) as Collection[];
  }
  await delay();
  return [...collections];
}

export async function fetchCollectionDetail(id: string): Promise<CollectionDetail> {
  /* istanbul ignore next -- real endpoint */
  if (import.meta.env.VITE_COLLECTIONS_API === 'real') {
    const res = await apiFetch(`/v1/collections/${id}`);
    if (!res.ok) throw new Error('Collection not found');
    return normalizeDetail(await res.json());
  }
  await delay();
  const col = collections.find((c) => c.id === id);
  if (!col) throw new Error('Collection not found');
  return { ...col, items: itemsByCollection[id] ?? [] };
}

export async function createCollection(data: CollectionCreateRequest): Promise<Collection> {
  /* istanbul ignore next -- real endpoint */
  if (import.meta.env.VITE_COLLECTIONS_API === 'real') {
    const res = await apiFetch('/v1/collections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create collection');
    return (await res.json()) as Collection;
  }
  await delay();
  const now = new Date().toISOString();
  const newCol: Collection = {
    id: `col-${nextCollectionId++}`,
    name: data.name,
    description: data.description ?? '',
    item_count: 0,
    created_at: now,
    updated_at: now,
  };
  collections.push(newCol);
  itemsByCollection[newCol.id] = [];
  return newCol;
}

export async function updateCollection(
  id: string,
  data: CollectionUpdateRequest
): Promise<Collection> {
  /* istanbul ignore next -- real endpoint */
  if (import.meta.env.VITE_COLLECTIONS_API === 'real') {
    const res = await apiFetch(`/v1/collections/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to update collection');
    return (await res.json()) as Collection;
  }
  await delay();
  const col = collections.find((c) => c.id === id);
  if (!col) throw new Error('Collection not found');
  if (data.name !== undefined) col.name = data.name;
  if (data.description !== undefined) col.description = data.description;
  col.updated_at = new Date().toISOString();
  return { ...col };
}

export async function deleteCollection(id: string): Promise<void> {
  /* istanbul ignore next -- real endpoint */
  if (import.meta.env.VITE_COLLECTIONS_API === 'real') {
    const res = await apiFetch(`/v1/collections/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete collection');
    return;
  }
  await delay();
  const idx = collections.findIndex((c) => c.id === id);
  if (idx === -1) throw new Error('Collection not found');
  collections.splice(idx, 1);
  delete itemsByCollection[id];
}

export async function removeCollectionItem(collectionId: string, itemId: string): Promise<void> {
  /* istanbul ignore next -- real endpoint */
  if (import.meta.env.VITE_COLLECTIONS_API === 'real') {
    const res = await apiFetch(`/v1/collections/${collectionId}/items/${itemId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to remove item');
    return;
  }
  await delay();
  const items = itemsByCollection[collectionId];
  if (!items) throw new Error('Collection not found');
  const idx = items.findIndex((i) => i.id === itemId);
  if (idx === -1) throw new Error('Item not found');
  items.splice(idx, 1);
  const col = collections.find((c) => c.id === collectionId);
  if (col) col.item_count = items.length;
}

export async function updateItemNote(
  collectionId: string,
  itemId: string,
  note: string
): Promise<void> {
  /* istanbul ignore next -- real endpoint */
  if (import.meta.env.VITE_COLLECTIONS_API === 'real') {
    const res = await apiFetch(`/v1/collections/${collectionId}/items/${itemId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    });
    if (!res.ok) throw new Error('Failed to update note');
    return;
  }
  await delay();
  const items = itemsByCollection[collectionId];
  if (!items) throw new Error('Collection not found');
  const item = items.find((i) => i.id === itemId);
  if (!item) throw new Error('Item not found');
  item.note = note;
}

export async function addItemToCollection(
  collectionId: string,
  documentId: string
): Promise<CollectionItem> {
  /* istanbul ignore next -- real endpoint */
  if (import.meta.env.VITE_COLLECTIONS_API === 'real') {
    const res = await apiFetch(`/v1/collections/${collectionId}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_ids: [documentId] }),
    });
    if (!res.ok) throw new Error('Failed to add item');
    const body = (await res.json()) as { added: Record<string, unknown>[]; added_count: number };
    if (!body.added || body.added.length === 0) throw new Error('No item was added');
    return normalizeItem(body.added[0]);
  }
  await delay();
  const items = itemsByCollection[collectionId];
  if (!items) throw new Error('Collection not found');
  const newItem: CollectionItem = {
    id: `item-${nextItemId++}`,
    document_id: documentId,
    title: `Document ${documentId}`,
    author: 'Unknown',
    year: undefined,
    cover_url: null,
    note: '',
    added_at: new Date().toISOString(),
  };
  items.push(newItem);
  const col = collections.find((c) => c.id === collectionId);
  if (col) col.item_count = items.length;
  return newItem;
}

export async function addItemsToCollection(
  collectionId: string,
  documentIds: string[]
): Promise<CollectionItem[]> {
  /* istanbul ignore next -- real endpoint */
  if (import.meta.env.VITE_COLLECTIONS_API === 'real') {
    const res = await apiFetch(`/v1/collections/${collectionId}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_ids: documentIds }),
    });
    if (!res.ok) throw new Error('Failed to add items');
    const body = (await res.json()) as { added: Record<string, unknown>[]; added_count: number };
    return (body.added ?? []).map(normalizeItem);
  }
  await delay();
  const items = itemsByCollection[collectionId];
  if (!items) throw new Error('Collection not found');
  const newItems: CollectionItem[] = documentIds.map((documentId) => {
    const newItem: CollectionItem = {
      id: `item-${nextItemId++}`,
      document_id: documentId,
      title: `Document ${documentId}`,
      author: 'Unknown',
      year: undefined,
      cover_url: null,
      note: '',
      added_at: new Date().toISOString(),
    };
    items.push(newItem);
    return newItem;
  });
  const col = collections.find((c) => c.id === collectionId);
  if (col) col.item_count = items.length;
  return newItems;
}
