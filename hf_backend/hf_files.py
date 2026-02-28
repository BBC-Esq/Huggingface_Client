from __future__ import annotations
from pathlib import Path
from typing import Optional

from huggingface_hub import HfApi

from hf_backend.hf_auth import get_api
from hf_backend.retry import with_retry


class HFFileError(RuntimeError):
    pass


def upload_file(
    repo_id: str,
    local_path: str,
    path_in_repo: str,
    repo_type: str = "model",
    commit_message: str = "Upload file",
    revision: str = "main",
) -> str:
    """Upload a single file. Returns the commit URL."""
    api = get_api()
    try:
        result = with_retry(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=path_in_repo,
            repo_id=repo_id,
            repo_type=repo_type,
            commit_message=commit_message,
            revision=revision,
        )
        return str(result)
    except Exception as e:
        raise HFFileError(f"Failed to upload file: {e}") from e


def upload_folder(
    repo_id: str,
    folder_path: str,
    path_in_repo: str = ".",
    repo_type: str = "model",
    commit_message: str = "Upload folder",
    revision: str = "main",
    ignore_patterns: list[str] | None = None,
) -> str:
    """Upload an entire folder. Returns the commit URL."""
    api = get_api()
    if ignore_patterns is None:
        ignore_patterns = [
            "__pycache__/**",
            "*.pyc",
            ".git/**",
            ".DS_Store",
            "Thumbs.db",
        ]
    try:
        result = with_retry(
            api.upload_folder,
            folder_path=folder_path,
            path_in_repo=path_in_repo if path_in_repo != "." else "",
            repo_id=repo_id,
            repo_type=repo_type,
            commit_message=commit_message,
            revision=revision,
            ignore_patterns=ignore_patterns,
        )
        return str(result)
    except Exception as e:
        raise HFFileError(f"Failed to upload folder: {e}") from e


def download_file(
    repo_id: str,
    filename: str,
    local_dir: str,
    repo_type: str = "model",
    revision: str = "main",
) -> str:
    """Download a single file. Returns the local path."""
    api = get_api()
    try:
        path = with_retry(
            api.hf_hub_download,
            repo_id=repo_id,
            filename=filename,
            local_dir=local_dir,
            repo_type=repo_type,
            revision=revision,
        )
        return str(path)
    except Exception as e:
        raise HFFileError(f"Failed to download file: {e}") from e


def delete_file(
    repo_id: str,
    path_in_repo: str,
    repo_type: str = "model",
    commit_message: str = "Delete file",
    revision: str = "main",
) -> None:
    """Delete a single file from the repo."""
    api = get_api()
    try:
        with_retry(
            api.delete_file,
            path_in_repo=path_in_repo,
            repo_id=repo_id,
            repo_type=repo_type,
            commit_message=commit_message,
            revision=revision,
        )
    except Exception as e:
        raise HFFileError(f"Failed to delete file: {e}") from e


def delete_files(
    repo_id: str,
    paths_in_repo: list[str],
    repo_type: str = "model",
    commit_message: str = "Delete files",
    revision: str = "main",
) -> None:
    """Delete multiple files from the repo in a single commit."""
    api = get_api()
    try:
        from huggingface_hub import CommitOperationDelete
        operations = [CommitOperationDelete(path_in_repo=p) for p in paths_in_repo]
        with_retry(
            api.create_commit,
            repo_id=repo_id,
            repo_type=repo_type,
            operations=operations,
            commit_message=commit_message,
            revision=revision,
        )
    except Exception as e:
        raise HFFileError(f"Failed to delete files: {e}") from e


def get_file_content(
    repo_id: str,
    path_in_repo: str,
    repo_type: str = "model",
    revision: str = "main",
) -> str:
    """Download and read a text file from the repo. Returns file contents."""
    api = get_api()
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            path = with_retry(
                api.hf_hub_download,
                repo_id=repo_id,
                filename=path_in_repo,
                local_dir=tmpdir,
                repo_type=repo_type,
                revision=revision,
            )
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
    except Exception as e:
        raise HFFileError(f"Failed to get file content: {e}") from e


def upload_file_content(
    repo_id: str,
    content: str | bytes,
    path_in_repo: str,
    repo_type: str = "model",
    commit_message: str = "Update file",
    revision: str = "main",
) -> str:
    """Upload content directly as a file (e.g. for README edits). Returns commit URL."""
    api = get_api()
    try:
        if isinstance(content, str):
            content = content.encode("utf-8")
        result = with_retry(
            api.upload_file,
            path_or_fileobj=content,
            path_in_repo=path_in_repo,
            repo_id=repo_id,
            repo_type=repo_type,
            commit_message=commit_message,
            revision=revision,
        )
        return str(result)
    except Exception as e:
        raise HFFileError(f"Failed to upload content: {e}") from e
