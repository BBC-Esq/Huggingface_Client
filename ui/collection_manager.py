# ui/collection_manager.py
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QMessageBox,
    QMenu,
)
from PySide6.QtGui import QAction

from hf_backend.hf_collections import CollectionInfo


class CollectionManager(QWidget):
    """Widget for browsing and managing HF collections."""

    request_refresh = Signal()
    request_create = Signal()
    request_add_item = Signal(str)    # emits collection slug
    request_remove_item = Signal(str, str)  # slug, item_id
    request_delete = Signal(str)      # emits collection slug
    request_open_url = Signal(str)    # emits url

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # Toolbar
        toolbar = QHBoxLayout()
        self._btn_refresh = QPushButton("⟳ Refresh")
        self._btn_create = QPushButton("+ New Collection")
        toolbar.addWidget(self._btn_refresh)
        toolbar.addWidget(self._btn_create)
        toolbar.addStretch()
        self._info_label = QLabel("")
        toolbar.addWidget(self._info_label)
        layout.addLayout(toolbar)

        # Tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name / Item", "Type", "Note / Description"])
        self._tree.setRootIsDecorated(True)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.setSelectionMode(QTreeWidget.SingleSelection)

        header = self._tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        layout.addWidget(self._tree, 1)

        self._btn_refresh.clicked.connect(self.request_refresh.emit)
        self._btn_create.clicked.connect(self.request_create.emit)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

    def set_collections(self, collections: list[CollectionInfo]) -> None:
        self._tree.clear()
        for coll in collections:
            coll_item = QTreeWidgetItem([
                coll.title,
                "Private" if coll.is_private else "Public",
                coll.description[:80] if coll.description else "",
            ])
            coll_item.setData(0, Qt.UserRole, {"type": "collection", "slug": coll.slug, "url": coll.url})
            font = coll_item.font(0)
            font.setBold(True)
            coll_item.setFont(0, font)

            for ci in coll.items:
                child = QTreeWidgetItem([
                    ci.item_id,
                    ci.item_type,
                    ci.note,
                ])
                child.setData(0, Qt.UserRole, {
                    "type": "item",
                    "slug": coll.slug,
                    "item_id": ci.item_id,
                    "item_type": ci.item_type,
                })
                coll_item.addChild(child)

            self._tree.addTopLevelItem(coll_item)

        self._info_label.setText(f"{len(collections)} collections")
        self._tree.expandAll()

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if not item:
            return

        data = item.data(0, Qt.UserRole)
        if not data:
            return

        menu = QMenu(self)

        if data["type"] == "collection":
            slug = data["slug"]

            act_add = QAction("Add item to collection...", self)
            act_add.triggered.connect(lambda: self.request_add_item.emit(slug))
            menu.addAction(act_add)

            if data.get("url"):
                act_open = QAction("Open in browser", self)
                act_open.triggered.connect(lambda: self.request_open_url.emit(data["url"]))
                menu.addAction(act_open)

            menu.addSeparator()

            act_del = QAction("Delete collection", self)
            act_del.triggered.connect(lambda: self.request_delete.emit(slug))
            menu.addAction(act_del)

        elif data["type"] == "item":
            slug = data["slug"]
            item_id = data["item_id"]

            act_remove = QAction(f"Remove '{item_id}' from collection", self)
            act_remove.triggered.connect(lambda: self.request_remove_item.emit(slug, item_id))
            menu.addAction(act_remove)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def clear(self) -> None:
        self._tree.clear()
        self._info_label.setText("")
