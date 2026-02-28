from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from hf_backend.hf_auth import get_api


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


def list_my_collections(owner: str) -> List[CollectionInfo]:
    """List collections owned by the given user/org."""
    api = get_api()
    try:
        collections = api.list_collections(owner=owner)
        results = []
        for c in collections:
            items = []
            for it in (c.items or []):
                items.append(CollectionItemInfo(
                    item_id=getattr(it, "item_id", ""),
                    item_type=getattr(it, "item_type", ""),
                    note=getattr(it, "note", "") or "",
                    position=getattr(it, "position", 0),
                ))
            results.append(CollectionInfo(
                slug=c.slug,
                title=c.title or "",
                description=getattr(c, "description", "") or "",
                owner=getattr(c, "owner", owner),
                is_private=getattr(c, "is_private", False),
                items=items,
                url=f"https://huggingface.co/collections/{c.slug}",
            ))
        return results
    except Exception as e:
        raise HFCollectionError(f"Failed to list collections: {e}") from e


def get_collection(slug: str) -> CollectionInfo:
    """Get detailed info about a collection."""
    api = get_api()
    try:
        c = api.get_collection(slug)
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
    except Exception as e:
        raise HFCollectionError(f"Failed to get collection: {e}") from e


def create_collection(
    title: str,
    namespace: str | None = None,
    description: str = "",
    private: bool = False,
) -> CollectionInfo:
    """Create a new collection."""
    api = get_api()
    try:
        kwargs = {"title": title, "description": description, "private": private}
        if namespace:
            kwargs["namespace"] = namespace
        c = api.create_collection(**kwargs)
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
        raise HFCollectionError(f"Failed to create collection: {e}") from e


def delete_collection(slug: str) -> None:
    """Delete a collection."""
    api = get_api()
    try:
        api.delete_collection(slug)
    except Exception as e:
        raise HFCollectionError(f"Failed to delete collection: {e}") from e


def add_collection_item(
    slug: str,
    item_id: str,
    item_type: str,
    note: str = "",
) -> CollectionInfo:
    """Add an item to a collection."""
    api = get_api()
    try:
        kwargs = {
            "collection_slug": slug,
            "item_id": item_id,
            "item_type": item_type,
        }
        if note:
            kwargs["note"] = note
        c = api.add_collection_item(**kwargs)
        return get_collection(c.slug)
    except Exception as e:
        raise HFCollectionError(f"Failed to add item: {e}") from e


def remove_collection_item(slug: str, item_id: str) -> CollectionInfo:
    """Remove an item from a collection."""
    api = get_api()
    try:
        c = api.delete_collection_item(collection_slug=slug, item_id=item_id)
        return get_collection(c.slug)
    except Exception as e:
        raise HFCollectionError(f"Failed to remove item: {e}") from e


def update_collection_metadata(
    slug: str,
    title: str | None = None,
    description: str | None = None,
    private: bool | None = None,
) -> None:
    """Update collection title/description/visibility."""
    api = get_api()
    try:
        kwargs: dict = {"collection_slug": slug}
        if title is not None:
            kwargs["title"] = title
        if description is not None:
            kwargs["description"] = description
        if private is not None:
            kwargs["private"] = private
        api.update_collection_metadata(**kwargs)
    except Exception as e:
        raise HFCollectionError(f"Failed to update collection: {e}") from e
