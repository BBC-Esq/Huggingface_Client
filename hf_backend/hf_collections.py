from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from hf_backend.hf_auth import get_api
from hf_backend.retry import with_retry

logger = logging.getLogger(__name__)


class HFCollectionError(RuntimeError):
    pass


@dataclass
class CollectionItemInfo:
    item_id: str
    item_type: str
    note: str = ""
    position: int = 0


@dataclass
class CollectionInfo:
    slug: str
    title: str
    description: str
    owner: str
    is_private: bool
    items: list[CollectionItemInfo] = field(default_factory=list)
    url: str = ""


def _to_collection_info(c) -> CollectionInfo:
    items = []
    for it in (c.items or []):
        items.append(CollectionItemInfo(
            item_id=getattr(it, "item_id", ""),
            item_type=getattr(it, "item_type", ""),
            note=getattr(it, "note", "") or "",
            position=getattr(it, "position", 0),
        ))
    return CollectionInfo(
        slug=c.slug,
        title=c.title or "",
        description=getattr(c, "description", "") or "",
        owner=getattr(c, "owner", ""),
        is_private=getattr(c, "is_private", False),
        items=items,
        url=f"https://huggingface.co/collections/{c.slug}",
    )


def list_my_collections(owner: str) -> List[CollectionInfo]:

    api = get_api()
    try:
        collections = with_retry(api.list_collections, owner=owner)
        results = []
        for c in collections:
            full = get_collection(c.slug)
            results.append(full)
        return results
    except Exception as e:
        logger.error("Failed to list collections for %s: %s", owner, e)
        raise HFCollectionError(f"Failed to list collections: {e}") from e


def get_collection(slug: str) -> CollectionInfo:

    api = get_api()
    try:
        c = with_retry(api.get_collection, slug)
        return _to_collection_info(c)
    except Exception as e:
        logger.error("Failed to get collection %s: %s", slug, e)
        raise HFCollectionError(f"Failed to get collection: {e}") from e


def create_collection(
    title: str,
    namespace: str | None = None,
    description: str = "",
    private: bool = False,
) -> CollectionInfo:

    api = get_api()
    try:
        kwargs = {"title": title, "description": description, "private": private}
        if namespace:
            kwargs["namespace"] = namespace
        c = with_retry(api.create_collection, **kwargs)
        return CollectionInfo(
            slug=c.slug,
            title=c.title or title,
            description=description,
            owner=getattr(c, "owner", ""),
            is_private=private,
            items=[],
            url=f"https://huggingface.co/collections/{c.slug}",
        )
    except Exception as e:
        logger.error("Failed to create collection '%s': %s", title, e)
        raise HFCollectionError(f"Failed to create collection: {e}") from e


def delete_collection(slug: str) -> None:

    api = get_api()
    try:
        with_retry(api.delete_collection, slug)
    except Exception as e:
        logger.error("Failed to delete collection %s: %s", slug, e)
        raise HFCollectionError(f"Failed to delete collection: {e}") from e


def add_collection_item(
    slug: str,
    item_id: str,
    item_type: str,
    note: str = "",
) -> CollectionInfo:

    api = get_api()
    try:
        kwargs = {
            "collection_slug": slug,
            "item_id": item_id,
            "item_type": item_type,
        }
        if note:
            kwargs["note"] = note
        c = with_retry(api.add_collection_item, **kwargs)
        return _to_collection_info(c)
    except Exception as e:
        logger.error("Failed to add item %s to collection %s: %s", item_id, slug, e)
        raise HFCollectionError(f"Failed to add item: {e}") from e


def remove_collection_item(slug: str, item_id: str) -> CollectionInfo:

    api = get_api()
    try:
        c = with_retry(api.delete_collection_item, collection_slug=slug, item_id=item_id)
        return _to_collection_info(c)
    except Exception as e:
        logger.error("Failed to remove item %s from collection %s: %s", item_id, slug, e)
        raise HFCollectionError(f"Failed to remove item: {e}") from e


def update_collection_metadata(
    slug: str,
    title: str | None = None,
    description: str | None = None,
    private: bool | None = None,
) -> None:

    api = get_api()
    try:
        kwargs: dict = {"collection_slug": slug}
        if title is not None:
            kwargs["title"] = title
        if description is not None:
            kwargs["description"] = description
        if private is not None:
            kwargs["private"] = private
        with_retry(api.update_collection_metadata, **kwargs)
    except Exception as e:
        logger.error("Failed to update collection %s: %s", slug, e)
        raise HFCollectionError(f"Failed to update collection: {e}") from e
