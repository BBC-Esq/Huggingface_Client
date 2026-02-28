from __future__ import annotations
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
    QComboBox,
    QLineEdit,
    QGroupBox,
    QTabWidget,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QFileDialog,
    QDialog,
    QStatusBar,
    QProgressBar,
    QCheckBox,
    QMenu,
)

from settings import AppSettings
from ui.repo_browser import RepoBrowser
from ui.collection_manager import CollectionManager
from ui.workers import ApiWorker
from ui.dialogs import (
    LoginDialog,
    CreateRepoDialog,
    UploadDialog,
    ModelCardDialog,
    CreateCollectionDialog,
    AddToCollectionDialog,
    TextEditorDialog,
)

from hf_backend.hf_auth import login, get_cached_token, UserInfo
from hf_backend.hf_repos import (
    list_my_repos,
    create_repo,
    delete_repo,
    update_repo_visibility,
    list_repo_files,
    list_repo_refs,
    HFRepoError,
    RepoInfo,
)
from hf_backend.hf_files import (
    upload_file,
    upload_folder,
    download_file,
    delete_files,
    get_file_content,
    upload_file_content,
)
from hf_backend.hf_collections import (
    list_my_collections,
    create_collection as hf_create_collection,
    delete_collection as hf_delete_collection,
    add_collection_item,
    remove_collection_item,
)
from hf_backend.hf_model_card import get_readme, push_readme


def _human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 ** 3:
        return f"{size / (1024 ** 2):.1f} MB"
    else:
        return f"{size / (1024 ** 3):.2f} GB"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HF Hub Manager")
        self._settings = AppSettings()
        self._user: UserInfo | None = None
        self._current_repo_id: str = ""
        self._current_repo_type: str = "model"
        self._workers: set = set()
        self._readme_cache: dict[tuple, str] = {}
        self._busy: bool = False
        self._all_repos: list[RepoInfo] = []
        self._favorites: set[str] = set()

        self._build_ui()
        self._connect_signals()
        self._restore_window()
        self._try_auto_login()

    # ── worker helper ──────────────────────────────────────────────

    def _run_api(
        self,
        fn,
        args: tuple = (),
        kwargs: dict | None = None,
        on_success=None,
        on_error=None,
        status_msg: str | None = None,
        busy: bool = True,
    ):
        """Run *fn* in a background thread, delivering results on the main thread."""
        worker = ApiWorker(fn, *args, **(kwargs or {}))

        def _on_finished(result):
            self._workers.discard(worker)
            if busy:
                self._set_busy(False)
            if on_success:
                on_success(result)

        def _on_error(msg):
            self._workers.discard(worker)
            if busy:
                self._set_busy(False)
            self._status.clearMessage()
            self._progress.hide()
            if on_error:
                on_error(msg)
            else:
                QMessageBox.critical(self, "Error", msg)

        worker.finished.connect(_on_finished, Qt.QueuedConnection)
        worker.error.connect(_on_error, Qt.QueuedConnection)
        self._workers.add(worker)

        if busy:
            self._set_busy(True)

        if status_msg:
            self._status.showMessage(status_msg)

        worker.start()
        return worker

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        enabled = not busy
        self._btn_login.setEnabled(enabled and self._user is None)
        self._btn_logout.setEnabled(enabled and self._user is not None)
        self._btn_refresh_repos.setEnabled(enabled)
        self._btn_create_repo.setEnabled(enabled)
        self._btn_delete_repo.setEnabled(enabled)
        self._btn_toggle_vis.setEnabled(enabled)
        self._repo_type_combo.setEnabled(enabled)
        self._search_input.setEnabled(enabled)
        self._chk_favorites.setEnabled(enabled)
        self._btn_load_readme.setEnabled(enabled)
        self._btn_edit_readme.setEnabled(enabled)
        self._btn_new_model_card.setEnabled(enabled)
        self._browser.set_actions_enabled(enabled)
        self._collections.set_actions_enabled(enabled)

    # ── UI construction ────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._root = QWidget()
        self.setCentralWidget(self._root)
        root_layout = QVBoxLayout()
        self._root.setLayout(root_layout)

        auth_group = QGroupBox("Account")
        auth_layout = QHBoxLayout()
        auth_group.setLayout(auth_layout)

        self._user_label = QLabel("Not logged in")
        self._btn_login = QPushButton("Login")
        self._btn_logout = QPushButton("Logout")
        self._btn_logout.setEnabled(False)
        auth_layout.addWidget(self._user_label, 1)
        auth_layout.addWidget(self._btn_login)
        auth_layout.addWidget(self._btn_logout)
        root_layout.addWidget(auth_group)

        self._splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(self._splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left.setLayout(left_layout)

        repo_toolbar = QHBoxLayout()

        self._repo_type_combo = QComboBox()
        self._repo_type_combo.addItem("Models", "model")
        self._repo_type_combo.addItem("Datasets", "dataset")
        self._repo_type_combo.addItem("Spaces", "space")
        repo_toolbar.addWidget(self._repo_type_combo)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search my repos…")
        self._search_input.setClearButtonEnabled(True)
        repo_toolbar.addWidget(self._search_input, 1)

        self._btn_refresh_repos = QPushButton("⟳")
        self._btn_refresh_repos.setToolTip("Refresh repo list")
        self._btn_refresh_repos.setMaximumWidth(36)
        repo_toolbar.addWidget(self._btn_refresh_repos)

        self._btn_create_repo = QPushButton("+")
        self._btn_create_repo.setToolTip("Create new repo")
        self._btn_create_repo.setMaximumWidth(36)
        repo_toolbar.addWidget(self._btn_create_repo)

        self._chk_favorites = QCheckBox("\u2605 Favorites only")
        repo_toolbar.addWidget(self._chk_favorites)

        left_layout.addLayout(repo_toolbar)

        self._repo_tree = QTreeWidget()
        self._repo_tree.setHeaderLabels(["\u2605", "Repository", "Visibility", "Downloads", "Likes", "Modified"])
        self._repo_tree.setRootIsDecorated(False)
        self._repo_tree.setSortingEnabled(True)
        self._repo_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self._repo_tree.setContextMenuPolicy(Qt.CustomContextMenu)

        header = self._repo_tree.header()
        header.setStretchLastSection(False)
        for i in range(6):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
        header.resizeSection(0, 30)
        header.resizeSection(1, 300)
        header.resizeSection(2, 80)
        header.resizeSection(3, 90)
        header.resizeSection(4, 70)
        header.resizeSection(5, 150)

        left_layout.addWidget(self._repo_tree, 1)

        repo_actions = QHBoxLayout()
        self._btn_delete_repo = QPushButton("Delete Repo")
        self._btn_toggle_vis = QPushButton("Toggle Visibility")
        self._btn_open_hub = QPushButton("Open on Hub")
        repo_actions.addWidget(self._btn_delete_repo)
        repo_actions.addWidget(self._btn_toggle_vis)
        repo_actions.addWidget(self._btn_open_hub)
        left_layout.addLayout(repo_actions)

        self._splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right.setLayout(right_layout)

        self._repo_info_label = QLabel("Select a repository from the list")
        self._repo_info_label.setStyleSheet("font-weight: bold; padding: 4px;")
        right_layout.addWidget(self._repo_info_label)

        self._tabs = QTabWidget()
        right_layout.addWidget(self._tabs, 1)

        self._browser = RepoBrowser()
        self._tabs.addTab(self._browser, "Files")

        readme_widget = QWidget()
        readme_layout = QVBoxLayout()
        readme_widget.setLayout(readme_layout)

        readme_btns = QHBoxLayout()
        self._btn_load_readme = QPushButton("Load README")
        self._btn_edit_readme = QPushButton("Edit README…")
        self._btn_new_model_card = QPushButton("New Model Card…")
        readme_btns.addWidget(self._btn_load_readme)
        readme_btns.addWidget(self._btn_edit_readme)
        readme_btns.addWidget(self._btn_new_model_card)
        readme_btns.addStretch()
        readme_layout.addLayout(readme_btns)

        from PySide6.QtWidgets import QPlainTextEdit
        self._readme_view = QPlainTextEdit()
        self._readme_view.setReadOnly(True)
        font = self._readme_view.font()
        font.setFamily("monospace")
        font.setPointSize(10)
        self._readme_view.setFont(font)
        readme_layout.addWidget(self._readme_view, 1)

        self._tabs.addTab(readme_widget, "README")

        self._collections = CollectionManager()
        self._tabs.addTab(self._collections, "Collections")

        self._splitter.addWidget(right)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 1)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(200)
        self._progress.hide()
        self._status.addPermanentWidget(self._progress)

    def _connect_signals(self) -> None:
        self._btn_login.clicked.connect(self._on_login)
        self._btn_logout.clicked.connect(self._on_logout)

        self._btn_refresh_repos.clicked.connect(self._refresh_repos)
        self._btn_create_repo.clicked.connect(self._on_create_repo)
        self._chk_favorites.toggled.connect(self._on_favorites_toggled)
        self._repo_type_combo.currentIndexChanged.connect(self._refresh_repos)
        self._search_input.returnPressed.connect(self._refresh_repos)
        self._repo_tree.currentItemChanged.connect(self._on_repo_selected)
        self._repo_tree.customContextMenuRequested.connect(self._on_repo_context_menu)
        self._btn_delete_repo.clicked.connect(self._on_delete_repo)
        self._btn_toggle_vis.clicked.connect(self._on_toggle_visibility)
        self._btn_open_hub.clicked.connect(self._on_open_hub)

        self._browser.request_refresh.connect(self._refresh_files)
        self._browser.request_upload.connect(self._on_upload)
        self._browser.request_edit_file.connect(self._on_edit_file)
        self._browser.request_delete_files.connect(self._on_delete_files)
        self._browser.request_download_file.connect(self._on_download_file)
        self._browser.branch_changed.connect(self._on_branch_changed)

        self._btn_load_readme.clicked.connect(lambda: self._load_readme(force_refresh=True))
        self._btn_edit_readme.clicked.connect(self._on_edit_readme)
        self._btn_new_model_card.clicked.connect(self._on_new_model_card)

        self._collections.request_refresh.connect(self._refresh_collections)
        self._collections.request_create.connect(self._on_create_collection)
        self._collections.request_add_item.connect(self._on_add_to_collection)
        self._collections.request_remove_item.connect(self._on_remove_from_collection)
        self._collections.request_delete.connect(self._on_delete_collection)
        self._collections.request_open_url.connect(lambda url: webbrowser.open(url))

    def _restore_window(self) -> None:
        geometry = self._settings.get_window_geometry()
        state = self._settings.get_window_state()
        splitter_state = self._settings.get_splitter_state()

        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(1300, 850)

        if state is not None:
            self.restoreState(state)

        if splitter_state is not None:
            self._splitter.restoreState(splitter_state)
        else:
            self._splitter.setSizes([650, 650])

        saved_type = self._settings.get_last_repo_type()
        if saved_type:
            idx = self._repo_type_combo.findData(saved_type)
            if idx >= 0:
                self._repo_type_combo.setCurrentIndex(idx)

        self._favorites = self._settings.get_favorite_repos()
        self._chk_favorites.setChecked(self._settings.get_favorites_only())

    def closeEvent(self, event) -> None:
        for worker in list(self._workers):
            worker.blockSignals(True)
            worker.cancel()
        self._settings.set_window_geometry(self.saveGeometry())
        self._settings.set_window_state(self.saveState())
        self._settings.set_splitter_state(self._splitter.saveState())
        super().closeEvent(event)

    # ── authentication ─────────────────────────────────────────────

    def _try_auto_login(self) -> None:
        token = self._settings.get_hf_token()
        if not token:
            token = get_cached_token()
        if token:
            def _on_auto_login_fail(_msg):
                self._settings.set_hf_token("")
                self._status.showMessage(
                    "Saved token is no longer valid \u2013 please log in again.", 8000
                )

            self._run_api(
                login, args=(token,),
                on_success=lambda user: self._on_login_success(user, token),
                on_error=_on_auto_login_fail,
                busy=False,
            )

    def _on_login(self) -> None:
        token = self._settings.get_hf_token() or get_cached_token()
        dlg = LoginDialog(initial_token=token, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        token = dlg.get_token()
        self._run_api(
            login, args=(token,),
            on_success=lambda user: self._on_login_success(user, token),
            on_error=lambda msg: QMessageBox.critical(self, "Login failed", msg),
            status_msg="Logging in...",
        )

    def _on_login_success(self, user: UserInfo, token: str) -> None:
        self._user = user
        self._settings.set_hf_token(token)
        self._user_label.setText(
            f"Logged in as: {user.username}"
            + (f" ({user.fullname})" if user.fullname else "")
            + (f"  |  Orgs: {', '.join(user.orgs)}" if user.orgs else "")
        )
        self._btn_login.setEnabled(False)
        self._btn_logout.setEnabled(True)
        self._status.showMessage("Logged in successfully.", 3000)
        self._refresh_repos()
        self._refresh_collections()

    def _on_logout(self) -> None:
        self._user = None
        self._settings.set_hf_token("")
        self._readme_cache.clear()
        self._all_repos.clear()
        self._user_label.setText("Not logged in")
        self._btn_login.setEnabled(True)
        self._btn_logout.setEnabled(False)
        self._repo_tree.clear()
        self._browser.clear()
        self._collections.clear()
        self._readme_view.clear()
        self._current_repo_id = ""
        self._repo_info_label.setText("Select a repository from the list")
        self._status.showMessage("Logged out.", 3000)

    # ── repository list ────────────────────────────────────────────

    def _refresh_repos(self) -> None:
        if not self._user:
            return

        repo_type = self._repo_type_combo.currentData() or "model"
        self._settings.set_last_repo_type(repo_type)
        search = self._search_input.text().strip() or None

        def on_success(repos):
            self._all_repos = list(repos)
            self._populate_repo_tree()

        self._run_api(
            list_my_repos,
            kwargs={"repo_type": repo_type, "author": self._user.username, "search": search},
            on_success=on_success,
            status_msg=f"Loading {self._repo_type_combo.currentText().lower()}...",
            busy=False,
        )

    def _populate_repo_tree(self) -> None:
        self._repo_tree.clear()
        favs_only = self._chk_favorites.isChecked()
        shown = 0
        for r in self._all_repos:
            is_fav = r.repo_id in self._favorites
            if favs_only and not is_fav:
                continue
            item = QTreeWidgetItem([
                "\u2605" if is_fav else "",
                r.repo_id,
                "Private" if r.private else "Public",
                str(r.downloads),
                str(r.likes),
                r.last_modified[:19] if r.last_modified else "",
            ])
            item.setData(0, Qt.UserRole, r)
            self._repo_tree.addTopLevelItem(item)
            shown += 1
        total = len(self._all_repos)
        if favs_only:
            self._status.showMessage(f"Showing {shown} favorite(s) of {total} repos.", 3000)
        else:
            self._status.showMessage(f"Found {total} repo(s).", 3000)

    def _on_favorites_toggled(self, checked: bool) -> None:
        self._settings.set_favorites_only(checked)
        self._populate_repo_tree()

    def _on_repo_context_menu(self, pos) -> None:
        item = self._repo_tree.itemAt(pos)
        if not item:
            return
        info: RepoInfo = item.data(0, Qt.UserRole)
        if not info:
            return

        menu = QMenu(self)
        is_fav = info.repo_id in self._favorites
        if is_fav:
            action = menu.addAction("Remove from Favorites")
        else:
            action = menu.addAction("Add to Favorites")

        chosen = menu.exec(self._repo_tree.viewport().mapToGlobal(pos))
        if chosen == action:
            self._toggle_favorite(info.repo_id)

    def _toggle_favorite(self, repo_id: str) -> None:
        if repo_id in self._favorites:
            self._favorites.discard(repo_id)
        else:
            self._favorites.add(repo_id)
        self._settings.set_favorite_repos(self._favorites)
        self._populate_repo_tree()

    def _on_repo_selected(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        if current is None or self._busy:
            return

        info: RepoInfo = current.data(0, Qt.UserRole)
        if not info:
            return

        self._current_repo_id = info.repo_id
        self._current_repo_type = info.repo_type
        self._settings.set_last_repo_id(info.repo_id)

        vis = "Private" if info.private else "Public"
        self._repo_info_label.setText(
            f"{info.repo_id}  ({info.repo_type}, {vis})"
            + (f"  ·  {info.downloads} downloads" if info.downloads else "")
            + (f"  ·  {info.likes} likes" if info.likes else "")
        )

        self._refresh_files()
        self._load_readme()

    def _on_create_repo(self) -> None:
        if not self._user:
            QMessageBox.warning(self, "Not logged in", "Please log in first.")
            return

        dlg = CreateRepoDialog(
            username=self._user.username,
            orgs=self._user.orgs,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        details = dlg.get_details()

        def on_success(url):
            self._status.showMessage(f"Created: {url}", 5000)
            QMessageBox.information(self, "Repository created", f"Created successfully:\n{url}")
            self._refresh_repos()

        self._run_api(
            create_repo,
            kwargs={"repo_id": details["repo_id"], "repo_type": details["repo_type"], "private": details["private"]},
            on_success=on_success,
            on_error=lambda msg: QMessageBox.critical(self, "Create failed", msg),
            status_msg="Creating repository...",
        )

    def _on_delete_repo(self) -> None:
        if not self._current_repo_id:
            return

        reply = QMessageBox.warning(
            self,
            "Delete Repository",
            f"PERMANENTLY delete '{self._current_repo_id}'?\n\n"
            "This cannot be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        reply2 = QMessageBox.warning(
            self,
            "Confirm Deletion",
            f"Are you absolutely sure you want to delete '{self._current_repo_id}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply2 != QMessageBox.Yes:
            return

        repo_id = self._current_repo_id
        repo_type = self._current_repo_type

        def on_success(_result):
            self._status.showMessage(f"Deleted: {repo_id}", 5000)
            self._current_repo_id = ""
            self._browser.clear()
            self._readme_view.clear()
            self._repo_info_label.setText("Select a repository from the list")
            self._refresh_repos()

        self._run_api(
            delete_repo, args=(repo_id, repo_type),
            on_success=on_success,
            on_error=lambda msg: QMessageBox.critical(self, "Delete failed", msg),
        )

    def _on_toggle_visibility(self) -> None:
        if not self._current_repo_id:
            return

        item = self._repo_tree.currentItem()
        if not item:
            return

        info: RepoInfo = item.data(0, Qt.UserRole)
        new_private = not info.private
        action = "private" if new_private else "public"

        reply = QMessageBox.question(
            self,
            "Toggle Visibility",
            f"Make '{self._current_repo_id}' {action}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        repo_id = self._current_repo_id
        repo_type = self._current_repo_type

        def on_success(_result):
            self._status.showMessage(f"Visibility updated to {action}.", 3000)
            self._refresh_repos()

        self._run_api(
            update_repo_visibility, args=(repo_id, repo_type, new_private),
            on_success=on_success,
        )

    def _on_open_hub(self) -> None:
        if not self._current_repo_id:
            return

        type_prefix = ""
        if self._current_repo_type == "dataset":
            type_prefix = "datasets/"
        elif self._current_repo_type == "space":
            type_prefix = "spaces/"

        url = f"https://huggingface.co/{type_prefix}{self._current_repo_id}"
        webbrowser.open(url)

    # ── file browser ───────────────────────────────────────────────

    def _refresh_files(self) -> None:
        if not self._current_repo_id:
            return

        branch = self._browser.get_current_branch() or "main"
        repo_id = self._current_repo_id
        repo_type = self._current_repo_type

        def fetch():
            try:
                refs = list_repo_refs(repo_id, repo_type)
                branches = refs.get("branches", ["main"])
            except HFRepoError:
                branches = ["main"]
            files = list_repo_files(repo_id, repo_type, revision=branch)
            return branches, files

        def on_success(result):
            if self._current_repo_id != repo_id:
                return
            branches, files = result
            self._browser.set_branches(branches, branch)
            self._browser.set_files(files)
            self._status.showMessage(f"Loaded {len(files)} files.", 3000)

        self._run_api(fetch, on_success=on_success, status_msg="Loading files...", busy=False)

    def _on_branch_changed(self, branch: str) -> None:
        self._refresh_files()

    def _on_upload(self) -> None:
        if not self._current_repo_id:
            return

        last_dir = self._settings.get_last_upload_dir()
        dlg = UploadDialog(
            repo_id=self._current_repo_id,
            last_dir=last_dir,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        details = dlg.get_details()
        repo_id = self._current_repo_id
        repo_type = self._current_repo_type

        if details["is_folder"]:
            self._settings.set_last_upload_dir(details["folder_path"])
        elif details["file_paths"]:
            self._settings.set_last_upload_dir(str(Path(details["file_paths"][0]).parent))

        def do_upload():
            if details["is_folder"]:
                upload_folder(
                    repo_id=repo_id,
                    folder_path=details["folder_path"],
                    path_in_repo=details["path_in_repo"],
                    repo_type=repo_type,
                    commit_message=details["commit_message"],
                    revision=details["revision"],
                )
            else:
                for fpath in details["file_paths"]:
                    fname = Path(fpath).name
                    path_in_repo = details["path_in_repo"]
                    if path_in_repo and path_in_repo != ".":
                        target = f"{path_in_repo.rstrip('/')}/{fname}"
                    else:
                        target = fname
                    upload_file(
                        repo_id=repo_id,
                        local_path=fpath,
                        path_in_repo=target,
                        repo_type=repo_type,
                        commit_message=details["commit_message"],
                        revision=details["revision"],
                    )

        self._progress.setRange(0, 0)
        self._progress.show()

        def on_success(_result):
            self._progress.hide()
            self._status.showMessage("Upload complete.", 5000)
            self._refresh_files()

        def on_error(msg):
            self._progress.hide()
            QMessageBox.critical(self, "Upload failed", msg)
            self._refresh_files()

        self._run_api(do_upload, on_success=on_success, on_error=on_error, status_msg="Uploading...")

    def _on_edit_file(self, rfilename: str) -> None:
        if not self._current_repo_id:
            return

        branch = self._browser.get_current_branch() or "main"
        repo_id = self._current_repo_id
        repo_type = self._current_repo_type

        def on_loaded(content):
            self._status.clearMessage()
            dlg = TextEditorDialog(
                title=f"{repo_id} - {rfilename}",
                content=content,
                parent=self,
            )
            if dlg.exec() != QDialog.Accepted:
                return

            new_content = dlg.get_content()
            commit_msg = dlg.get_commit_message()

            def on_saved(_result):
                self._status.showMessage(f"Saved {rfilename}.", 3000)
                self._refresh_files()

            self._run_api(
                upload_file_content,
                kwargs={
                    "repo_id": repo_id,
                    "content": new_content,
                    "path_in_repo": rfilename,
                    "repo_type": repo_type,
                    "commit_message": commit_msg,
                    "revision": branch,
                },
                on_success=on_saved,
                on_error=lambda msg: QMessageBox.critical(self, "Save failed", msg),
                status_msg=f"Saving {rfilename}...",
            )

        self._run_api(
            get_file_content,
            kwargs={
                "repo_id": repo_id,
                "path_in_repo": rfilename,
                "repo_type": repo_type,
                "revision": branch,
            },
            on_success=on_loaded,
            on_error=lambda msg: QMessageBox.critical(self, "Error", msg),
            status_msg=f"Loading {rfilename}...",
        )

    def _on_delete_files(self, filenames: list[str]) -> None:
        if not self._current_repo_id or not filenames:
            return

        reply = QMessageBox.question(
            self,
            "Delete Files",
            f"Delete {len(filenames)} file(s) from '{self._current_repo_id}'?\n\n"
            + "\n".join(filenames[:10])
            + ("\n..." if len(filenames) > 10 else ""),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        branch = self._browser.get_current_branch() or "main"
        repo_id = self._current_repo_id
        repo_type = self._current_repo_type
        count = len(filenames)

        def on_success(_result):
            self._status.showMessage(f"Deleted {count} file(s).", 3000)
            self._refresh_files()

        def on_error(msg):
            QMessageBox.critical(self, "Delete failed", msg)
            self._refresh_files()

        self._run_api(
            delete_files,
            kwargs={
                "repo_id": repo_id,
                "paths_in_repo": filenames,
                "repo_type": repo_type,
                "commit_message": f"Delete {count} file(s)",
                "revision": branch,
            },
            on_success=on_success,
            on_error=on_error,
            status_msg="Deleting files...",
        )

    def _on_download_file(self, rfilename: str) -> None:
        if not self._current_repo_id:
            return

        dest_dir = QFileDialog.getExistingDirectory(
            self, "Download to folder", self._settings.get_last_upload_dir()
        )
        if not dest_dir:
            return

        branch = self._browser.get_current_branch() or "main"
        repo_id = self._current_repo_id
        repo_type = self._current_repo_type

        self._progress.setRange(0, 0)
        self._progress.show()

        def on_success(local_path):
            self._progress.hide()
            self._status.showMessage(f"Downloaded to: {local_path}", 5000)

        def on_error(msg):
            self._progress.hide()
            QMessageBox.critical(self, "Download failed", msg)

        self._run_api(
            download_file,
            kwargs={
                "repo_id": repo_id,
                "filename": rfilename,
                "local_dir": dest_dir,
                "repo_type": repo_type,
                "revision": branch,
            },
            on_success=on_success,
            on_error=on_error,
            status_msg=f"Downloading {rfilename}...",
        )

    # ── README / model card ────────────────────────────────────────

    def _load_readme(self, *, force_refresh: bool = False) -> None:
        if not self._current_repo_id:
            self._readme_view.clear()
            return

        repo_id = self._current_repo_id
        repo_type = self._current_repo_type
        cache_key = (repo_id, repo_type)

        if not force_refresh and cache_key in self._readme_cache:
            content = self._readme_cache[cache_key]
            self._readme_view.setPlainText(content if content else "(No README.md found)")
            return

        def on_success(content):
            if self._current_repo_id != repo_id:
                return
            self._readme_cache[cache_key] = content
            self._readme_view.setPlainText(content if content else "(No README.md found)")
            self._status.clearMessage()

        def on_error(_msg):
            self._readme_view.setPlainText("(No README.md found)")

        self._run_api(
            get_readme, args=(repo_id,),
            kwargs={"repo_type": repo_type},
            on_success=on_success,
            on_error=on_error,
            status_msg="Loading README...",
            busy=False,
        )

    def _on_edit_readme(self) -> None:
        if not self._current_repo_id:
            return

        content = self._readme_view.toPlainText()
        if content == "(No README.md found)":
            content = ""

        dlg = TextEditorDialog(
            title=f"{self._current_repo_id} - README.md",
            content=content,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        new_content = dlg.get_content()
        commit_msg = dlg.get_commit_message()
        repo_id = self._current_repo_id
        repo_type = self._current_repo_type

        def on_success(_result):
            self._readme_cache[(repo_id, repo_type)] = new_content
            self._readme_view.setPlainText(new_content if new_content else "(No README.md found)")
            self._status.showMessage("README saved.", 3000)
            self._refresh_files()

        self._run_api(
            push_readme, args=(repo_id, new_content),
            kwargs={"repo_type": repo_type, "commit_message": commit_msg},
            on_success=on_success,
            on_error=lambda msg: QMessageBox.critical(self, "Save failed", msg),
            status_msg="Saving README...",
        )

    def _on_new_model_card(self) -> None:
        if not self._current_repo_id:
            return

        existing = self._readme_view.toPlainText()
        if existing == "(No README.md found)":
            existing = ""

        dlg = ModelCardDialog(existing_content=existing, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        content = dlg.get_content()
        if not content.strip():
            return

        repo_id = self._current_repo_id
        repo_type = self._current_repo_type

        def on_success(_result):
            self._readme_cache[(repo_id, repo_type)] = content
            self._readme_view.setPlainText(content)
            self._status.showMessage("Model card pushed.", 3000)
            self._refresh_files()

        self._run_api(
            push_readme, args=(repo_id, content),
            kwargs={"repo_type": repo_type, "commit_message": "Add/update model card"},
            on_success=on_success,
            on_error=lambda msg: QMessageBox.critical(self, "Push failed", msg),
            status_msg="Pushing model card...",
        )

    # ── collections ────────────────────────────────────────────────

    def _refresh_collections(self) -> None:
        if not self._user:
            return

        username = self._user.username

        def on_success(colls):
            self._collections.set_collections(colls)
            self._status.showMessage(f"Loaded {len(colls)} collections.", 3000)

        self._run_api(
            list_my_collections, args=(username,),
            on_success=on_success,
            status_msg="Loading collections...",
            busy=False,
        )

    def _on_create_collection(self) -> None:
        if not self._user:
            return

        dlg = CreateCollectionDialog(
            username=self._user.username,
            orgs=self._user.orgs,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        details = dlg.get_details()

        def on_success(coll):
            self._status.showMessage(f"Collection created: {coll.slug}", 5000)
            self._refresh_collections()

        self._run_api(
            hf_create_collection,
            kwargs={
                "title": details["title"],
                "namespace": details["namespace"],
                "description": details["description"],
                "private": details["private"],
            },
            on_success=on_success,
        )

    def _on_add_to_collection(self, slug: str) -> None:
        dlg = AddToCollectionDialog(parent=self)

        if self._current_repo_id:
            dlg._item_id.setText(self._current_repo_id)
            idx = dlg._item_type.findData(self._current_repo_type)
            if idx >= 0:
                dlg._item_type.setCurrentIndex(idx)

        if dlg.exec() != QDialog.Accepted:
            return

        details = dlg.get_details()

        def on_success(_result):
            self._status.showMessage("Item added to collection.", 3000)
            self._refresh_collections()

        self._run_api(
            add_collection_item,
            kwargs={
                "slug": slug,
                "item_id": details["item_id"],
                "item_type": details["item_type"],
                "note": details["note"],
            },
            on_success=on_success,
        )

    def _on_remove_from_collection(self, slug: str, item_id: str) -> None:
        reply = QMessageBox.question(
            self,
            "Remove Item",
            f"Remove '{item_id}' from collection?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        def on_success(_result):
            self._status.showMessage("Item removed from collection.", 3000)
            self._refresh_collections()

        self._run_api(
            remove_collection_item, args=(slug, item_id),
            on_success=on_success,
        )

    def _on_delete_collection(self, slug: str) -> None:
        reply = QMessageBox.warning(
            self,
            "Delete Collection",
            f"Permanently delete collection '{slug}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        def on_success(_result):
            self._status.showMessage("Collection deleted.", 3000)
            self._refresh_collections()

        self._run_api(
            hf_delete_collection, args=(slug,),
            on_success=on_success,
        )
