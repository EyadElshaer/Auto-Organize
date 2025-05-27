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
        self.parent_window = parent
        self.is_dark_mode = False
        self.is_initializing = True  # Flag to prevent auto-save during initialization
        self.init_ui()
        self.is_initializing = False  # Initialization complete

    def init_ui(self):
        """Initialize the UI components"""
        # Preferences group with improved appearance
        group = QGroupBox("Preferences")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #c0c0c0;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        g_layout = QVBoxLayout()
        g_layout.setSpacing(10)  # Add more space between items

        # Common checkbox style with subtle hover effect
        checkbox_style = """
            QCheckBox {
                font-size: 13px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox:hover {
                background-color: rgba(240, 240, 240, 0.5);
                border-radius: 4px;
            }
        """

        # Start on Launch checkbox
        self.start_launch_chk = QCheckBox("Start on Launch")
        self.start_launch_chk.setToolTip("Automatically start organizing when application launches")
        self.start_launch_chk.stateChanged.connect(self.start_on_launch_changed.emit)
        self.start_launch_chk.setStyleSheet(checkbox_style)
        g_layout.addWidget(self.start_launch_chk)

        # Minimize on startup checkbox
        self.minimize_chk = QCheckBox("Minimize to tray on launch")
        self.minimize_chk.setStyleSheet(checkbox_style)
        g_layout.addWidget(self.minimize_chk)

        # Exit on close checkbox
        self.exit_on_close_chk = QCheckBox("Exit completely on close")
        self.exit_on_close_chk.setStyleSheet(checkbox_style)
        g_layout.addWidget(self.exit_on_close_chk)

        # Auto update checkbox
        self.auto_update_chk = QCheckBox("Check for updates automatically")
        self.auto_update_chk.setStyleSheet(checkbox_style)
        g_layout.addWidget(self.auto_update_chk)

        # Notifications checkbox
        self.notifications_chk = QCheckBox("Show system tray notifications")
        self.notifications_chk.setStyleSheet(checkbox_style)
        g_layout.addWidget(self.notifications_chk)

        # Theme selector in horizontal layout with improved appearance
        theme_container = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                padding: 5px;
            }
        """)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System Default", "Light", "Dark"])
        self.theme_combo.setMinimumHeight(30)

        # Initial styling will be set by update_theme_selector_style
        # but we'll provide a default style here
        self.theme_combo.setStyleSheet("""
            QComboBox {
                font-size: 13px;
                padding: 5px 10px;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                min-width: 150px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #c0c0c0;
            }
            QComboBox::down-arrow {
                /* First try to use the image */
                image: url(icons/dropdown.png);
                width: 12px;
                height: 12px;
                /* Fallback styling in case image isn't available */
                color: #333;
                border: none;
            }
            QComboBox::down-arrow:on {
                /* shift the arrow when popup is open */
                top: 1px;
                left: 1px;
            }
            QComboBox:hover {
                border: 1px solid #0078d7;
            }
            /* Make sure the dropdown items are visible with proper contrast */
            QComboBox QAbstractItemView {
                border: 1px solid #c0c0c0;
                selection-background-color: #0078d7;
                selection-color: white;
            }
            /* Style for dropdown items */
            QComboBox QAbstractItemView::item {
                min-height: 24px;
                padding: 4px;
            }
            /* Hover effect for dropdown items */
            QComboBox QAbstractItemView::item:hover {
                background-color: rgba(0, 120, 215, 0.2);
            }
        """)
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)

        theme_container.addWidget(theme_label)
        theme_container.addWidget(self.theme_combo)
        theme_container.addStretch()
        g_layout.addLayout(theme_container)

        # Max File Age setting
        max_age_container = QHBoxLayout()
        max_age_label = QLabel("Only Process Files Modified in Last X Hours:")
        max_age_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        self.max_file_age_spinbox = QSpinBox()
        self.max_file_age_spinbox.setToolTip("Set the maximum age in hours for files to be processed. 0 means no limit.")
        self.max_file_age_spinbox.setRange(0, 8760) # 0 to 1 year in hours
        self.max_file_age_spinbox.setValue(48) # Default UI value
        self.max_file_age_spinbox.setSuffix(" hours")
        self.max_file_age_spinbox.setStyleSheet("""
            QSpinBox {
                font-size: 13px;
                padding: 5px;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                min-width: 80px;
            }
        """)
        if self.parent_window: # Connect only if parent_window exists
            self.max_file_age_spinbox.valueChanged.connect(lambda value: self.on_spinbox_changed(self.max_file_age_spinbox, value))


        max_age_container.addWidget(max_age_label)
        max_age_container.addWidget(self.max_file_age_spinbox)
        max_age_container.addStretch()
        g_layout.addLayout(max_age_container)

        group.setLayout(g_layout)
        self.main_layout.addWidget(group)

        # Initialize theme selector style
        self.update_theme_selector_style()

        # Reset button with improved appearance
        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton("Reset All Settings")
        self.reset_btn.setMinimumHeight(36)  # Make button taller
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 8px 16px;
                border: 2px solid #F57C00;
                outline: none;
            }
            QPushButton:hover {
                background-color: #F57C00;
                border: 2px solid #E65100;
            }
            QPushButton:pressed {
                background-color: #EF6C00;
                border: 2px solid #E65100;
            }
        """)
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
        config["max_file_age_hours"] = self.max_file_age_spinbox.value()

    def set_dark_mode(self, is_dark):
        """Set dark mode and update styling"""
        self.is_dark_mode = is_dark
        self.update_theme_selector_style()
        self.update_checkbox_style()

    def update_theme_selector_style(self):
        """Update theme selector styling based on current theme"""
        if self.is_dark_mode:
            self.theme_combo.setStyleSheet("""
                QComboBox {
                    font-size: 13px;
                    padding: 5px 10px;
                    border: 1px solid #505050;
                    border-radius: 4px;
                    min-width: 150px;
                    background-color: #383838;
                    color: #e0e0e0;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #505050;
                }
                QComboBox::down-arrow {
                    /* First try to use the white arrow image for dark mode */
                    image: url(icons/dropdown_white.png);
                    width: 12px;
                    height: 12px;
                    /* Fallback styling in case image isn't available */
                    color: #e0e0e0;
                    border: none;
                }
                QComboBox::down-arrow:on {
                    /* shift the arrow when popup is open */
                    top: 1px;
                    left: 1px;
                }
                QComboBox:hover {
                    border: 1px solid #0078d7;
                }
                /* Make sure the dropdown items are visible with proper contrast */
                QComboBox QAbstractItemView {
                    border: 1px solid #505050;
                    selection-background-color: #0078d7;
                    selection-color: white;
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                }
                /* Style for dropdown items */
                QComboBox QAbstractItemView::item {
                    min-height: 24px;
                    padding: 4px;
                    color: #e0e0e0;
                }
                /* Hover effect for dropdown items */
                QComboBox QAbstractItemView::item:hover {
                    background-color: rgba(0, 120, 215, 0.4);
                }
            """)
        else:
            self.theme_combo.setStyleSheet("""
                QComboBox {
                    font-size: 13px;
                    padding: 5px 10px;
                    border: 1px solid #c0c0c0;
                    border-radius: 4px;
                    min-width: 150px;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #c0c0c0;
                }
                QComboBox::down-arrow {
                    /* First try to use the image */
                    image: url(icons/dropdown.png);
                    width: 12px;
                    height: 12px;
                    /* Fallback styling in case image isn't available */
                    color: #333;
                    border: none;
                }
                QComboBox::down-arrow:on {
                    /* shift the arrow when popup is open */
                    top: 1px;
                    left: 1px;
                }
                QComboBox:hover {
                    border: 1px solid #0078d7;
                }
                /* Make sure the dropdown items are visible with proper contrast */
                QComboBox QAbstractItemView {
                    border: 1px solid #c0c0c0;
                    selection-background-color: #0078d7;
                    selection-color: white;
                    background-color: white;
                    color: black;
                }
                /* Style for dropdown items */
                QComboBox QAbstractItemView::item {
                    min-height: 24px;
                    padding: 4px;
                }
                /* Hover effect for dropdown items */
                QComboBox QAbstractItemView::item:hover {
                    background-color: rgba(0, 120, 215, 0.2);
                }
            """)

    def on_theme_changed(self, theme):
        """Handle theme changes and emit signal"""
        if not self.is_initializing and self.parent_window:
            # Emit the signal for the theme change
            self.theme_changed.emit(theme)

            # Show a message in the status bar
            self.parent_window.statusBar().showMessage(f"Theme changed to: {theme}", 3000)

    def on_checkbox_changed(self, checkbox, state):
        """Handle checkbox state changes and trigger auto-save"""
        if not self.is_initializing and self.parent_window:
            # Get checkbox name for status message
            checkbox_name = ""
            if checkbox == self.start_launch_chk:
                checkbox_name = "Start on Launch"
                # Special handling for start_on_launch
                self.start_on_launch_changed.emit(state == 2)  # 2 = Qt.Checked
            elif checkbox == self.minimize_chk:
                checkbox_name = "Minimize to tray on launch"
            elif checkbox == self.exit_on_close_chk:
                checkbox_name = "Exit completely on close"
            elif checkbox == self.auto_update_chk:
                checkbox_name = "Check for updates automatically"
            elif checkbox == self.notifications_chk:
                checkbox_name = "Show system tray notifications"

            # Trigger auto-save
            self.parent_window.auto_save_settings()

            # Show status message
            status = "enabled" if state == 2 else "disabled"
            self.parent_window.statusBar().showMessage(f"{checkbox_name} {status}", 3000)

    def update_checkbox_style(self):
        """Update checkbox styling based on current theme"""
        if self.is_dark_mode:
            checkbox_style = """
                QCheckBox {
                    font-size: 13px;
                    padding: 5px;
                    color: #e0e0e0;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
                QCheckBox:hover {
                    background-color: rgba(80, 80, 80, 0.5);
                    border-radius: 4px;
                }
            """
        else:
            checkbox_style = """
                QCheckBox {
                    font-size: 13px;
                    padding: 5px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
                QCheckBox:hover {
                    background-color: rgba(240, 240, 240, 0.5);
                    border-radius: 4px;
                }
            """

        # Apply the style to all checkboxes
        self.start_launch_chk.setStyleSheet(checkbox_style)
        self.minimize_chk.setStyleSheet(checkbox_style)
        self.exit_on_close_chk.setStyleSheet(checkbox_style)
        self.auto_update_chk.setStyleSheet(checkbox_style)
        self.notifications_chk.setStyleSheet(checkbox_style)

    def load_settings(self, config):
        """Load settings from config"""
        # Set initializing flag to prevent auto-save during loading
        old_initializing = self.is_initializing
        self.is_initializing = True

        try:
            # Temporarily disconnect signals to prevent auto-save
            if self.parent_window:
                try:
                    self.start_launch_chk.stateChanged.disconnect(self.parent_window.auto_save_settings)
                    self.minimize_chk.stateChanged.disconnect(self.parent_window.auto_save_settings)
                    self.exit_on_close_chk.stateChanged.disconnect(self.parent_window.auto_save_settings)
                    self.auto_update_chk.stateChanged.disconnect(self.parent_window.auto_save_settings)
                    self.notifications_chk.stateChanged.disconnect(self.parent_window.auto_save_settings)
            if hasattr(self, 'max_file_age_spinbox'):
                self.max_file_age_spinbox.valueChanged.disconnect(self.parent_window.auto_save_settings)
                except TypeError:
                    # Signals might not be connected
                    pass

            # Load settings
            self.start_launch_chk.setChecked(config.get("start_on_launch", False))
            self.minimize_chk.setChecked(config.get("minimize_on_startup", False))
            self.exit_on_close_chk.setChecked(config.get("exit_on_close", False))
            self.auto_update_chk.setChecked(config.get("auto_update_check", True))
            self.notifications_chk.setChecked(config.get("show_notifications", True))
            self.max_file_age_spinbox.setValue(config.get("max_file_age_hours", 48)) # Default to 48

            current_theme = config.get("theme", "System Default").lower()
            theme_index = {
                "system default": 0,
                "light": 1,
                "dark": 2,
            }.get(current_theme, 0)
            self.theme_combo.setCurrentIndex(theme_index)

            # Reconnect signals
            if self.parent_window:
                self.start_launch_chk.stateChanged.connect(lambda state: self.on_checkbox_changed(self.start_launch_chk, state))
                self.minimize_chk.stateChanged.connect(lambda state: self.on_checkbox_changed(self.minimize_chk, state))
                self.exit_on_close_chk.stateChanged.connect(lambda state: self.on_checkbox_changed(self.exit_on_close_chk, state))
                self.auto_update_chk.stateChanged.connect(lambda state: self.on_checkbox_changed(self.auto_update_chk, state))
                self.notifications_chk.stateChanged.connect(lambda state: self.on_checkbox_changed(self.notifications_chk, state))
                if hasattr(self, 'max_file_age_spinbox'): # Check if spinbox exists before connecting
                    self.max_file_age_spinbox.valueChanged.connect(lambda value: self.on_spinbox_changed(self.max_file_age_spinbox, value))
        finally:
            # Restore initializing flag
            self.is_initializing = old_initializing

    def on_spinbox_changed(self, spinbox, value):
        """Handle QSpinBox value changes and trigger auto-save"""
        if not self.is_initializing and self.parent_window:
            spinbox_name = ""
            if spinbox == self.max_file_age_spinbox:
                spinbox_name = "Max File Age"
            
            # Trigger auto-save
            self.parent_window.auto_save_settings()

            # Show status message
            self.parent_window.statusBar().showMessage(f"{spinbox_name} set to {value} hours", 3000)