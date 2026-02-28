# HF Hub Manager

A PySide6 desktop application for managing your Hugging Face Hub account — repositories, files, model cards, and collections — all from a single GUI.

## Features

- **Authentication**: Login with your Hugging Face access token (persisted securely in OS settings)
- **Repository Management**: Create, browse, delete, and toggle visibility of models, datasets, and spaces
- **File Browser**: Browse repo file trees, upload files/folders, download, edit text files, and delete — all with commit messages and branch selection
- **README / Model Card Editor**: View, edit, or generate model cards from a structured template with YAML frontmatter (license, pipeline tag, library, language, tags, etc.)
- **Collections**: Create, browse, add items to, and delete Hugging Face collections
- **Branch Support**: Switch between branches when browsing files
- **Window State Persistence**: Window size, position, and splitter state are remembered between sessions

## Installation

```bash
pip install PySide6 huggingface_hub
```

Or using the requirements file:

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

1. Click **Login** and paste your Hugging Face access token (get one at https://huggingface.co/settings/tokens — you need a token with `write` scope).
2. Your repositories will load automatically. Use the dropdown to switch between Models, Datasets, and Spaces.
3. Select a repo from the left panel to browse its files, view/edit its README, or manage collections.

## Project Structure

```
hf_hub_manager/
├── main.py                      # Entry point
├── settings.py                  # Persistent settings (QSettings)
├── requirements.txt
├── hf_backend/
│   ├── __init__.py
│   ├── hf_auth.py               # Token management, login, whoami
│   ├── hf_repos.py              # Create, list, delete repos; list files & branches
│   ├── hf_files.py              # Upload, download, delete, edit files
│   ├── hf_collections.py        # Collections CRUD
│   └── hf_model_card.py         # Model card generation & push
├── ui/
│   ├── __init__.py
│   ├── main_window.py           # Main application window
│   ├── repo_browser.py          # File tree browser widget
│   ├── collection_manager.py    # Collection list/manager widget
│   └── dialogs.py               # Login, Create Repo, Upload, Model Card,
│                                  Collection, Text Editor dialogs
└── fs_ops/
    └── __init__.py
```

## Key Keyboard Shortcuts & Interactions

- **Double-click** a text file in the file browser to edit it
- **Right-click** files for context menu (edit, download, delete)
- **Right-click** collections or collection items for context menu actions
- **Enter** in the search box to filter repos
- All destructive actions (delete repo, delete files, delete collection) require confirmation

## Notes

- The app uses the `huggingface_hub` Python library under the hood — all operations go through the official HF API
- Large file uploads use HF's built-in LFS support automatically
- Your token is stored via `QSettings` (OS-level settings storage) — on Linux this is typically in `~/.config/LocalTools/HFHubManager.conf`
- The app auto-detects cached tokens from `huggingface-cli login` on startup
