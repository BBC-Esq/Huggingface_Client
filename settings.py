from __future__ import annotations
from PySide6.QtCore import QSettings, QByteArray


class AppSettings:
    def __init__(self) -> None:
        self._qs = QSettings("LocalTools", "HFHubManager")

    def get_window_geometry(self) -> QByteArray | None:
        value = self._qs.value("window_geometry")
        return value if isinstance(value, QByteArray) else None

    def set_window_geometry(self, geometry: QByteArray) -> None:
        self._qs.setValue("window_geometry", geometry)

    def get_window_state(self) -> QByteArray | None:
        value = self._qs.value("window_state")
        return value if isinstance(value, QByteArray) else None

    def set_window_state(self, state: QByteArray) -> None:
        self._qs.setValue("window_state", state)

    def get_hf_token(self) -> str:
        return self._qs.value("hf_token", "", str)

    def set_hf_token(self, token: str) -> None:
        self._qs.setValue("hf_token", token)

    def get_last_repo_id(self) -> str:
        return self._qs.value("last_repo_id", "", str)

    def set_last_repo_id(self, repo_id: str) -> None:
        self._qs.setValue("last_repo_id", repo_id)

    def get_last_repo_type(self) -> str:
        return self._qs.value("last_repo_type", "model", str)

    def set_last_repo_type(self, repo_type: str) -> None:
        self._qs.setValue("last_repo_type", repo_type)

    def get_last_upload_dir(self) -> str:
        return self._qs.value("last_upload_dir", "", str)

    def set_last_upload_dir(self, path: str) -> None:
        self._qs.setValue("last_upload_dir", path)

    def get_splitter_state(self) -> QByteArray | None:
        value = self._qs.value("splitter_state")
        return value if isinstance(value, QByteArray) else None

    def set_splitter_state(self, state: QByteArray) -> None:
        self._qs.setValue("splitter_state", state)

    def get_favorite_repos(self) -> set[str]:
        raw = self._qs.value("favorite_repos", [])
        if isinstance(raw, list):
            return set(raw)
        return set()

    def set_favorite_repos(self, repos: set[str]) -> None:
        self._qs.setValue("favorite_repos", sorted(repos))

    def get_favorites_only(self) -> bool:
        return self._qs.value("favorites_only", False, bool)

    def set_favorites_only(self, val: bool) -> None:
        self._qs.setValue("favorites_only", val)
