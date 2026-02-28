# hf_backend/hf_auth.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from huggingface_hub import HfApi
from huggingface_hub.utils import get_token as _hf_get_token


class HFAuthError(RuntimeError):
    pass


@dataclass
class UserInfo:
    username: str
    fullname: str
    email: str
    avatar_url: str
    orgs: list[str]


_api_instance: Optional[HfApi] = None


def get_api(token: str | None = None) -> HfApi:
    """Return a shared HfApi instance, optionally setting the token."""
    global _api_instance
    if _api_instance is None or token is not None:
        _api_instance = HfApi(token=token if token else None)
    return _api_instance


def login(token: str) -> UserInfo:
    """Validate a token and return user info. Raises HFAuthError on failure."""
    token = token.strip()
    if not token:
        raise HFAuthError("Token cannot be empty.")

    api = get_api(token)
    try:
        info = api.whoami()
    except Exception as e:
        _reset_api()
        raise HFAuthError(f"Login failed: {e}") from e

    orgs = [o.get("name", "") for o in info.get("orgs", [])]
    return UserInfo(
        username=info.get("name", ""),
        fullname=info.get("fullname", ""),
        email=info.get("email", ""),
        avatar_url=info.get("avatarUrl", ""),
        orgs=orgs,
    )


def get_cached_token() -> str:
    """Try to get a token from HF's default cache (~/.cache/huggingface/token)."""
    try:
        t = _hf_get_token()
        return t or ""
    except Exception:
        return ""


def whoami(token: str | None = None) -> UserInfo | None:
    """Return user info if logged in, else None."""
    try:
        api = get_api(token)
        info = api.whoami()
        orgs = [o.get("name", "") for o in info.get("orgs", [])]
        return UserInfo(
            username=info.get("name", ""),
            fullname=info.get("fullname", ""),
            email=info.get("email", ""),
            avatar_url=info.get("avatarUrl", ""),
            orgs=orgs,
        )
    except Exception:
        return None


def _reset_api() -> None:
    global _api_instance
    _api_instance = None
