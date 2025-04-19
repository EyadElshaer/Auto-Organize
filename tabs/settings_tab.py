import os
from PyQt5.QtWidgets import (
    QLabel, QPushButton, QCheckBox, QGroupBox, 
    QVBoxLayout, QHBoxLayout, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
# When running directly
try:
    from tabs.base_tab import BaseTab
except ModuleNotFoundError:
    from base_tab import BaseTab  # For direct execution

class SettingsTab(BaseTab):
    """Settings tab for application preferences"""
    
    # Add a signal for theme changes
    theme_changed = pyqtSignal(str)
    start_on_launch_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Initialize the UI components"""
        # Preferences group
        group = QGroupBox("Preferences")
        g_layout = QVBoxLayout()

        # Start on Launch checkbox
        self.start_launch_chk = QCheckBox("Start on Launch")
        self.start_launch_chk.setToolTip("Automatically start organizing when application launches")
        self.start_launch_chk.stateChanged.connect(self.start_on_launch_changed.emit)
        g_layout.addWidget(self.start_launch_chk)

        # Minimize on startup checkbox
        self.minimize_chk = QCheckBox("Minimize to tray on launch")
        g_layout.addWidget(self.minimize_chk)

        # Exit on close checkbox
        self.exit_on_close_chk = QCheckBox("Exit completely on close")
        g_layout.addWidget(self.exit_on_close_chk)
        
        # Auto update checkbox
        self.auto_update_chk = QCheckBox("Check for updates automatically")
        g_layout.addWidget(self.auto_update_chk)
        
        # Notifications checkbox
        self.notifications_chk = QCheckBox("Show system tray notifications")
        g_layout.addWidget(self.notifications_chk)

        # Theme selector in horizontal layout
        theme_container = QHBoxLayout()
        theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System Default", "Light", "Dark"])
        self.theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        theme_container.addWidget(theme_label)
        theme_container.addWidget(self.theme_combo)
        theme_container.addStretch()
        g_layout.addLayout(theme_container)

        group.setLayout(g_layout)
        self.main_layout.addWidget(group)

        # Buttons row
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.reset_btn = QPushButton("Reset Settings")
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.reset_btn)
        self.main_layout.addLayout(btn_row)

    def save_settings(self, config):
        """Save settings to config"""
        config["start_on_launch"] = self.start_launch_chk.isChecked()
        config["minimize_on_startup"] = self.minimize_chk.isChecked()
        config["exit_on_close"] = self.exit_on_close_chk.isChecked()
        config["auto_update_check"] = self.auto_update_chk.isChecked()
        config["show_notifications"] = self.notifications_chk.isChecked()
        config["theme"] = self.theme_combo.currentText()

    def load_settings(self, config):
        """Load settings from config"""
        self.start_launch_chk.setChecked(config.get("start_on_launch", False))
        self.minimize_chk.setChecked(config.get("minimize_on_startup", False))
        self.exit_on_close_chk.setChecked(config.get("exit_on_close", False))
        self.auto_update_chk.setChecked(config.get("auto_update_check", True))
        self.notifications_chk.setChecked(config.get("show_notifications", True))
        
        current_theme = config.get("theme", "System Default").lower()
        theme_index = {
            "system default": 0,
            "light": 1,
            "dark": 2,
        }.get(current_theme, 0)
        self.theme_combo.setCurrentIndex(theme_index)