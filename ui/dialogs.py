from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPlainTextEdit,
    QGroupBox,
    QMessageBox,
    QPushButton,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
)

from hf_backend.hf_model_card import (
    PIPELINE_TAGS,
    LICENSES,
    LIBRARY_NAMES,
    COMMON_LANGUAGES,
)


class LoginDialog(QDialog):

    def __init__(self, initial_token: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hugging Face Login")
        self.setMinimumWidth(500)

        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QLabel(
            "Enter your Hugging Face access token.\n"
            "Get one at: https://huggingface.co/settings/tokens"
        ))

        form = QFormLayout()
        self._token_input = QLineEdit()
        self._token_input.setEchoMode(QLineEdit.Password)
        self._token_input.setPlaceholderText("hf_...")
        self._token_input.setText(initial_token)
        form.addRow("Token:", self._token_input)

        self._show_token = QCheckBox("Show token")
        self._show_token.toggled.connect(
            lambda checked: self._token_input.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        form.addRow("", self._show_token)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self._token_input.text().strip():
            QMessageBox.warning(self, "Validation", "Token cannot be empty.")
            return
        self.accept()

    def get_token(self) -> str:
        return self._token_input.text().strip()


class CreateRepoDialog(QDialog):

    def __init__(self, username: str = "", orgs: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create New Repository")
        self.setMinimumWidth(500)

        layout = QVBoxLayout()
        self.setLayout(layout)

        form = QFormLayout()

        self._namespace_combo = QComboBox()
        if username:
            self._namespace_combo.addItem(username, username)
        for org in (orgs or []):
            self._namespace_combo.addItem(f"{org} (org)", org)
        form.addRow("Owner:", self._namespace_combo)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("my-awesome-model")
        form.addRow("Name:", self._name_input)

        self._type_combo = QComboBox()
        self._type_combo.addItem("Model", "model")
        self._type_combo.addItem("Dataset", "dataset")
        self._type_combo.addItem("Space", "space")
        form.addRow("Type:", self._type_combo)

        self._private_check = QCheckBox("Private repository")
        form.addRow("Visibility:", self._private_check)

        layout.addLayout(form)

        self._preview = QLabel("")
        self._preview.setStyleSheet("QLabel { color: #888; padding: 5px; }")
        layout.addWidget(self._preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._name_input.textChanged.connect(self._update_preview)
        self._namespace_combo.currentIndexChanged.connect(self._update_preview)
        self._update_preview()

    def _update_preview(self) -> None:
        ns = self._namespace_combo.currentData() or ""
        name = self._name_input.text().strip() or "<name>"
        self._preview.setText(f"Repo ID: {ns}/{name}")

    def _validate_and_accept(self) -> None:
        if not self._name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Repository name is required.")
            return
        self.accept()

    def get_details(self) -> dict:
        ns = self._namespace_combo.currentData() or ""
        name = self._name_input.text().strip()
        return {
            "repo_id": f"{ns}/{name}",
            "repo_type": self._type_combo.currentData(),
            "private": self._private_check.isChecked(),
        }


class UploadDialog(QDialog):

    def __init__(self, repo_id: str = "", last_dir: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Upload to {repo_id}")
        self.setMinimumWidth(600)

        self._last_dir = last_dir
        layout = QVBoxLayout()
        self.setLayout(layout)

        mode_layout = QHBoxLayout()
        self._mode_files = QPushButton("Select Files")
        self._mode_folder = QPushButton("Select Folder")
        mode_layout.addWidget(self._mode_files)
        mode_layout.addWidget(self._mode_folder)
        layout.addLayout(mode_layout)

        self._file_list = QListWidget()
        self._file_list.setMinimumHeight(120)
        layout.addWidget(self._file_list)

        self._selected_paths: list[str] = []
        self._is_folder: bool = False
        self._folder_path: str = ""

        form = QFormLayout()
        self._path_in_repo = QLineEdit()
        self._path_in_repo.setPlaceholderText("(root of repo — or enter a subdirectory, e.g. 'models/')")
        form.addRow("Upload to path:", self._path_in_repo)

        self._commit_msg = QLineEdit()
        self._commit_msg.setText("Upload files")
        self._commit_msg.setPlaceholderText("Commit message")
        form.addRow("Commit message:", self._commit_msg)

        self._revision = QLineEdit()
        self._revision.setText("main")
        form.addRow("Branch:", self._revision)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._mode_files.clicked.connect(self._select_files)
        self._mode_folder.clicked.connect(self._select_folder)

    def _select_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select files to upload", self._last_dir
        )
        if files:
            self._is_folder = False
            self._selected_paths = files
            self._folder_path = ""
            self._file_list.clear()
            for f in files:
                self._file_list.addItem(f)

    def _select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select folder to upload", self._last_dir
        )
        if folder:
            self._is_folder = True
            self._folder_path = folder
            self._selected_paths = []
            self._file_list.clear()
            self._file_list.addItem(f"[FOLDER] {folder}")

    def _validate_and_accept(self) -> None:
        if not self._selected_paths and not self._folder_path:
            QMessageBox.warning(self, "Validation", "Please select files or a folder to upload.")
            return
        self.accept()

    def get_details(self) -> dict:
        return {
            "is_folder": self._is_folder,
            "folder_path": self._folder_path,
            "file_paths": self._selected_paths,
            "path_in_repo": self._path_in_repo.text().strip() or ".",
            "commit_message": self._commit_msg.text().strip() or "Upload files",
            "revision": self._revision.text().strip() or "main",
        }


class ModelCardDialog(QDialog):

    def __init__(self, existing_content: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Model Card Editor")
        self.setMinimumSize(800, 700)

        layout = QVBoxLayout()
        self.setLayout(layout)

        meta_group = QGroupBox("Metadata (YAML frontmatter)")
        meta_form = QFormLayout()
        meta_group.setLayout(meta_form)

        self._model_name = QLineEdit()
        self._model_name.setPlaceholderText("My Cool Model")
        meta_form.addRow("Model name:", self._model_name)

        self._language = QComboBox()
        self._language.setEditable(True)
        for lang in COMMON_LANGUAGES:
            self._language.addItem(lang)
        meta_form.addRow("Language:", self._language)

        self._license = QComboBox()
        self._license.setEditable(True)
        for lic in LICENSES:
            self._license.addItem(lic)
        meta_form.addRow("License:", self._license)

        self._library = QComboBox()
        self._library.setEditable(True)
        for lib in LIBRARY_NAMES:
            self._library.addItem(lib)
        meta_form.addRow("Library:", self._library)

        self._pipeline = QComboBox()
        self._pipeline.setEditable(True)
        for tag in PIPELINE_TAGS:
            self._pipeline.addItem(tag)
        meta_form.addRow("Pipeline tag:", self._pipeline)

        self._base_model = QLineEdit()
        self._base_model.setPlaceholderText("e.g. meta-llama/Llama-3-8B")
        meta_form.addRow("Base model:", self._base_model)

        self._tags = QLineEdit()
        self._tags.setPlaceholderText("Comma-separated: quantized, gguf, chat")
        meta_form.addRow("Tags:", self._tags)

        self._datasets = QLineEdit()
        self._datasets.setPlaceholderText("Comma-separated dataset IDs")
        meta_form.addRow("Datasets:", self._datasets)

        layout.addWidget(meta_group)

        content_group = QGroupBox("Card Content (Markdown)")
        content_layout = QVBoxLayout()
        content_group.setLayout(content_layout)

        self._description_edit = QPlainTextEdit()
        self._description_edit.setPlaceholderText("Describe what this model does...")
        self._description_edit.setMaximumHeight(80)
        content_layout.addWidget(QLabel("Model Description:"))
        content_layout.addWidget(self._description_edit)

        self._use_edit = QPlainTextEdit()
        self._use_edit.setPlaceholderText("How should this model be used?")
        self._use_edit.setMaximumHeight(60)
        content_layout.addWidget(QLabel("Intended Use:"))
        content_layout.addWidget(self._use_edit)

        self._training_edit = QPlainTextEdit()
        self._training_edit.setPlaceholderText("Training data, hyperparameters, etc.")
        self._training_edit.setMaximumHeight(60)
        content_layout.addWidget(QLabel("Training Details:"))
        content_layout.addWidget(self._training_edit)

        self._eval_edit = QPlainTextEdit()
        self._eval_edit.setPlaceholderText("Benchmark scores, evaluation metrics, etc.")
        self._eval_edit.setMaximumHeight(60)
        content_layout.addWidget(QLabel("Evaluation:"))
        content_layout.addWidget(self._eval_edit)

        self._limitations_edit = QPlainTextEdit()
        self._limitations_edit.setPlaceholderText("Known limitations, biases, risks...")
        self._limitations_edit.setMaximumHeight(60)
        content_layout.addWidget(QLabel("Limitations:"))
        content_layout.addWidget(self._limitations_edit)

        layout.addWidget(content_group)

        raw_group = QGroupBox("Raw README.md (advanced — edit directly)")
        raw_layout = QVBoxLayout()
        raw_group.setLayout(raw_layout)

        self._raw_editor = QPlainTextEdit()
        self._raw_editor.setPlaceholderText("Full README.md content will appear here...")
        raw_layout.addWidget(self._raw_editor)

        btn_generate = QPushButton("Generate from fields above ↓")
        btn_generate.clicked.connect(self._generate_to_raw)
        raw_layout.addWidget(btn_generate)

        layout.addWidget(raw_group, 2)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if existing_content:
            self._raw_editor.setPlainText(existing_content)

    def _parse_csv(self, text: str) -> list[str]:
        return [t.strip() for t in text.split(",") if t.strip()]

    def _generate_to_raw(self) -> None:
        from hf_backend.hf_model_card import generate_model_card

        content = generate_model_card(
            model_name=self._model_name.text().strip() or "My Model",
            language=self._language.currentText().strip(),
            license=self._license.currentText().strip(),
            library_name=self._library.currentText().strip(),
            pipeline_tag=self._pipeline.currentText().strip(),
            tags=self._parse_csv(self._tags.text()) or None,
            base_model=self._base_model.text().strip(),
            datasets=self._parse_csv(self._datasets.text()) or None,
            model_description=self._description_edit.toPlainText().strip(),
            intended_use=self._use_edit.toPlainText().strip(),
            training_details=self._training_edit.toPlainText().strip(),
            evaluation=self._eval_edit.toPlainText().strip(),
            limitations=self._limitations_edit.toPlainText().strip(),
        )
        self._raw_editor.setPlainText(content)

    def get_content(self) -> str:
        return self._raw_editor.toPlainText()


class CreateCollectionDialog(QDialog):

    def __init__(self, username: str = "", orgs: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Collection")
        self.setMinimumWidth(450)

        layout = QVBoxLayout()
        self.setLayout(layout)

        form = QFormLayout()

        self._namespace_combo = QComboBox()
        if username:
            self._namespace_combo.addItem(username, username)
        for org in (orgs or []):
            self._namespace_combo.addItem(f"{org} (org)", org)
        form.addRow("Owner:", self._namespace_combo)

        self._title = QLineEdit()
        self._title.setPlaceholderText("My Awesome Collection")
        form.addRow("Title:", self._title)

        self._description = QPlainTextEdit()
        self._description.setPlaceholderText("Description of this collection...")
        self._description.setMaximumHeight(80)
        form.addRow("Description:", self._description)

        self._private = QCheckBox("Private collection")
        form.addRow("Visibility:", self._private)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self._title.text().strip():
            QMessageBox.warning(self, "Validation", "Title is required.")
            return
        self.accept()

    def get_details(self) -> dict:
        return {
            "title": self._title.text().strip(),
            "namespace": self._namespace_combo.currentData() or None,
            "description": self._description.toPlainText().strip(),
            "private": self._private.isChecked(),
        }


class AddToCollectionDialog(QDialog):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Item to Collection")
        self.setMinimumWidth(450)

        layout = QVBoxLayout()
        self.setLayout(layout)

        form = QFormLayout()

        self._item_id = QLineEdit()
        self._item_id.setPlaceholderText("username/repo-name")
        form.addRow("Item ID:", self._item_id)

        self._item_type = QComboBox()
        self._item_type.addItem("Model", "model")
        self._item_type.addItem("Dataset", "dataset")
        self._item_type.addItem("Space", "space")
        self._item_type.addItem("Paper", "paper")
        form.addRow("Type:", self._item_type)

        self._note = QLineEdit()
        self._note.setPlaceholderText("Optional note (max 500 chars)")
        self._note.setMaxLength(500)
        form.addRow("Note:", self._note)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self._item_id.text().strip():
            QMessageBox.warning(self, "Validation", "Item ID is required.")
            return
        self.accept()

    def set_defaults(self, item_id: str = "", item_type: str = "") -> None:
        if item_id:
            self._item_id.setText(item_id)
        if item_type:
            idx = self._item_type.findData(item_type)
            if idx >= 0:
                self._item_type.setCurrentIndex(idx)

    def get_details(self) -> dict:
        return {
            "item_id": self._item_id.text().strip(),
            "item_type": self._item_type.currentData(),
            "note": self._note.text().strip(),
        }


class TextEditorDialog(QDialog):

    def __init__(self, title: str, content: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self._editor = QPlainTextEdit()
        self._editor.setPlainText(content)
        self._editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = self._editor.font()
        font.setFamily("monospace")
        font.setPointSize(10)
        self._editor.setFont(font)
        layout.addWidget(self._editor, 1)

        form = QFormLayout()
        self._commit_msg = QLineEdit()
        self._commit_msg.setText(f"Update {title.split(' - ')[-1] if ' - ' in title else 'file'}")
        form.addRow("Commit message:", self._commit_msg)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_content(self) -> str:
        return self._editor.toPlainText()

    def get_commit_message(self) -> str:
        return self._commit_msg.text().strip() or "Update file"
