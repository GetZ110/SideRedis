"""Dialog for adding new keys."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class AddKeyDialog(QDialog):
    """Dialog to add a new Redis key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Key")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Key name")
        form_layout.addRow("Key:", self.key_input)

        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("Value")
        form_layout.addRow("Value:", self.value_input)

        self.type_select = QComboBox()
        self.type_select.addItems(["string", "list", "set", "hash", "zset"])
        form_layout.addRow("Type:", self.type_select)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        """Get the entered values."""
        return (
            self.key_input.text(),
            self.value_input.text(),
            self.type_select.currentText(),
        )
