from __future__ import annotations
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
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
    QApplication,
    QFileDialog,
    QDialog,
    QStatusBar,
    QProgressBar,
)

from settings import AppSettings
from ui.repo_browser import RepoBrowser
from ui.collection_manager import CollectionManager
from ui.dialogs import (
    LoginDialog,
    CreateRepoDialog,
    UploadDialog,
    ModelCardDialog,
    CreateCollectionDialog,
    AddToCollectionDialog,
    TextEditorDialog,
)

from hf_backend.hf_auth import login, whoami, get_cached_token, HFAuthError, UserInfo
from hf_backend.hf_repos import (
    list_my_repos,
    create_repo,
    delete_repo,
    update_repo_visibility,
    list_repo_files,
    list_repo_refs,
    get_repo_info,
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
    HFFileError,
)
from hf_backend.hf_collections import (
    list_my_collections,
    create_collection as hf_create_collection,
    delete_collection as hf_delete_collection,
    add_collection_item,
    remove_collection_item,
    HFCollectionError,
)
from hf_backend.hf_model_card import get_readme, push_readme, HFModelCardError


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

        self._build_ui()
        self._connect_signals()
        self._restore_window()
        self._try_auto_login()

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

        left_layout.addLayout(repo_toolbar)

        self._repo_tree = QTreeWidget()
        self._repo_tree.setHeaderLabels(["Repository", "Visibility", "Downloads", "Likes", "Modified"])
        self._repo_tree.setRootIsDecorated(False)
        self._repo_tree.setSortingEnabled(True)
        self._repo_tree.setSelectionMode(QTreeWidget.SingleSelection)

        header = self._repo_tree.header()
        header.setStretchLastSection(False)
        for i in range(5):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
        header.resizeSection(0, 300)
        header.resizeSection(1, 80)
        header.resizeSection(2, 90)
        header.resizeSection(3, 70)
        header.resizeSection(4, 150)

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
        self._repo_type_combo.currentIndexChanged.connect(self._refresh_repos)
        self._search_input.returnPressed.connect(self._refresh_repos)
        self._repo_tree.currentItemChanged.connect(self._on_repo_selected)
        self._btn_delete_repo.clicked.connect(self._on_delete_repo)
        self._btn_toggle_vis.clicked.connect(self._on_toggle_visibility)
        self._btn_open_hub.clicked.connect(self._on_open_hub)

        self._browser.request_refresh.connect(self._refresh_files)
        self._browser.request_upload.connect(self._on_upload)
        self._browser.request_edit_file.connect(self._on_edit_file)
        self._browser.request_delete_files.connect(self._on_delete_files)
        self._browser.request_download_file.connect(self._on_download_file)
        self._browser.branch_changed.connect(self._on_branch_changed)

        self._btn_load_readme.clicked.connect(self._load_readme)
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

    def closeEvent(self, event) -> None:
        self._settings.set_window_geometry(self.saveGeometry())
        self._settings.set_window_state(self.saveState())
        self._settings.set_splitter_state(self._splitter.saveState())
        super().closeEvent(event)

    def _try_auto_login(self) -> None:
        token = self._settings.get_hf_token()
        if not token:
            token = get_cached_token()
        if token:
            try:
                user = login(token)
                self._on_login_success(user, token)
            except HFAuthError:
                pass

    def _on_login(self) -> None:
        token = self._settings.get_hf_token() or get_cached_token()
        dlg = LoginDialog(initial_token=token, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        token = dlg.get_token()
        self._status.showMessage("Logging in...")
        QApplication.processEvents()

        try:
            user = login(token)
        except HFAuthError as e:
            self._status.clearMessage()
            QMessageBox.critical(self, "Login failed", str(e))
            return

        self._on_login_success(user, token)

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

    def _refresh_repos(self) -> None:
        if not self._user:
            return

        repo_type = self._repo_type_combo.currentData() or "model"
        self._settings.set_last_repo_type(repo_type)
        search = self._search_input.text().strip() or None

        self._status.showMessage(f"Loading {repo_type}s...")
        QApplication.processEvents()

        try:
            repos = list_my_repos(
                repo_type=repo_type,
                author=self._user.username,
                search=search,
            )
        except HFRepoError as e:
            self._status.clearMessage()
            QMessageBox.critical(self, "Error", str(e))
            return

        self._repo_tree.clear()
        for r in repos:
            item = QTreeWidgetItem([
                r.repo_id,
                "Private" if r.private else "Public",
                str(r.downloads),
                str(r.likes),
                r.last_modified[:19] if r.last_modified else "",
            ])
            item.setData(0, Qt.UserRole, r)
            self._repo_tree.addTopLevelItem(item)

        self._status.showMessage(f"Found {len(repos)} {repo_type}(s).", 3000)

    def _on_repo_selected(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        if current is None:
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
        self._status.showMessage("Creating repository...")
        QApplication.processEvents()

        try:
            url = create_repo(
                repo_id=details["repo_id"],
                repo_type=details["repo_type"],
                private=details["private"],
            )
        except HFRepoError as e:
            self._status.clearMessage()
            QMessageBox.critical(self, "Create failed", str(e))
            return

        self._status.showMessage(f"Created: {url}", 5000)
        QMessageBox.information(self, "Repository created", f"Created successfully:\n{url}")
        self._refresh_repos()

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

        try:
            delete_repo(self._current_repo_id, self._current_repo_type)
        except HFRepoError as e:
            QMessageBox.critical(self, "Delete failed", str(e))
            return

        self._status.showMessage(f"Deleted: {self._current_repo_id}", 5000)
        self._current_repo_id = ""
        self._browser.clear()
        self._readme_view.clear()
        self._repo_info_label.setText("Select a repository from the list")
        self._refresh_repos()

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

        try:
            update_repo_visibility(self._current_repo_id, self._current_repo_type, new_private)
        except HFRepoError as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self._status.showMessage(f"Visibility updated to {action}.", 3000)
        self._refresh_repos()

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

    def _refresh_files(self) -> None:
        if not self._current_repo_id:
            return

        branch = self._browser.get_current_branch() or "main"
        self._status.showMessage("Loading files...")
        QApplication.processEvents()

        try:
            refs = list_repo_refs(self._current_repo_id, self._current_repo_type)
            branches = refs.get("branches", ["main"])
            self._browser.set_branches(branches, branch)
        except HFRepoError:
            self._browser.set_branches(["main"], "main")

        try:
            files = list_repo_files(self._current_repo_id, self._current_repo_type, revision=branch)
            self._browser.set_files(files)
        except HFRepoError as e:
            self._status.clearMessage()
            QMessageBox.critical(self, "Error", str(e))
            return

        self._status.showMessage(f"Loaded {len(files)} files.", 3000)

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
        self._status.showMessage("Uploading...")
        self._progress.setRange(0, 0)
        self._progress.show()
        QApplication.processEvents()

        try:
            if details["is_folder"]:
                folder = details["folder_path"]
                self._settings.set_last_upload_dir(folder)
                upload_folder(
                    repo_id=self._current_repo_id,
                    folder_path=folder,
                    path_in_repo=details["path_in_repo"],
                    repo_type=self._current_repo_type,
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

                    self._settings.set_last_upload_dir(str(Path(fpath).parent))
                    upload_file(
                        repo_id=self._current_repo_id,
                        local_path=fpath,
                        path_in_repo=target,
                        repo_type=self._current_repo_type,
                        commit_message=details["commit_message"],
                        revision=details["revision"],
                    )
        except HFFileError as e:
            self._progress.hide()
            self._status.clearMessage()
            QMessageBox.critical(self, "Upload failed", str(e))
            self._refresh_files()
            return

        self._progress.hide()
        self._status.showMessage("Upload complete.", 5000)
        self._refresh_files()

    def _on_edit_file(self, rfilename: str) -> None:
        if not self._current_repo_id:
            return

        branch = self._browser.get_current_branch() or "main"
        self._status.showMessage(f"Loading {rfilename}...")
        QApplication.processEvents()

        try:
            content = get_file_content(
                self._current_repo_id, rfilename,
                repo_type=self._current_repo_type,
                revision=branch,
            )
        except HFFileError as e:
            self._status.clearMessage()
            QMessageBox.critical(self, "Error", str(e))
            return

        self._status.clearMessage()
        dlg = TextEditorDialog(
            title=f"{self._current_repo_id} - {rfilename}",
            content=content,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        new_content = dlg.get_content()
        commit_msg = dlg.get_commit_message()

        self._status.showMessage(f"Saving {rfilename}...")
        QApplication.processEvents()

        try:
            upload_file_content(
                repo_id=self._current_repo_id,
                content=new_content,
                path_in_repo=rfilename,
                repo_type=self._current_repo_type,
                commit_message=commit_msg,
                revision=branch,
            )
        except HFFileError as e:
            self._status.clearMessage()
            QMessageBox.critical(self, "Save failed", str(e))
            return

        self._status.showMessage(f"Saved {rfilename}.", 3000)
        self._refresh_files()

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
        self._status.showMessage("Deleting files...")
        QApplication.processEvents()

        try:
            delete_files(
                repo_id=self._current_repo_id,
                paths_in_repo=filenames,
                repo_type=self._current_repo_type,
                commit_message=f"Delete {len(filenames)} file(s)",
                revision=branch,
            )
        except HFFileError as e:
            self._status.clearMessage()
            QMessageBox.critical(self, "Delete failed", str(e))
            self._refresh_files()
            return

        self._status.showMessage(f"Deleted {len(filenames)} file(s).", 3000)
        self._refresh_files()

    def _on_download_file(self, rfilename: str) -> None:
        if not self._current_repo_id:
            return

        dest_dir = QFileDialog.getExistingDirectory(
            self, "Download to folder", self._settings.get_last_upload_dir()
        )
        if not dest_dir:
            return

        branch = self._browser.get_current_branch() or "main"
        self._status.showMessage(f"Downloading {rfilename}...")
        self._progress.setRange(0, 0)
        self._progress.show()
        QApplication.processEvents()

        try:
            local_path = download_file(
                repo_id=self._current_repo_id,
                filename=rfilename,
                local_dir=dest_dir,
                repo_type=self._current_repo_type,
                revision=branch,
            )
        except HFFileError as e:
            self._progress.hide()
            self._status.clearMessage()
            QMessageBox.critical(self, "Download failed", str(e))
            return

        self._progress.hide()
        self._status.showMessage(f"Downloaded to: {local_path}", 5000)

    def _load_readme(self) -> None:
        if not self._current_repo_id:
            self._readme_view.clear()
            return

        self._status.showMessage("Loading README...")
        QApplication.processEvents()

        try:
            content = get_readme(self._current_repo_id, self._current_repo_type)
        except Exception:
            content = ""

        self._readme_view.setPlainText(content if content else "(No README.md found)")
        self._status.clearMessage()

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

        self._status.showMessage("Saving README...")
        QApplication.processEvents()

        try:
            push_readme(
                self._current_repo_id,
                new_content,
                repo_type=self._current_repo_type,
                commit_message=commit_msg,
            )
        except HFModelCardError as e:
            self._status.clearMessage()
            QMessageBox.critical(self, "Save failed", str(e))
            return

        self._status.showMessage("README saved.", 3000)
        self._load_readme()
        self._refresh_files()

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

        self._status.showMessage("Pushing model card...")
        QApplication.processEvents()

        try:
            push_readme(
                self._current_repo_id,
                content,
                repo_type=self._current_repo_type,
                commit_message="Add/update model card",
            )
        except HFModelCardError as e:
            self._status.clearMessage()
            QMessageBox.critical(self, "Push failed", str(e))
            return

        self._status.showMessage("Model card pushed.", 3000)
        self._load_readme()
        self._refresh_files()

    def _refresh_collections(self) -> None:
        if not self._user:
            return

        self._status.showMessage("Loading collections...")
        QApplication.processEvents()

        try:
            colls = list_my_collections(self._user.username)
        except HFCollectionError as e:
            self._status.clearMessage()
            QMessageBox.critical(self, "Error", str(e))
            return

        self._collections.set_collections(colls)
        self._status.showMessage(f"Loaded {len(colls)} collections.", 3000)

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

        try:
            coll = hf_create_collection(
                title=details["title"],
                namespace=details["namespace"],
                description=details["description"],
                private=details["private"],
            )
        except HFCollectionError as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self._status.showMessage(f"Collection created: {coll.slug}", 5000)
        self._refresh_collections()

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

        try:
            add_collection_item(
                slug=slug,
                item_id=details["item_id"],
                item_type=details["item_type"],
                note=details["note"],
            )
        except HFCollectionError as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self._status.showMessage("Item added to collection.", 3000)
        self._refresh_collections()

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

        try:
            remove_collection_item(slug, item_id)
        except HFCollectionError as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self._status.showMessage("Item removed from collection.", 3000)
        self._refresh_collections()

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

        try:
            hf_delete_collection(slug)
        except HFCollectionError as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self._status.showMessage("Collection deleted.", 3000)
        self._refresh_collections()
