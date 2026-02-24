"""Key list browser with tree view, grouped by ':' delimiter."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from side_redis.redis_client import redis_manager

SEPARATOR = ":"


class _PrefixTree:
    __slots__ = ("children", "is_key", "count")

    def __init__(self):
        self.children = None
        self.is_key = False
        self.count = 0

    def insert(self, parts):
        node = self
        for part in parts:
            if node.children is None:
                node.children = {}
            if part not in node.children:
                node.children[part] = _PrefixTree()
            node = node.children[part]
        node.is_key = True

    def recount(self, include_children=True):
        if self.children is None:
            self.count = 1 if self.is_key else 0
            return self.count
        if include_children:
            total = int(self.is_key)
            for child in self.children.values():
                total += child.recount(include_children=True)
        else:
            total = 1 if self.is_key else 0
        self.count = total
        return total

    def to_nodes(self, prefix=""):
        if self.children is None:
            return []
        folders = []
        leaves = []
        for segment in sorted(self.children, key=lambda x: str(x).lower()):
            child = self.children[segment]
            child_id = f"{prefix}{SEPARATOR}{segment}" if prefix else segment

            # If this node is itself a key (not just a parent), add it as a leaf
            if child.is_key:
                leaves.append(
                    {
                        "id": child_id,
                        "label": segment,
                        "icon": "key",
                    }
                )

            # Also add as folder if it has children
            if child.children is not None:
                # Count children (including nested ones)
                children_count = child.recount(include_children=True) - (1 if child.is_key else 0)
                node = {
                    "id": child_id,
                    "label": f"{segment} ({children_count})",
                    "icon": "folder",
                    "children": child.to_nodes(child_id),
                }
                folders.append(node)

        return folders + leaves


class KeysBrowser(QWidget):
    # Signals for cross-thread communication
    update_tree_signal = Signal(int)
    finish_load_signal = Signal(int)

    def __init__(self, on_key_selected):
        super().__init__()
        self.on_key_selected = on_key_selected
        self._key_set = set()
        self._prefix_tree = _PrefixTree()
        self.cursor = 0
        self.pattern = "*"
        self._exact_search = False
        self._is_search_mode = False

        # Lock for thread-safe access to _prefix_tree
        import threading
        self._tree_lock = threading.Lock()

        # Connect signals
        self.update_tree_signal.connect(self._update_tree_during_load)
        self.finish_load_signal.connect(self._finish_load_all)

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(4)

        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("Pattern (e.g. user:*)")
        self.pattern_input.returnPressed.connect(self._search)
        search_layout.addWidget(self.pattern_input, 1)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._search)
        search_btn.setMaximumWidth(60)
        search_layout.addWidget(search_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        refresh_btn.setMaximumWidth(60)
        search_layout.addWidget(refresh_btn)

        layout.addLayout(search_layout)

        # Options bar
        options_layout = QHBoxLayout()
        options_layout.setSpacing(8)

        self.exact_checkbox = QCheckBox("Exact")
        self.exact_checkbox.setToolTip("Treat input as exact key name instead of pattern")
        self.exact_checkbox.stateChanged.connect(self._on_exact_changed)
        options_layout.addWidget(self.exact_checkbox)
        options_layout.addSpacing(20)
        options_layout.addWidget(QLabel("DB:"))

        self.db_select = QComboBox()
        for i in range(16):
            self.db_select.addItem(f"db{i}", i)
        self.db_select.currentIndexChanged.connect(self._on_db_change)
        options_layout.addWidget(self.db_select)

        options_layout.addStretch()

        self.count_label = QLabel("0 keys")
        self.count_label.setStyleSheet("color: gray; font-size: 11px;")
        options_layout.addWidget(self.count_label)
        layout.addLayout(options_layout)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        # Buttons
        button_layout = QHBoxLayout()
        self.more_btn = QPushButton("Load more (200)")
        self.more_btn.clicked.connect(self._load_more)
        self.more_btn.setVisible(False)
        button_layout.addWidget(self.more_btn)

        self.load_all_btn = QPushButton("Load all")
        self.load_all_btn.clicked.connect(self._load_all)
        self.load_all_btn.setVisible(False)
        button_layout.addWidget(self.load_all_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _on_exact_changed(self, state):
        self._exact_search = (state == 2)  # Qt.Checked = 2

    def _search(self):
        raw = self.pattern_input.text().strip()
        if self._exact_search and raw:
            # Exact mode: try to read the key directly
            self._try_exact_key(raw)
            return

        # Pattern mode: normal search
        is_default = raw in ("", "*")
        self.pattern = raw or "*"
        self.cursor = 0
        self._key_set = set()
        self._prefix_tree = _PrefixTree()
        self._is_search_mode = not is_default
        self._load_keys()

    def _try_exact_key(self, key_name: str):
        """Try to read a key by exact name, testing all data types."""
        if not redis_manager.connected:
            return

        self.cursor = 0
        self._key_set = set()
        self._prefix_tree = _PrefixTree()

        # Try to get the key type
        try:
            key_type = redis_manager.get_key_type(key_name)
            # If key exists, add it to the tree
            if key_type != "none":
                self._key_set.add(key_name)
                self._prefix_tree.insert(key_name.split(SEPARATOR))
                self._prefix_tree.recount()
                self._update_tree()

                db_size = redis_manager.get_db_size()
                total = len(self._key_set)
                self.count_label.setText(f"Found: {total} key(s)")
                self.more_btn.setVisible(False)
                self.load_all_btn.setVisible(False)
            else:
                self.count_label.setText("Key not found")
                self._update_tree()
                self.more_btn.setVisible(False)
                self.load_all_btn.setVisible(False)
        except Exception as e:
            self.count_label.setText(f"Error: {e}")
            self._update_tree()
            self.more_btn.setVisible(False)
            self.load_all_btn.setVisible(False)

    def _refresh(self):
        self.cursor = 0
        self._key_set = set()
        self._prefix_tree = _PrefixTree()
        self._load_keys()

    def _load_more(self):
        self._load_keys()

    def _load_all(self):
        if not redis_manager.connected:
            return

        # Disable buttons and show loading
        self.more_btn.setEnabled(False)
        self.load_all_btn.setEnabled(False)

        # Start loading animation
        self._loading_dots = 0
        self._loading_timer = QTimer()
        self._loading_timer.timeout.connect(self._update_loading_animation)
        self._loading_timer.start(500)

        # Load in background thread
        import threading

        def load_all_thread():
            cursor = 0
            total_loaded = 0

            while True:
                cursor, keys = redis_manager.scan_keys(
                    pattern=self.pattern, count=200, cursor=cursor
                )

                for key in keys:
                    if key not in self._key_set:
                        # Use lock to protect _prefix_tree access
                        with self._tree_lock:
                            self._key_set.add(key)
                            self._prefix_tree.insert(key.split(SEPARATOR))
                    total_loaded += 1

                if cursor == 0:
                    break

            # Emit finish signal when done - this will update the tree once
            self.finish_load_signal.emit(total_loaded)

        thread = threading.Thread(target=load_all_thread, daemon=True)
        thread.start()

    def _update_tree_during_load(self, loaded_count):
        """Update tree during loading process."""
        self._prefix_tree.recount()
        self._update_tree()

        db_size = redis_manager.get_db_size()
        total = len(self._key_set)
        self.count_label.setText(f"Loading: {total} / {db_size}{'' * self._loading_dots}")

    def _update_loading_animation(self):
        """Update loading animation dots."""
        self._loading_dots = (self._loading_dots + 1) % 4
        dots = '.' * self._loading_dots
        db_size = redis_manager.get_db_size()
        total = len(self._key_set)
        self.count_label.setText(f"Loading: {total} / {db_size}{dots}")

    def _finish_load_all(self, loaded_count):
        """Called when load all is complete."""
        # Stop loading animation
        if hasattr(self, '_loading_timer'):
            self._loading_timer.stop()

        self._prefix_tree.recount()
        self._update_tree()

        db_size = redis_manager.get_db_size()
        total = len(self._key_set)
        self.count_label.setText(f"{total} loaded / {db_size} total")

        self.more_btn.setVisible(False)
        self.load_all_btn.setVisible(False)
        self.more_btn.setEnabled(True)
        self.load_all_btn.setEnabled(True)

    def _load_keys(self):
        if not redis_manager.connected:
            return

        try:
            new_cursor, new_keys = redis_manager.scan_keys(
                pattern=self.pattern, count=200, cursor=self.cursor
            )
            self.cursor = new_cursor

            for key in new_keys:
                if key not in self._key_set:
                    # Use lock to protect _prefix_tree access
                    with self._tree_lock:
                        self._key_set.add(key)
                        self._prefix_tree.insert(key.split(SEPARATOR))

            # Update tree with lock protection
            with self._tree_lock:
                self._prefix_tree.recount()

            self._update_tree()

            self.more_btn.setVisible(self.cursor != 0)
            self.load_all_btn.setVisible(self.cursor != 0)

            db_size = redis_manager.get_db_size()
            self.count_label.setText(f"{len(self._key_set)} loaded / {db_size} total")

        except Exception as e:
            self.count_label.setText(f"Error: {e}")

    def _update_tree(self):
        # Save expanded state
        expanded_items = set()
        root = self.tree.invisibleRootItem()
        self._save_expanded_state(root, "", expanded_items)

        # Rebuild tree with lock protection
        with self._tree_lock:
            nodes = self._prefix_tree.to_nodes()

        self.tree.clear()
        self._add_nodes(None, nodes)

        # Restore expanded state
        self._restore_expanded_state(root, "", expanded_items)

    def _save_expanded_state(self, item, path, expanded_set):
        for i in range(item.childCount()):
            child = item.child(i)
            data = child.data(0, Qt.UserRole)
            if isinstance(data, dict):
                child_path = f"{path}:{data.get('id', '')}" if path else data.get('id', '')
                if child.isExpanded():
                    expanded_set.add(child_path)
                # Recursively save children
                if child.childCount() > 0:
                    self._save_expanded_state(child, child_path, expanded_set)

    def _restore_expanded_state(self, item, path, expanded_set):
        for i in range(item.childCount()):
            child = item.child(i)
            data = child.data(0, Qt.UserRole)
            if isinstance(data, dict):
                child_path = f"{path}:{data.get('id', '')}" if path else data.get('id', '')
                if child_path in expanded_set:
                    child.setExpanded(True)
                # Recursively restore children
                if child.childCount() > 0:
                    self._restore_expanded_state(child, child_path, expanded_set)

    def _add_nodes(self, parent, nodes):
        for node in nodes:
            if parent is None:
                item = QTreeWidgetItem(self.tree)
            else:
                item = QTreeWidgetItem(parent)
            item.setText(0, node.get("label", ""))
            item.setData(0, Qt.UserRole, {"id": node.get("id", ""), "icon": node.get("icon", "")})
            children = node.get("children", [])
            if children:
                self._add_nodes(item, children)
                item.setExpanded(False)

    def _on_item_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, dict):
            node_id = data.get("id", "")
            icon_type = data.get("icon", "")
            # Only trigger selection if the item is a key, not a folder
            if icon_type == "key" and node_id and node_id in self._key_set:
                if self.on_key_selected:
                    self.on_key_selected(node_id)

    def _on_db_change(self, index):
        if redis_manager.connected:
            redis_manager.select_db(index)
            self._refresh()

    def load_initial(self):
        """Load initial keys - called from main thread."""
        if redis_manager.connected:
            self.db_select.setCurrentIndex(redis_manager.db)
            self._search()
