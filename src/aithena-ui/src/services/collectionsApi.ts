/**
 * Collections API service layer.
 *
 * All functions call the real backend via `apiFetch`.
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
  thumbnail_url?: string | null;
  document_url?: string | null;
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

// ── Helpers ───────────────────────────────────────────────────────

/** Normalize raw API item to match the CollectionItem interface. */
function normalizeItem(raw: Record<string, unknown>): CollectionItem {
  return {
    id: String(raw.id ?? ''),
    document_id: String(raw.document_id ?? ''),
    title: String(raw.title ?? 'Untitled'),
    author: raw.author != null ? String(raw.author) : undefined,
    year: typeof raw.year === 'number' ? raw.year : undefined,
    cover_url: raw.cover_url != null ? String(raw.cover_url) : null,
    thumbnail_url: raw.thumbnail_url != null ? String(raw.thumbnail_url) : null,
    document_url: raw.document_url != null ? String(raw.document_url) : null,
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

export async function fetchCollections(): Promise<Collection[]> {
  const res = await apiFetch('/v1/collections');
  if (!res.ok) throw new Error('Failed to fetch collections');
  return (await res.json()) as Collection[];
}

export async function fetchCollectionDetail(id: string): Promise<CollectionDetail> {
  const res = await apiFetch(`/v1/collections/${id}`);
  if (!res.ok) throw new Error('Collection not found');
  return normalizeDetail(await res.json());
}

export async function createCollection(data: CollectionCreateRequest): Promise<Collection> {
  const res = await apiFetch('/v1/collections', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create collection');
  return (await res.json()) as Collection;
}

export async function updateCollection(
  id: string,
  data: CollectionUpdateRequest
): Promise<Collection> {
  const res = await apiFetch(`/v1/collections/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update collection');
  return (await res.json()) as Collection;
}

export async function deleteCollection(id: string): Promise<void> {
  const res = await apiFetch(`/v1/collections/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete collection');
}

export async function removeCollectionItem(collectionId: string, itemId: string): Promise<void> {
  const res = await apiFetch(`/v1/collections/${collectionId}/items/${itemId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to remove item');
}

export async function updateItemNote(
  collectionId: string,
  itemId: string,
  note: string
): Promise<void> {
  const res = await apiFetch(`/v1/collections/${collectionId}/items/${itemId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error('Failed to update note');
}

export async function addItemToCollection(
  collectionId: string,
  documentId: string
): Promise<CollectionItem> {
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

export async function addItemsToCollection(
  collectionId: string,
  documentIds: string[]
): Promise<CollectionItem[]> {
  const res = await apiFetch(`/v1/collections/${collectionId}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_ids: documentIds }),
  });
  if (!res.ok) throw new Error('Failed to add items');
  const body = (await res.json()) as { added: Record<string, unknown>[]; added_count: number };
  return (body.added ?? []).map(normalizeItem);
}
