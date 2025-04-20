import os, json, urllib.request, webbrowser, sys
from PyQt5.QtWidgets import (
    QLabel, QPushButton, QGroupBox, QVBoxLayout, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont
from tabs.base_tab import BaseTab

def load_version(version_file):
    """Load version from file"""
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except:
        return "v0.0.0"

def get_resource_path(relative_path):
    """Get the correct resource path in both development and PyInstaller modes"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def safe_icon(icon_path):
    """Create a QIcon object with fallback to empty icon if file doesn't exist"""
    path = get_resource_path(icon_path)
    print(f"Looking for icon: {icon_path} at path: {path}")
    if os.path.exists(path):
        print(f"Found icon: {path}")
        return QIcon(path)
    # If icon doesn't exist but icon.ico does, use that instead
    ico_path = get_resource_path("icon.ico")
    if os.path.exists(ico_path):
        print(f"Using fallback icon: {ico_path}")
        return QIcon(ico_path)
    # Last resort - empty icon
    print(f"No icon found, returning empty QIcon")
    return QIcon()

class AboutTab(BaseTab):
    """About tab with version information and links"""
    
    def __init__(self, parent=None, version_file=None):
        super().__init__(parent)
        self.version_file = version_file
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI components"""
        # Version info
        version_container = QGroupBox("Version Information")
        version_layout = QVBoxLayout()
        
        # Load version from file
        current_version = load_version(self.version_file) if self.version_file else "N/A"
        
        # Create a more prominent version display
        self.version_label = QLabel(f"Version: {current_version}")
        self.version_label.setAlignment(Qt.AlignCenter)
        font = self.version_label.font()
        font.setPointSize(font.pointSize() + 2)  # Make font bigger
        font.setBold(True)
        self.version_label.setFont(font)
        
        # Auto-update status
        self.auto_update_status_label = QLabel()
        self.auto_update_status_label.setAlignment(Qt.AlignCenter)
        
        # Add update button with icon (if available)
        update_container = QHBoxLayout()
        self.update_btn = QPushButton("Check for Update")
        self.update_btn.clicked.connect(self.check_for_updates)
        try:
            self.update_btn.setIcon(safe_icon("icons/update.png"))
        except:
            pass  # No icon available
        update_container.addStretch()
        update_container.addWidget(self.update_btn)
        update_container.addStretch()
        
        version_layout.addWidget(self.version_label)
        version_layout.addWidget(self.auto_update_status_label)
        version_layout.addLayout(update_container)
        version_container.setLayout(version_layout)
        
        # About info
        about_container = QGroupBox("About")
        about_layout = QVBoxLayout()
        about_text = QLabel("Auto Organizer is a tool for automatically organizing files based on naming patterns.\n\n"
                          "© 2024-2025 Auto Organizer Team | Created by Eyad Elshaer")
        about_text.setWordWrap(True)
        about_text.setAlignment(Qt.AlignCenter)
        about_layout.addWidget(about_text)
        about_container.setLayout(about_layout)
        
        # GitHub link
        github_container = QHBoxLayout()
        github_btn = QPushButton("GitHub Repository")
        github_btn.clicked.connect(lambda: webbrowser.open("https://github.com/EyadElshaer/Auto-Organize"))
        github_container.addStretch()
        github_container.addWidget(github_btn)
        github_container.addStretch()
        
        self.main_layout.addWidget(version_container)
        self.main_layout.addWidget(about_container)
        self.main_layout.addLayout(github_container)
        self.main_layout.addStretch()
        
    def update_version_display(self, version):
        """Update the displayed version"""
        if hasattr(self, 'version_label') and self.version_label:
            self.version_label.setText(f"Version: {version}")
            
    def update_auto_update_status(self, enabled):
        """Update the auto-update status label"""
        if hasattr(self, 'auto_update_status_label') and self.auto_update_status_label:
            status = "Enabled" if enabled else "Disabled"
            self.auto_update_status_label.setText(f"Automatic update check: {status}")
            
    def check_for_updates(self):
        """Check for updates from GitHub"""
        try:
            with urllib.request.urlopen("https://api.github.com/repos/EyadElshaer/Auto-Organize/releases/latest") as res:
                data = json.load(res)
                latest_version = data["tag_name"]
                current_version = load_version(self.version_file) if self.version_file else "v0.0.0"
                
                # Log both versions for debugging
                print(f"Current version: {current_version}, Latest version: {latest_version}")
                
                # Use the main window as parent if available
                parent = self.parent() if hasattr(self, 'parent') and callable(self.parent) else self
                
                if latest_version != current_version:
                    msg = QMessageBox(parent)
                    msg.setWindowTitle("Update Available")
                    msg.setText(f"A new version is available!\n\nCurrent version: {current_version}\nLatest version: {latest_version}")
                    msg.setInformativeText("Would you like to download the update now?")
                    msg.setStandardButtons(QMessageBox.No | QMessageBox.Yes)
                    msg.setDefaultButton(QMessageBox.Yes)
                    # Make dialog modal to prevent interaction with parent window
                    msg.setModal(True)
                    
                    if msg.exec_() == QMessageBox.Yes:
                        webbrowser.open(data["html_url"])
                else:
                    QMessageBox.information(parent, "Up to Date", f"You're using the latest version ({current_version}).")
        except Exception as e:
            # Use the main window as parent if available
            parent = self.parent() if hasattr(self, 'parent') and callable(self.parent) else self
            QMessageBox.warning(parent, "Error", f"Failed to check for updates:\n{str(e)}")
            print(f"Update check error: {str(e)}")