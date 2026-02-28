# HF Hub Manager

A PySide6 desktop application for managing your Hugging Face Hub account — repositories, files, model cards, and collections — all from a single GUI.

## Features

- **Authentication**: Login with your Hugging Face access token (persisted securely via OS settings); auto-detects cached tokens from `huggingface-cli login` on startup
- **Repository Management**: Create, browse, delete, and toggle visibility of models, datasets, and spaces
- **Favorites**: Mark repos as favorites and filter the list to show only favorites
- **Search & Filtering**: Filter your repo list by keyword; switch between Models, Datasets, and Spaces via dropdown
- **File Browser**: Browse repo file trees with branch selection, upload files/folders, download, edit text files in the built-in editor, and delete — all with commit messages
- **File Size Guard**: Text files over 10 MB are blocked from the built-in editor with guidance to download, edit locally, and re-upload
- **README / Model Card Editor**: View, edit, or generate model cards from a structured template with YAML frontmatter (license, pipeline tag, library, language, tags, base model, datasets, etc.)
- **Collections**: Create, browse, add items to, remove items from, and delete Hugging Face collections
- **Branch Support**: Switch between branches when browsing files; the default branch is detected automatically from the repo's refs
- **Retry with Backoff**: API calls automatically retry on transient network errors and HTTP 5xx responses
- **Logging**: Timestamped log files are written to the `logs/` directory for diagnostics
- **Window State Persistence**: Window size, position, splitter state, last repo type, and favorites filter are remembered between sessions

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

## Key Keyboard Shortcuts & Interactions

- **Double-click** a text file in the file browser to edit it (files over 10 MB show guidance instead)
- **Right-click** files for context menu (edit, download, delete); multi-select supported for batch delete
- **Right-click** a repo in the list to add/remove it from favorites
- **Right-click** a collection for add item, open in browser, or delete; right-click an item to remove it
- **Click column headers** in the repo list to sort by name, visibility, downloads, likes, or modified date
- **Enter** in the search box to filter repos
- All destructive actions (delete repo, delete files, delete collection) require confirmation

## Notes

- The app uses the `huggingface_hub` Python library under the hood — all operations go through the official HF API
- Large file uploads use HF's built-in LFS support automatically
- Your token is stored via `QSettings` (OS-level settings storage) — on Linux this is typically in `~/.config/LocalTools/HFHubManager.conf`
- Log files are saved to the `logs/` directory in the project root, with automatic cleanup keeping the 10 most recent files
