from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QMenu,
    QPushButton,
    QLabel,
    QMessageBox,
    QComboBox,
)

from hf_backend.hf_repos import RepoFileEntry

_SIZE_ROLE = Qt.UserRole + 1
_MAX_EDIT_BYTES = 10 * 1024 * 1024


def _human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 ** 3:
        return f"{size / (1024 ** 2):.1f} MB"
    else:
        return f"{size / (1024 ** 3):.2f} GB"


class RepoBrowser(QWidget):

    file_selected = Signal(str)
    request_edit_file = Signal(str)
    request_delete_files = Signal(list)
    request_download_file = Signal(str)
    request_upload = Signal()
    request_refresh = Signal()
    branch_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        toolbar = QHBoxLayout()

        self._branch_combo = QComboBox()
        self._branch_combo.setMinimumWidth(140)
        self._branch_combo.setEditable(False)
        toolbar.addWidget(QLabel("Branch:"))
        toolbar.addWidget(self._branch_combo)

        self._btn_refresh = QPushButton("⟳ Refresh")
        self._btn_upload = QPushButton("⬆ Upload")
        toolbar.addWidget(self._btn_refresh)
        toolbar.addWidget(self._btn_upload)
        toolbar.addStretch()

        self._info_label = QLabel("")
        toolbar.addWidget(self._info_label)

        layout.addLayout(toolbar)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Size", "LFS", "Blob ID"])
        self._tree.setRootIsDecorated(True)
        self._tree.setSortingEnabled(True)
        self._tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)

        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        layout.addWidget(self._tree, 1)

        self._btn_refresh.clicked.connect(self.request_refresh.emit)
        self._btn_upload.clicked.connect(self.request_upload.emit)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._branch_combo.currentTextChanged.connect(self._on_branch_changed)
        self._actions_enabled = True

    def set_actions_enabled(self, enabled: bool) -> None:
        self._actions_enabled = enabled
        self._btn_refresh.setEnabled(enabled)
        self._btn_upload.setEnabled(enabled)
        self._branch_combo.setEnabled(enabled)

    def _on_branch_changed(self, text: str) -> None:
        if text:
            self.branch_changed.emit(text)

    def set_branches(self, branches: list[str], current: str = "") -> None:
        self._branch_combo.blockSignals(True)
        self._branch_combo.clear()
        for b in branches:
            self._branch_combo.addItem(b)
        idx = self._branch_combo.findText(current)
        if idx >= 0:
            self._branch_combo.setCurrentIndex(idx)
        self._branch_combo.blockSignals(False)

    def get_current_branch(self) -> str:
        return self._branch_combo.currentText()

    def set_files(self, entries: list[RepoFileEntry]) -> None:
        self._tree.clear()

        folder_items: dict[str, QTreeWidgetItem] = {}
        total_size = 0

        for entry in entries:
            total_size += entry.size
            parts = entry.rfilename.split("/")

            if len(parts) == 1:
                item = QTreeWidgetItem([
                    entry.rfilename,
                    _human_size(entry.size),
                    "LFS" if entry.is_lfs else "",
                    entry.blob_id[:12] if entry.blob_id else "",
                ])
                item.setData(0, Qt.UserRole, entry.rfilename)
                item.setData(0, _SIZE_ROLE, entry.size)
                self._tree.addTopLevelItem(item)
            else:
                folder_path = "/".join(parts[:-1])
                parent = self._get_or_create_folder(folder_items, folder_path)
                item = QTreeWidgetItem([
                    parts[-1],
                    _human_size(entry.size),
                    "LFS" if entry.is_lfs else "",
                    entry.blob_id[:12] if entry.blob_id else "",
                ])
                item.setData(0, Qt.UserRole, entry.rfilename)
                item.setData(0, _SIZE_ROLE, entry.size)
                parent.addChild(item)

        self._info_label.setText(f"{len(entries)} files · {_human_size(total_size)} total")
        self._tree.expandAll()

    def _get_or_create_folder(
        self, cache: dict[str, QTreeWidgetItem], folder_path: str
    ) -> QTreeWidgetItem:
        if folder_path in cache:
            return cache[folder_path]

        parts = folder_path.split("/")
        if len(parts) == 1:
            item = QTreeWidgetItem([folder_path, "", "", ""])
            item.setData(0, Qt.UserRole, None)
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            self._tree.addTopLevelItem(item)
            cache[folder_path] = item
            return item

        parent_path = "/".join(parts[:-1])
        parent = self._get_or_create_folder(cache, parent_path)
        item = QTreeWidgetItem([parts[-1], "", "", ""])
        item.setData(0, Qt.UserRole, None)
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        parent.addChild(item)
        cache[folder_path] = item
        return item

    def _selected_file_names(self) -> list[str]:
        names = []
        for item in self._tree.selectedItems():
            rfilename = item.data(0, Qt.UserRole)
            if rfilename:
                names.append(rfilename)
        return names

    def _try_edit(self, item: QTreeWidgetItem) -> None:
        rfilename = item.data(0, Qt.UserRole)
        if not rfilename or not self._looks_like_text(rfilename):
            return
        size = item.data(0, _SIZE_ROLE) or 0
        if size > _MAX_EDIT_BYTES:
            QMessageBox.information(
                self,
                "File Too Large",
                f"{rfilename} is {_human_size(size)}, which exceeds the "
                f"10 MB limit for the built-in editor.\n\n"
                f"To edit this file you can:\n"
                f"  1. Download it (right-click \u2192 Download file)\n"
                f"  2. Edit it locally with your preferred text editor\n"
                f"  3. Upload the modified file using the Upload button",
            )
            return
        self.request_edit_file.emit(rfilename)

    def _on_context_menu(self, pos) -> None:
        if not self._actions_enabled:
            return
        selected = self._selected_file_names()
        if not selected:
            return

        menu = QMenu(self)

        if len(selected) == 1:
            item = self._tree.selectedItems()[0]
            name = selected[0]
            is_text = self._looks_like_text(name)
            size = item.data(0, _SIZE_ROLE) or 0

            if is_text and size <= _MAX_EDIT_BYTES:
                act_edit = QAction("Edit file...", self)
                act_edit.triggered.connect(lambda: self._try_edit(item))
                menu.addAction(act_edit)

            act_download = QAction("Download file...", self)
            act_download.triggered.connect(lambda: self.request_download_file.emit(name))
            menu.addAction(act_download)

        act_delete = QAction(f"Delete {len(selected)} file(s)...", self)
        act_delete.triggered.connect(lambda: self.request_delete_files.emit(selected))
        menu.addAction(act_delete)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        if not self._actions_enabled:
            return
        self._try_edit(item)

    @staticmethod
    def _looks_like_text(name: str) -> bool:
        text_exts = {
            ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg",
            ".ini", ".py", ".js", ".ts", ".html", ".css", ".xml",
            ".csv", ".tsv", ".sh", ".bash", ".dockerfile", ".gitignore",
            ".gitattributes", ".env", ".config", ".jsonl",
        }
        lower = name.lower()
        if lower in {"readme.md", ".gitattributes", ".gitignore", "license", "notice"}:
            return True
        return any(lower.endswith(ext) for ext in text_exts)

    def clear(self) -> None:
        self._tree.clear()
        self._info_label.setText("")
        self._branch_combo.clear()
