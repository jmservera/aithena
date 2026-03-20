"""Pydantic models for the Collections CRUD API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateCollectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class UpdateCollectionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class AddItemsRequest(BaseModel):
    document_ids: list[str] = Field(..., min_length=1, max_length=50)


class UpdateItemRequest(BaseModel):
    note: str | None = Field(default=None, max_length=5000)
    position: int | None = Field(default=None, ge=0)


class ReorderItemsRequest(BaseModel):
    item_ids: list[str] = Field(..., min_length=1, max_length=50)


class CollectionItemResponse(BaseModel):
    id: str
    collection_id: str
    document_id: str
    position: int | None
    note: str | None
    added_at: str
    updated_at: str


class CollectionResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None
    item_count: int
    created_at: str
    updated_at: str


class CollectionDetailResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None
    created_at: str
    updated_at: str
    items: list[CollectionItemResponse]
