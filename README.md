# SideRedis

A modern Redis visual client built with PySide6, featuring multi-threading optimization and intuitive tree-view key management.

![SideRedis Logo](side_redis/static/logo.svg)

## Features

### 🗂️ Tree-View Key Browser
- Keys automatically grouped by `:` delimiter into collapsible folder hierarchy
- Real-time key counting for each folder
- Smart key display: keys that are also folders appear in both locations
- Expand/collapse state preserved during pagination
- Efficient loading with "Load more (200)" and "Load all" options
- Progress indicator during bulk loading

### 🔧 Full Type Support
- **String** — View, edit, and format JSON
- **Hash** — Add, edit, and delete fields
- **List** — Paginated viewing (100 items per page) with "Load more" button
- **Set** — Sorted member display with pagination
- **Sorted Set** — View members with scores, paginated loading
- **Stream** — Stream data visualization

### ⚡ Performance
- **Multi-threading optimized** — Thread pool executor for non-blocking Redis operations
- **Efficient pagination** — Load data in batches to prevent UI freezing
- **Real-time updates** — UI updates every 500 keys during bulk loading
- **Thread-safe operations** — Proper locking for concurrent data access

### 🔌 Connection Management
- Save and switch between multiple Redis connection profiles
- Auto-connect to last used connection on startup
- Connection timeout protection
- Password and username authentication support

### 📊 Server Dashboard
- Real-time server information display
- Version, uptime, memory usage
- Connected clients count
- Operations per second
- Database statistics

### 💻 Command Console
- Interactive Redis CLI with command history
- Up/Down arrow keys for command navigation
- Clear command history support
- Real-time command execution feedback

### 🎨 User Interface
- **Dark Mode** — Toggle between dark and light themes
- **Responsive layout** — Adjustable splitter panels
- **Keyboard shortcuts** — Efficient navigation
- **Modern design** — Clean, intuitive interface

## Quick Start

**Prerequisites**: Python 3.12+, a running Redis server

```bash
# Install dependencies (uv recommended)
uv sync

# Or with pip
pip install -r requirements.txt

# Run
uv run python -m side_redis.main

# Or directly
python -m side_redis.main
```

## Architecture

```
PySide6 (Qt)  ←ThreadPool→  Redis
      ↑                ↑
  Qt Widgets      Redis Client
  Signal/Slot        ThreadPoolExecutor
```

**Key optimizations**:

| Feature | Implementation |
|---------|---------------|
| Thread Pool | `ThreadPoolExecutor` for all Redis operations |
| Non-blocking UI | All operations return control immediately |
| Connection Pool | Shared pool across all threads |
| Thread-safe Data | Locking for concurrent tree updates |
| Pagination | Batch loading (100-500 items per batch) |

## Usage

### Connecting to Redis
1. Click "Connect" button or use File → Connect
2. Enter connection details (host, port, password)
3. Click "Save" to store the connection profile
4. Click "Connect" to establish connection

### Browsing Keys
- Keys are automatically grouped by `:` delimiter
- Click folders to expand/collapse
- Click key names to view details
- Use "Load more" to load additional keys
- Use "Load all" to load all keys (with progress indicator)

### Managing Keys
- **View** — Click on any key to see its value
- **Edit** — Modify values and save changes
- **Delete** — Remove keys with confirmation
- **Rename** — Change key names
- **TTL** — Set expiration time

### Running Commands
- Switch to "Console" tab
- Type Redis commands (e.g., `SET key value`, `GET key`)
- Use Up/Down arrows to navigate history
- Click "Send" or press Enter to execute

## Project Structure

```
side_redis/
├── main.py                 # Application entry point
├── redis_client.py         # Redis connection manager
├── connection_store.py     # Connection profile storage
├── ui/
│   ├── connection.py       # Connection dialog
│   ├── keys_browser.py     # Tree-view key browser
│   ├── key_detail.py       # Key detail viewer/editor
│   ├── info_panel.py       # Server information panel
│   ├── terminal.py         # Command console
│   └── add_key_dialog.py   # Add new key dialog
└── static/
    ├── logo.svg            # Application logo
    ├── banner.svg          # Banner image
    └── favicon.svg         # Favicon icon
```

## License

MIT
