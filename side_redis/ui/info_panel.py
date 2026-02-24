"""Redis server info dashboard."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from side_redis.redis_client import redis_manager


class InfoPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignTop)
        layout.addWidget(self.scroll)

        self.content_widget = QWidget()
        self.scroll.setWidget(self.content_widget)

        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignTop)

    def refresh(self):
        # Clear content by recreating widget
        old_widget = self.content_widget
        self.content_widget = QWidget()
        self.scroll.setWidget(self.content_widget)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignTop)
        try:
            if old_widget:
                old_widget.deleteLater()
        except RuntimeError:
            pass

        if not redis_manager.connected:
            label = QLabel("Not connected")
            label.setStyleSheet("color: gray;")
            self.content_layout.addWidget(label)
            return

        try:
            info = redis_manager.get_server_info()
        except Exception as e:
            label = QLabel(f"Error: {e}")
            label.setStyleSheet("color: red;")
            self.content_layout.addWidget(label)
            return

        title = QLabel("Server Information")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.content_layout.addWidget(title)

        # Metrics grid
        metrics_layout = QGridLayout()
        metrics_layout.setSpacing(10)

        self._metric_card(
            metrics_layout, 0, "Version", info.get("redis_version", "N/A")
        )
        self._metric_card(
            metrics_layout, 1, "Uptime", f"{info.get('uptime_in_days', 0)}d"
        )
        self._metric_card(
            metrics_layout, 2, "Clients", str(info.get("connected_clients", 0))
        )
        self._metric_card(
            metrics_layout, 3, "Memory", info.get("used_memory_human", "N/A")
        )

        keys_count = sum(
            v.get("keys", 0)
            for k, v in info.items()
            if isinstance(v, dict) and "keys" in v
        )
        self._metric_card(metrics_layout, 4, "Keys", str(keys_count))
        self._metric_card(
            metrics_layout, 5, "Ops/sec", str(info.get("instantaneous_ops_per_sec", 0))
        )

        self.content_layout.addLayout(metrics_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        self.content_layout.addWidget(separator)

        # Detailed sections
        sections = {
            "Server": [
                "redis_version",
                "redis_mode",
                "os",
                "tcp_port",
                "uptime_in_seconds",
                "uptime_in_days",
            ],
            "Memory": [
                "used_memory_human",
                "used_memory_peak_human",
                "maxmemory_human",
                "mem_fragmentation_ratio",
            ],
            "Stats": [
                "total_connections_received",
                "total_commands_processed",
                "instantaneous_ops_per_sec",
                "keyspace_hits",
                "keyspace_misses",
            ],
            "Replication": ["role", "connected_slaves"],
            "Persistence": ["rdb_last_save_time", "aof_enabled"],
        }

        for section_name, fields in sections.items():
            group = QGroupBox(section_name)
            group_layout = QGridLayout()
            group_layout.setSpacing(5)

            row = 0
            for field in fields:
                val = info.get(field)
                if val is not None:
                    field_label = QLabel(field)
                    field_label.setStyleSheet("color: gray;")
                    value_label = QLabel(str(val))
                    value_label.setStyleSheet("font-family: monospace;")
                    group_layout.addWidget(field_label, row, 0)
                    group_layout.addWidget(value_label, row, 1)
                    row += 1

            group.setLayout(group_layout)
            self.content_layout.addWidget(group)

        # Database info
        db_group = QGroupBox("Keyspace")
        db_layout = QVBoxLayout()

        for key, val in info.items():
            if key.startswith("db") and isinstance(val, dict):
                db_label = QLabel(key)
                db_label.setStyleSheet("font-weight: bold; color: #2196F3;")
                db_layout.addWidget(db_label)

                for k, v in val.items():
                    row_layout = QHBoxLayout()
                    row_layout.addWidget(QLabel(f"  {k}:"))
                    row_layout.addWidget(QLabel(str(v)))
                    row_layout.addStretch()
                    db_layout.addLayout(row_layout)

        db_group.setLayout(db_layout)
        self.content_layout.addWidget(db_group)

    def _metric_card(self, layout, index, title: str, value: str):
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(
            "QFrame { border-radius: 5px; padding: 10px; }"
        )

        card_layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: gray; font-size: 11px;")
        card_layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        card_layout.addWidget(value_label)

        layout.addWidget(card, index // 3, index % 3)
