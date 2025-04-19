import sys, os, re, json, urllib.request, platform
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu, QAction, QMessageBox
)
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtCore import QTimer, Qt

# Import tab modules
from tabs import MainTab, SettingsTab, LogsTab, AboutTab, load_version

# Constants
CONFIG_FILE = os.path.expanduser("~/.watcher_pairs_config.json")
AUTOSTART_PATH = os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\watcher_app.lnk")
VERSION_FILE = os.path.join(os.path.dirname(__file__), "version.txt")

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
    if os.path.exists(path):
        print(f"Found icon: {path}")
        return QIcon(path)
    # If icon doesn't exist but icon.ico does, use that instead
    ico_path = get_resource_path("icon.ico")
    if os.path.exists(ico_path):
        print(f"Using fallback icon: {ico_path} for {icon_path}")
        return QIcon(ico_path)
    # Last resort - empty icon
    print(f"WARNING: No icon found for {icon_path}")
    return QIcon()

def get_windows_system_theme():
    try:
        import winreg
        reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        key = winreg.OpenKey(reg, key_path)
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value == 1 else "dark"
    except:
        return "light"

class WatcherApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Organizer")
        # Use safe_icon for window icon
        self.setWindowIcon(safe_icon("icon.ico"))
        self.setGeometry(100, 100, 750, 500)
        self.load_config()
        self.apply_theme(self.config.get("theme", "System Default"))

        # Set proper window flags to improve minimize behavior
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMinimizeButtonHint)

        # Initialize state variables
        self.watching = False
        
        # Initialize tabs
        self.init_tabs()

        # Setup system tray
        self.setup_tray()
        
        # Setup timers
        self.setup_timers()
        
        # Auto-hide if configured
        if self.config.get("minimize_on_startup", False):
            self.hide_to_tray()
            
    def setup_tray(self):
        """Setup the system tray icon and menu"""
        # Check if system tray is supported
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("System tray is not available on this system")
            return
            
        # Use safe_icon for tray icon
        self.tray = QSystemTrayIcon(safe_icon("icon.ico"), self)
        self.tray.setToolTip("Auto Organizer")
        
        # Create tray menu
        self.tray_menu = QMenu()
        
        # Add enable/disable actions
        self.enable_action = QAction("Enable Watching", self, triggered=self.enable_watching)
        self.disable_action = QAction("Disable Watching", self, triggered=self.disable_watching)
        
        # Add other actions
        self.open_action = QAction("Open", self, triggered=self.restore_window)
        self.exit_action = QAction("Exit", self, triggered=QApplication.quit)
        
        # Add actions to menu
        self.tray_menu.addAction(self.enable_action)
        self.tray_menu.addAction(self.disable_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.open_action)
        self.tray_menu.addAction(self.exit_action)
        
        # Set initial state
        self.update_tray_menu()
        
        # Set the context menu
        self.tray.setContextMenu(self.tray_menu)
        
        # Activate the tray icon
        self.tray.show()
        
        # Connect activation signal to handle tray icon clicks
        self.tray.activated.connect(self.tray_activated)
        
        # Check if the tray icon is visible
        if not self.tray.isVisible():
            print("Tray icon may not be visible - trying to show again")
            self.tray.show()
        
    def update_tray_menu(self):
        """Update the tray menu based on watching state"""
        if self.watching:
            self.enable_action.setVisible(False)
            self.disable_action.setVisible(True)
            self.tray.setToolTip("Auto Organizer (Watching)")
        else:
            self.enable_action.setVisible(True)
            self.disable_action.setVisible(False)
            self.tray.setToolTip("Auto Organizer (Stopped)")
            
    def enable_watching(self):
        """Enable watching from tray menu"""
        pairs = self.main_tab.get_watch_pairs()
        if not pairs:
            self.show_notification(
                "Error", 
                "Add at least one watcher pair first.", 
                QSystemTrayIcon.Warning, 
                3000
            )
            return
            
        self.watching = True
        self.timer.start(2000)
        self.main_tab.toggle_btn.setText("Stop")
        self.main_tab.status.setText("Status: Watching...")
        self.update_tray_menu()
        
        self.show_notification(
            "Watching", 
            "Auto Organizer is now watching folders", 
            QSystemTrayIcon.Information, 
            2000
        )
        
    def disable_watching(self):
        """Disable watching from tray menu"""
        self.watching = False
        self.timer.stop()
        self.main_tab.toggle_btn.setText("Start")
        self.main_tab.status.setText("Status: Stopped")
        self.update_tray_menu()
        
        self.show_notification(
            "Stopped", 
            "Auto Organizer has stopped watching folders", 
            QSystemTrayIcon.Information, 
            2000
        )
        
    def toggle_watch(self):
        """Toggle watching from main UI"""
        if not self.watching:
            # Get watch pairs from the main tab
            pairs = self.main_tab.get_watch_pairs()
            if not pairs:
                self.main_tab.status.setText("Add at least one watcher pair ❗")
                return
                
            self.watching = True
            self.timer.start(2000)
            self.main_tab.toggle_btn.setText("Stop")
            self.main_tab.status.setText("Status: Watching...")
        else:
            self.watching = False
            self.timer.stop()
            self.main_tab.toggle_btn.setText("Start")
            self.main_tab.status.setText("Status: Stopped")
            
        # Update tray menu to reflect new state
        self.update_tray_menu()

    def setup_timers(self):
        """Setup application timers"""
        # Timer for scanning watch dirs
        self.timer = QTimer()
        self.timer.timeout.connect(self.scan_all_pairs)
        self.watching = False
        
        # Timer to check for version changes
        self.version_timer = QTimer()
        self.version_timer.timeout.connect(self.refresh_version)
        self.version_timer.start(5000)  # Check every 5 seconds
        
        # Setup auto-update check timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.auto_check_for_updates)
        # Check for updates once per day (86400000 ms)
        if self.config.get("auto_update_check", True):
            self.update_timer.start(86400000)  # 24 hours

        # Update version if needed
        current_version = load_version(VERSION_FILE)
        if current_version != self.config.get("version", "v0.0.0"):
            self.config["version"] = current_version
            self.refresh_version()

    def init_tabs(self):
        """Initialize all application tabs"""
        from PyQt5.QtWidgets import QTabWidget
        
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Main tab - explicitly pass self as parent
        self.main_tab = MainTab(self)
        self.main_tab.toggle_btn.clicked.connect(self.toggle_watch)
        self.main_tab.save_btn.clicked.connect(self.save_settings)
        self.main_tab.load_settings(self.config)
        # Use safe_icon for tab icons
        self.tabs.addTab(self.main_tab, safe_icon("watch.png"), "Watchers")
        
        # Settings tab - explicitly pass self as parent
        self.settings_tab = SettingsTab(self)
        self.settings_tab.save_btn.clicked.connect(self.save_settings)
        self.settings_tab.reset_btn.clicked.connect(self.reset_settings)
        self.settings_tab.run_startup_chk.stateChanged.connect(self.settings_tab.toggle_autostart)
        self.settings_tab.theme_changed.connect(self.apply_theme)
        self.settings_tab.load_settings(self.config)
        self.tabs.addTab(self.settings_tab, safe_icon("settings.png"), "Settings")
        
        # Logs tab - explicitly pass self as parent
        self.logs_tab = LogsTab(self)
        self.tabs.addTab(self.logs_tab, safe_icon("logs.png"), "Logs")
        
        # About tab - explicitly pass self as parent
        self.about_tab = AboutTab(self, VERSION_FILE)
        self.about_tab.update_auto_update_status(self.config.get("auto_update_check", True))
        self.tabs.addTab(self.about_tab, safe_icon("info.png"), "About")

    def apply_theme(self, theme):
        theme = theme.lower()
        app = QApplication.instance()
        palette = QPalette()

        if theme == "system default":
            if platform.system() == "Windows":
                theme = get_windows_system_theme()
            else:
                theme = "light"

        if theme == "dark":
            app.setStyle("Fusion")
            # Dark gray instead of pure black
            dark_color = QColor(45, 45, 45)
            darker_color = QColor(35, 35, 35)
            mid_color = QColor(55, 55, 55)
            
            palette.setColor(QPalette.Window, darker_color)
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, dark_color)
            palette.setColor(QPalette.AlternateBase, mid_color)
            palette.setColor(QPalette.ToolTipBase, dark_color)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, dark_color)
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.white)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
        elif theme == "light":
            app.setStyle("Fusion")
            palette.setColor(QPalette.Window, Qt.white)
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Base, Qt.white)
            palette.setColor(QPalette.AlternateBase, QColor(240, 240, 240))
            palette.setColor(QPalette.ToolTipBase, Qt.black)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.black)
            palette.setColor(QPalette.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ButtonText, Qt.black)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            palette.setColor(QPalette.Link, QColor(0, 0, 255))

        app.setPalette(palette)

    def restore_window(self):
        """Restore window from system tray"""
        # Restore normal window flags
        self.setWindowFlags(self.windowFlags() & ~Qt.Tool)
        self.setVisible(True)
        self.showNormal()
        self.activateWindow()
        self.raise_()  # Bring window to front

    def save_settings(self):
        # Save settings from all tabs
        self.main_tab.save_settings(self.config)
        self.settings_tab.save_settings(self.config)
        
        # Handle auto-update timer
        if self.config["auto_update_check"]:
            # Start or restart the update timer
            self.update_timer.start(86400000)  # 24 hours
        else:
            # Stop the timer if auto-update is disabled
            self.update_timer.stop()
            
        # Update about tab display
        self.about_tab.update_auto_update_status(self.config["auto_update_check"])
            
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f)
        QMessageBox.information(self, "Saved", "Settings saved successfully.")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {}
        self.config.setdefault("version", load_version(VERSION_FILE))
        self.config.setdefault("minimize_on_startup", False)
        self.config.setdefault("exit_on_close", False)
        self.config.setdefault("auto_update_check", True)
        self.config.setdefault("show_notifications", True)
        self.config.setdefault("theme", "System Default")

    def scan_all_pairs(self):
        import shutil
        import subprocess
        
        # Set startupinfo to hide command window on Windows
        startupinfo = None
        if platform.system() == 'Windows':
            try:
                import subprocess
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
            except Exception as e:
                self.logs_tab.log(f"Error setting up subprocess: {str(e)}")
        
        pairs = self.main_tab.get_watch_pairs()
        if not pairs:
            return
            
        for watch, target in pairs:
            if not os.path.isdir(watch) or not os.path.isdir(target):
                continue

            try:
                # Get items inside directory
                items = os.listdir(watch)
            except Exception as e:
                self.logs_tab.log(f"Error scanning directory {watch}: {str(e)}")
                continue
                
            for item in items:
                src = os.path.join(watch, item)
                if not os.path.exists(src): continue

                # Skip files that have been undone
                if "(Undo)" in item:
                    continue

                split_parts = re.split(r"[,()\[\]-]", item)
                if len(split_parts) < 2 or not split_parts[1].strip():
                    continue

                extension = os.path.splitext(item)[1]
                main_folder = split_parts[0].strip()
                if not main_folder: continue

                base_name = split_parts[1].strip()
                final_name = base_name if base_name.lower().endswith(extension.lower()) else base_name + extension

                subfolders = []
                subfolders += [g for group in re.findall(r"\(([^)]+)\)|\[(.*?)\]|\{(.*?)\}", item) for g in group if g]
                subfolders += re.findall(r"\-([^\-]+)\-", item)

                dest_path = os.path.join(target, main_folder, *subfolders)
                try:
                    os.makedirs(dest_path, exist_ok=True)
                    dest = os.path.join(dest_path, final_name)
                    
                    # Use native file system operations to avoid console window
                    if platform.system() == 'Windows':
                        try:
                            # Use silent move with robocopy on Windows
                            if os.path.isdir(src):
                                # For directories
                                cmd = ["robocopy", src, dest, "/E", "/MOVE", "/NFL", "/NDL", "/NJH", "/NJS"]
                                subprocess.run(cmd, startupinfo=startupinfo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            else:
                                # For files - use built-in shutil move which should be silent now with startupinfo
                                shutil.move(src, dest)
                            self.logs_tab.log(f"Moved: {item} → {dest_path}", src, dest)
                        except Exception as e:
                            self.logs_tab.log(f"Error with silent move for {item}: {e}")
                            # Fallback to regular move
                            shutil.move(src, dest)
                            self.logs_tab.log(f"Moved (fallback): {item} → {dest_path}", src, dest)
                    else:
                        # Use regular move for non-Windows platforms
                        shutil.move(src, dest)
                        self.logs_tab.log(f"Moved: {item} → {dest_path}", src, dest)
                except Exception as e:
                    self.logs_tab.log(f"Error moving {item}: {e}")

    def reset_settings(self):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        QMessageBox.information(self, "Reset", "Settings reset. Please restart the app.")
        self.close()

    def closeEvent(self, event):
        if self.config.get("exit_on_close", False):
            # Call QMainWindow's closeEvent to properly handle window closing
            super().closeEvent(event)
            # Explicitly terminate the application to ensure no windows remain
            self.close()
        else:
            # Prevent default handling to keep the app running
            event.ignore()
            # Hide main window properly
            self.hide_to_tray()
            # Show notification
            self.show_notification(
                "Auto Organizer",
                "Still running in the background. Right-click tray icon to exit.",
                QSystemTrayIcon.Information,
                3000
            )

    def refresh_version(self):
        """Refresh the version display if version.txt has changed"""
        try:
            current_version = load_version(VERSION_FILE)
            
            # Update about tab version label
            self.about_tab.update_version_display(current_version)
            
            # Update config if version has changed
            if self.config.get("version") != current_version:
                self.config["version"] = current_version
                # Save config to file to persist the version change
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(self.config, f)
        except Exception as e:
            print(f"Error refreshing version: {str(e)}")

    def show_notification(self, title, message, icon=QSystemTrayIcon.Information, duration=2000):
        """Show a system tray notification if enabled"""
        if self.config.get("show_notifications", True):
            self.tray.showMessage(title, message, icon, duration)

    def auto_check_for_updates(self):
        """Automatically check for updates if enabled"""
        if not self.config.get("auto_update_check", True):
            return
            
        try:
            with urllib.request.urlopen("https://api.github.com/repos/EyadElshaer/Auto-Organize/releases/latest") as res:
                data = json.load(res)
                latest_version = data["tag_name"]
                current_version = load_version(VERSION_FILE)
                
                # Compare version numbers semantically
                def parse_version(v):
                    # Remove 'v' prefix if present and split by dots
                    return [int(x) for x in v.lstrip('v').split('.')]
                
                latest_parts = parse_version(latest_version)
                current_parts = parse_version(current_version)
                
                # Pad shorter version with zeros
                while len(latest_parts) < len(current_parts):
                    latest_parts.append(0)
                while len(current_parts) < len(latest_parts):
                    current_parts.append(0)
                
                # Compare version parts
                needs_update = False
                for i in range(len(latest_parts)):
                    if latest_parts[i] > current_parts[i]:
                        needs_update = True
                        break
                    elif latest_parts[i] < current_parts[i]:
                        # Local version is higher than remote
                        break
                
                if needs_update:
                    self.show_notification(
                        "Update Available",
                        f"Version {latest_version} is available! Open the app and go to About tab to update.",
                        QSystemTrayIcon.Information,
                        5000
                    )
        except Exception as e:
            print(f"Auto update check error: {str(e)}")

    def tray_activated(self, reason):
        """Handle system tray icon activation"""
        # QSystemTrayIcon.Trigger = single click, QSystemTrayIcon.DoubleClick = double click
        if reason in [QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick]:
            # If the window is minimized or hidden, restore it
            if self.isMinimized() or not self.isVisible():
                self.restore_window()
            # If it's already visible, bring it to front
            else:
                self.activateWindow()

    def hide_to_tray(self):
        """Properly hide the window to system tray without showing any flash windows"""
        # First set window to be hidden from taskbar
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        self.setVisible(False)  # This is more reliable than hide() for system tray apps

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WatcherApp()
    window.show()
    sys.exit(app.exec_())