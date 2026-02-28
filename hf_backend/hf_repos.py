from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError

from hf_backend.hf_auth import get_api
from hf_backend.retry import with_retry


class HFRepoError(RuntimeError):
    pass


@dataclass
class RepoInfo:
    repo_id: str
    repo_type: str
    private: bool
    sha: str
    last_modified: str
    tags: list[str] = field(default_factory=list)
    downloads: int = 0
    likes: int = 0


@dataclass
class RepoFileEntry:
    """One file (or LFS pointer) in a repo."""
    rfilename: str
    size: int
    blob_id: str
    is_lfs: bool


def list_my_repos(
    repo_type: str = "model",
    author: str | None = None,
    search: str | None = None,
    sort: str = "lastModified",
    limit: int = 100,
) -> List[RepoInfo]:
    """List repos owned by the current user (or a specified author)."""
    api = get_api()
    try:
        if repo_type == "model":
            items = with_retry(api.list_models, author=author, search=search, sort=sort, limit=limit)
        elif repo_type == "dataset":
            items = with_retry(api.list_datasets, author=author, search=search, sort=sort, limit=limit)
        elif repo_type == "space":
            items = with_retry(api.list_spaces, author=author, search=search, sort=sort, limit=limit)
        else:
            raise HFRepoError(f"Unknown repo type: {repo_type}")
    except HFRepoError:
        raise
    except Exception as e:
        raise HFRepoError(f"Failed to list repos: {e}") from e

    results = []
    for item in items:
        modified = ""
        if hasattr(item, "last_modified") and item.last_modified:
            modified = str(item.last_modified)
        elif hasattr(item, "lastModified") and item.lastModified:
            modified = str(item.lastModified)

        tags = list(getattr(item, "tags", []) or [])
        results.append(RepoInfo(
            repo_id=item.id,
            repo_type=repo_type,
            private=getattr(item, "private", False),
            sha=getattr(item, "sha", ""),
            last_modified=modified,
            tags=tags,
            downloads=getattr(item, "downloads", 0) or 0,
            likes=getattr(item, "likes", 0) or 0,
        ))
    return results


def create_repo(
    repo_id: str,
    repo_type: str = "model",
    private: bool = False,
    exist_ok: bool = False,
) -> str:
    """Create a new repo. Returns the URL of the created repo."""
    api = get_api()
    try:
        result = with_retry(
            api.create_repo,
            repo_id=repo_id,
            repo_type=repo_type,
            private=private,
            exist_ok=exist_ok,
        )
        return str(result)
    except Exception as e:
        raise HFRepoError(f"Failed to create repo: {e}") from e


def delete_repo(repo_id: str, repo_type: str = "model") -> None:
    """Delete a repository permanently."""
    api = get_api()
    try:
        with_retry(api.delete_repo, repo_id=repo_id, repo_type=repo_type)
    except Exception as e:
        raise HFRepoError(f"Failed to delete repo: {e}") from e


def update_repo_visibility(repo_id: str, repo_type: str, private: bool) -> None:
    """Change the visibility of a repo."""
    api = get_api()
    try:
        with_retry(api.update_repo_settings, repo_id=repo_id, repo_type=repo_type, private=private)
    except Exception as e:
        raise HFRepoError(f"Failed to update visibility: {e}") from e


def get_repo_info(repo_id: str, repo_type: str = "model") -> RepoInfo:
    """Get detailed info about a single repo."""
    api = get_api()
    try:
        if repo_type == "model":
            info = with_retry(api.model_info, repo_id)
        elif repo_type == "dataset":
            info = with_retry(api.dataset_info, repo_id)
        elif repo_type == "space":
            info = with_retry(api.space_info, repo_id)
        else:
            raise HFRepoError(f"Unknown repo type: {repo_type}")
    except HFRepoError:
        raise
    except RepositoryNotFoundError:
        raise HFRepoError(f"Repository not found: {repo_id}")
    except Exception as e:
        raise HFRepoError(f"Failed to get repo info: {e}") from e

    modified = ""
    if hasattr(info, "last_modified") and info.last_modified:
        modified = str(info.last_modified)

    tags = list(getattr(info, "tags", []) or [])
    return RepoInfo(
        repo_id=info.id,
        repo_type=repo_type,
        private=getattr(info, "private", False),
        sha=getattr(info, "sha", ""),
        last_modified=modified,
        tags=tags,
        downloads=getattr(info, "downloads", 0) or 0,
        likes=getattr(info, "likes", 0) or 0,
    )


def list_repo_files(repo_id: str, repo_type: str = "model", revision: str = "main") -> List[RepoFileEntry]:
    """List all files in a repo."""
    api = get_api()
    try:
        if repo_type == "model":
            info = with_retry(api.model_info, repo_id, revision=revision, files_metadata=True)
        elif repo_type == "dataset":
            info = with_retry(api.dataset_info, repo_id, revision=revision, files_metadata=True)
        elif repo_type == "space":
            info = with_retry(api.space_info, repo_id, revision=revision, files_metadata=True)
        else:
            raise HFRepoError(f"Unknown repo type: {repo_type}")
    except HFRepoError:
        raise
    except Exception as e:
        raise HFRepoError(f"Failed to list files: {e}") from e

    entries = []
    for sib in info.siblings or []:
        is_lfs = bool(getattr(sib, "lfs", None))
        entries.append(RepoFileEntry(
            rfilename=sib.rfilename,
            size=getattr(sib, "size", 0) or 0,
            blob_id=getattr(sib, "blob_id", "") or "",
            is_lfs=is_lfs,
        ))
    return sorted(entries, key=lambda e: e.rfilename.lower())


def list_repo_refs(repo_id: str, repo_type: str = "model") -> dict:
    """List branches and tags of a repo."""
    api = get_api()
    try:
        refs = with_retry(api.list_repo_refs, repo_id=repo_id, repo_type=repo_type)
        branches = [b.name for b in (refs.branches or [])]
        tags = [t.name for t in (refs.tags or [])]
        return {"branches": branches, "tags": tags}
    except Exception as e:
        raise HFRepoError(f"Failed to list refs: {e}") from e
