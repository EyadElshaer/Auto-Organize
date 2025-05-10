import os
from PyQt5.QtWidgets import (
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QHBoxLayout, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from tabs.base_tab import BaseTab

# Import functions from main app
try:
    from watcher_app import get_resource_path, safe_icon
except ImportError:
    # Fallback implementations for when running the tab directly
    def get_resource_path(relative_path):
        return os.path.join(os.path.dirname(__file__), '..', relative_path)

    def safe_icon(icon_path):
        path = get_resource_path(icon_path)
        if os.path.exists(path):
            return QIcon(path)
        return QIcon()

class MainTab(BaseTab):
    """Main tab with watcher pairs functionality"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.is_dark_mode = False
        self.is_initializing = True  # Flag to prevent auto-save during initialization
        self.init_ui()
        self.is_initializing = False  # Initialization complete

    def init_ui(self):
        """Initialize the UI components"""
        self.main_layout.addWidget(QLabel("Watcher Pairs (Source → Target):"))

        # Create table for watch pairs with improved appearance
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Watch Folder", "Target Folder"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)  # Alternate row colors for better readability
        # We'll use a property to store the current theme
        self.is_dark_mode = False

        # Initial styling will be set, but will be updated when theme changes
        self.update_table_style()
        self.main_layout.addWidget(self.table)

        # Add/Remove buttons with improved appearance
        buttons = QHBoxLayout()

        self.btn_add = QPushButton("Add Folder Pair")
        self.btn_add.setIcon(safe_icon("icons/add.png") if os.path.exists(get_resource_path("icons/add.png")) else QIcon())
        self.btn_add.setMinimumHeight(30)
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
                border: 2px solid #388E3C;
                outline: none;
            }
            QPushButton:hover {
                background-color: #45a049;
                border: 2px solid #2E7D32;
            }
            QPushButton:pressed {
                background-color: #388E3C;
                border: 2px solid #1B5E20;
            }
        """)
        self.btn_add.clicked.connect(self.add_pair)

        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.setIcon(safe_icon("icons/remove.png") if os.path.exists(get_resource_path("icons/remove.png")) else QIcon())
        self.btn_remove.setMinimumHeight(30)
        self.btn_remove.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
                border: 2px solid #D32F2F;
                outline: none;
            }
            QPushButton:hover {
                background-color: #d32f2f;
                border: 2px solid #B71C1C;
            }
            QPushButton:pressed {
                background-color: #C62828;
                border: 2px solid #8B0000;
            }
        """)
        self.btn_remove.clicked.connect(self.remove_pair)

        buttons.addWidget(self.btn_add)
        buttons.addWidget(self.btn_remove)
        self.main_layout.addLayout(buttons)

        # Action button with improved appearance
        actions = QHBoxLayout()
        self.toggle_btn = QPushButton("Start Watching")
        self.toggle_btn.setIcon(safe_icon("icons/play.png") if os.path.exists(get_resource_path("icons/play.png")) else QIcon())
        self.toggle_btn.setMinimumHeight(36)  # Make button taller
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 8px 16px;
                border: 2px solid #1976D2;
                outline: none;
            }
            QPushButton:hover {
                background-color: #0b7dda;
                border: 2px solid #0D47A1;
            }
            QPushButton:pressed {
                background-color: #1565C0;
                border: 2px solid #0D47A1;
            }
        """)
        actions.addWidget(self.toggle_btn)
        self.main_layout.addLayout(actions)

        # Status label - styling will be set by update_status_style
        self.status = QLabel("Status: Stopped")
        self.main_layout.addWidget(self.status)

        # Initialize status style
        self.update_status_style()

    def add_table_row(self, watch="", target=""):
        """Add a new row to the watch pairs table"""
        # Temporarily disconnect itemChanged signal to prevent multiple auto-saves
        if self.parent_window and not self.is_initializing:
            try:
                self.table.itemChanged.disconnect(self.parent_window.auto_save_settings)
            except TypeError:
                # Signal might not be connected
                pass

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(watch))
        self.table.setItem(row, 1, QTableWidgetItem(target))

        # Reconnect signal and trigger auto-save
        if self.parent_window and not self.is_initializing:
            self.table.itemChanged.connect(self.parent_window.auto_save_settings)
            self.parent_window.auto_save_settings()
            if watch and target:  # Only show message if both are provided
                self.parent_window.statusBar().showMessage(f"Added watch pair: {watch} → {target}", 3000)

    def add_pair(self):
        """Add a new watch pair through file dialog"""
        # Use the parent window (main application window) for the dialog
        # to prevent creating temporary windows that flash
        parent = self.parent_window if self.parent_window else self
        watch = QFileDialog.getExistingDirectory(parent, "Select Watch Folder")
        if not watch: return
        target = QFileDialog.getExistingDirectory(parent, "Select Target Folder")
        if not target: return

        # Add the row (auto-save is handled in add_table_row)
        self.add_table_row(watch, target)

    def remove_pair(self):
        """Remove the selected watch pair"""
        row = self.table.currentRow()
        if row >= 0:
            # Get the pair info before removing for status message
            watch = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            target = self.table.item(row, 1).text() if self.table.item(row, 1) else ""

            # Temporarily disconnect itemChanged signal to prevent multiple auto-saves
            if self.parent_window:
                try:
                    self.table.itemChanged.disconnect(self.parent_window.auto_save_settings)
                except TypeError:
                    # Signal might not be connected
                    pass

            self.table.removeRow(row)

            # Reconnect signal and trigger auto-save
            if self.parent_window:
                self.table.itemChanged.connect(self.parent_window.auto_save_settings)
                self.parent_window.auto_save_settings()
                self.parent_window.statusBar().showMessage(f"Removed watch pair: {watch} → {target}", 3000)

    def save_settings(self, config):
        """Save watch pairs to config"""
        pairs = []
        for row in range(self.table.rowCount()):
            watch = self.table.item(row, 0).text()
            target = self.table.item(row, 1).text()
            pairs.append((watch, target))
        config["watch_pairs"] = pairs

    def update_table_style(self):
        """Update table styling based on current theme"""
        if self.is_dark_mode:
            # Dark mode styling
            self.table.setStyleSheet("""
                QTableWidget {
                    gridline-color: #3a3a3a;
                    border: 1px solid #505050;
                    border-radius: 4px;
                    background-color: #2d2d2d;
                    alternate-background-color: #353535;
                    color: #e0e0e0;
                }
                QTableWidget::item {
                    padding: 4px;
                    border-color: #3a3a3a;
                }
                QTableWidget::item:selected {
                    background-color: #0078d7;
                    color: white;
                }
                QHeaderView::section {
                    background-color: #383838;
                    padding: 6px;
                    font-weight: bold;
                    border: 1px solid #505050;
                    color: #e0e0e0;
                }
            """)
        else:
            # Light mode styling
            self.table.setStyleSheet("""
                QTableWidget {
                    gridline-color: #d0d0d0;
                    border: 1px solid #c0c0c0;
                    border-radius: 4px;
                    background-color: white;
                    alternate-background-color: #f5f5f5;
                }
                QTableWidget::item {
                    padding: 4px;
                }
                QTableWidget::item:selected {
                    background-color: #0078d7;
                    color: white;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    padding: 6px;
                    font-weight: bold;
                    border: 1px solid #c0c0c0;
                }
            """)

    def set_dark_mode(self, is_dark):
        """Set dark mode and update styling"""
        self.is_dark_mode = is_dark
        self.update_table_style()
        self.update_status_style()

    def update_status_style(self):
        """Update status label styling based on theme and current state"""
        text = self.status.text()

        if "Watching" in text:
            if self.is_dark_mode:
                self.status.setStyleSheet("""
                    QLabel {
                        font-weight: bold;
                        font-size: 14px;
                        padding: 8px;
                        border: 1px solid #388E3C;
                        border-radius: 4px;
                        background-color: #1B5E20;
                        color: #AAFFAA;
                        margin-top: 10px;
                    }
                """)
            else:
                self.status.setStyleSheet("""
                    QLabel {
                        font-weight: bold;
                        font-size: 14px;
                        padding: 8px;
                        border: 1px solid #4CAF50;
                        border-radius: 4px;
                        background-color: #E8F5E9;
                        color: #2E7D32;
                        margin-top: 10px;
                    }
                """)
        elif "❗" in text:
            if self.is_dark_mode:
                self.status.setStyleSheet("""
                    QLabel {
                        font-weight: bold;
                        font-size: 14px;
                        padding: 8px;
                        border: 1px solid #C62828;
                        border-radius: 4px;
                        background-color: #8B0000;
                        color: #FFAAAA;
                        margin-top: 10px;
                    }
                """)
            else:
                self.status.setStyleSheet("""
                    QLabel {
                        font-weight: bold;
                        font-size: 14px;
                        padding: 8px;
                        border: 1px solid #f44336;
                        border-radius: 4px;
                        background-color: #ffebee;
                        color: #c62828;
                        margin-top: 10px;
                    }
                """)
        else:
            if self.is_dark_mode:
                self.status.setStyleSheet("""
                    QLabel {
                        font-weight: bold;
                        font-size: 14px;
                        padding: 8px;
                        border: 1px solid #505050;
                        border-radius: 4px;
                        background-color: #383838;
                        color: #b0b0b0;
                        margin-top: 10px;
                    }
                """)
            else:
                self.status.setStyleSheet("""
                    QLabel {
                        font-weight: bold;
                        font-size: 14px;
                        padding: 8px;
                        border: 1px solid #d0d0d0;
                        border-radius: 4px;
                        background-color: #f8f8f8;
                        color: #757575;
                        margin-top: 10px;
                    }
                """)

    def load_settings(self, config):
        """Load watch pairs from config"""
        # Set initializing flag to prevent auto-save during loading
        old_initializing = self.is_initializing
        self.is_initializing = True

        try:
            # Clear existing rows first
            while self.table.rowCount() > 0:
                self.table.removeRow(0)

            # Add pairs from config
            for pair in config.get("watch_pairs", []):
                self.add_table_row(pair[0], pair[1])
        finally:
            # Restore initializing flag
            self.is_initializing = old_initializing

    def get_watch_pairs(self):
        """Return all watch pairs as a list of tuples"""
        pairs = []
        for row in range(self.table.rowCount()):
            watch = self.table.item(row, 0).text()
            target = self.table.item(row, 1).text()
            pairs.append((watch, target))
        return pairs