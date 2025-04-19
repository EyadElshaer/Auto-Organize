from PyQt5.QtWidgets import (
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QHBoxLayout, QFileDialog
)
from PyQt5.QtCore import Qt
from tabs.base_tab import BaseTab

class MainTab(BaseTab):
    """Main tab with watcher pairs functionality"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI components"""
        self.main_layout.addWidget(QLabel("Watcher Pairs (Source → Target):"))
        
        # Create table for watch pairs
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Watch Folder", "Target Folder"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.main_layout.addWidget(self.table)

        # Add/Remove buttons
        buttons = QHBoxLayout()
        self.btn_add = QPushButton("+")
        self.btn_add.clicked.connect(self.add_pair)
        self.btn_remove = QPushButton("-")
        self.btn_remove.clicked.connect(self.remove_pair)
        buttons.addWidget(self.btn_add)
        buttons.addWidget(self.btn_remove)
        self.main_layout.addLayout(buttons)

        # Action buttons
        actions = QHBoxLayout()
        self.toggle_btn = QPushButton("Start")
        self.save_btn = QPushButton("Save")
        actions.addWidget(self.toggle_btn)
        actions.addWidget(self.save_btn)
        self.main_layout.addLayout(actions)

        # Status label
        self.status = QLabel("Status: Stopped")
        self.main_layout.addWidget(self.status)
        
    def add_table_row(self, watch="", target=""):
        """Add a new row to the watch pairs table"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(watch))
        self.table.setItem(row, 1, QTableWidgetItem(target))

    def add_pair(self):
        """Add a new watch pair through file dialog"""
        # Use the parent window (main application window) for the dialog
        # to prevent creating temporary windows that flash
        parent = self.parent_window if self.parent_window else self
        watch = QFileDialog.getExistingDirectory(parent, "Select Watch Folder")
        if not watch: return
        target = QFileDialog.getExistingDirectory(parent, "Select Target Folder")
        if not target: return
        self.add_table_row(watch, target)

    def remove_pair(self):
        """Remove the selected watch pair"""
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            
    def save_settings(self, config):
        """Save watch pairs to config"""
        pairs = []
        for row in range(self.table.rowCount()):
            watch = self.table.item(row, 0).text()
            target = self.table.item(row, 1).text()
            pairs.append((watch, target))
        config["watch_pairs"] = pairs
        
    def load_settings(self, config):
        """Load watch pairs from config"""
        for pair in config.get("watch_pairs", []):
            self.add_table_row(pair[0], pair[1])
            
    def get_watch_pairs(self):
        """Return all watch pairs as a list of tuples"""
        pairs = []
        for row in range(self.table.rowCount()):
            watch = self.table.item(row, 0).text()
            target = self.table.item(row, 1).text()
            pairs.append((watch, target))
        return pairs 