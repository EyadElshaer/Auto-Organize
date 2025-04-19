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

# Constants
AUTOSTART_PATH = os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\watcher_app.lnk")

class SettingsTab(BaseTab):
    """Settings tab for application preferences"""
    
    # Add a signal for theme changes
    theme_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI components"""
        # Preferences group
        group = QGroupBox("Preferences")
        g_layout = QVBoxLayout()

        # Run on startup checkbox
        self.run_startup_chk = QCheckBox("Run on Startup")
        self.run_startup_chk.setChecked(os.path.exists(AUTOSTART_PATH))
        g_layout.addWidget(self.run_startup_chk)

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

        # Theme selector
        theme_label = QLabel("Theme")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System Default", "Light", "Dark"])
        # Connect the theme combobox to the signal
        self.theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        g_layout.addWidget(theme_label)
        g_layout.addWidget(self.theme_combo)

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
        config["minimize_on_startup"] = self.minimize_chk.isChecked()
        config["exit_on_close"] = self.exit_on_close_chk.isChecked()
        config["auto_update_check"] = self.auto_update_chk.isChecked()
        config["show_notifications"] = self.notifications_chk.isChecked()
        config["theme"] = self.theme_combo.currentText()
        
    def load_settings(self, config):
        """Load settings from config"""
        self.minimize_chk.setChecked(config.get("minimize_on_startup", False))
        self.exit_on_close_chk.setChecked(config.get("exit_on_close", False))
        self.auto_update_chk.setChecked(config.get("auto_update_check", True))
        self.notifications_chk.setChecked(config.get("show_notifications", True))
        
        current_theme = config.get("theme", "System Default").lower()
        self.theme_combo.setCurrentIndex(
            {"system default": 0, "light": 1, "dark": 2}.get(current_theme, 0)
        )
        
    def toggle_autostart(self):
        """Toggle auto-start at Windows startup"""
        try:
            import winshell
            from win32com.client import Dispatch
            import sys
            
            script_path = sys.argv[0]
            if self.run_startup_chk.isChecked():
                shortcut = Dispatch('WScript.Shell').CreateShortCut(AUTOSTART_PATH)
                shortcut.Targetpath = script_path
                shortcut.WorkingDirectory = os.path.dirname(script_path)
                shortcut.IconLocation = script_path
                shortcut.save()
            else:
                if os.path.exists(AUTOSTART_PATH):
                    os.remove(AUTOSTART_PATH)
        except Exception as e:
            print(f"Error toggling autostart: {str(e)}") 