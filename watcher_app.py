import sys, os, re, json, urllib.request, platform, subprocess, shutil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu, QAction, QMessageBox
)
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QThread, QObject
from queue import Queue
import time

# Add Python's site-packages to path
import site
for site_path in site.getsitepackages():
    if site_path not in sys.path:
        sys.path.append(site_path)

# Try importing watchdog with detailed error reporting
USE_WATCHDOG = False  # Set default to False
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    USE_WATCHDOG = True  # Only set to True if import succeeds
    print("Successfully imported watchdog")
except ImportError as e:
    print(f"Watchdog import error: {str(e)}")
    print("Python path:", sys.path)
    print("Falling back to polling method")
except Exception as e:
    print(f"Unexpected error importing watchdog: {str(e)}")
    print("Falling back to polling method")

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

def is_valid_filename_format(filename):
    """Check if filename follows the required format with strict tag ordering"""
    try:
        # Skip files that have been undone
        if "(Undo)" in filename:
            return False
            
        # Basic comma check
        if ',' not in filename:
            return False

        # Split by first comma and validate basic structure
        main_folder, name_part = filename.split(',', 1)
        
        # Validate main folder (before comma)
        if not main_folder.strip():
            return False
            
        # Validate name part (after comma)
        name_part = name_part.strip()
        if not name_part:
            return False

        # Get base name (part before any tags)
        base_name = name_part.split('(')[0].split('[')[0].split('-')[0].strip()
        if not base_name:
            return False

        # Check tag ordering
        remainder = name_part[len(base_name):]
        
        # Now check tags in sequence
        has_parentheses = False
        has_brackets = False
        
        # Track positions to ensure correct order
        paren_pos = remainder.find('(')
        bracket_pos = remainder.find('[')
        dash_pos = remainder.find('-')
        
        # If we have brackets, we must have parentheses before them
        if bracket_pos != -1:
            if paren_pos == -1 or paren_pos > bracket_pos:
                return False
                
        # If we have dashes, we must have brackets before them
        if dash_pos != -1:
            if bracket_pos == -1 or bracket_pos > dash_pos:
                return False

        # Validate tag content
        if '(' in remainder:
            # Check all parentheses pairs
            paren_parts = re.findall(r'\(([^)]*)\)', remainder)
            if any(not part.strip() for part in paren_parts):
                return False
            has_parentheses = True

        if '[' in remainder:
            # Must have parentheses before brackets
            if not has_parentheses:
                return False
            # Check all bracket pairs
            bracket_parts = re.findall(r'\[(.*?)\]', remainder)
            if any(not part.strip() for part in bracket_parts):
                return False
            has_brackets = True

        if '-' in remainder:
            # Must have brackets before dashes
            if not has_brackets:
                return False
            # Check all dash pairs
            dash_parts = re.findall(r'-([^-]*)-', remainder)
            if any(not part.strip() for part in dash_parts):
                return False

        return True
        
    except Exception as e:
        print(f"Validation error for {filename}: {str(e)}")
        return False

class FileProcessorWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(str, str, str)
    initial_scan_complete = pyqtSignal()
    
    def __init__(self, queue, batch_size=5, max_file_age_hours=24):
        super().__init__()
        self.queue = queue
        self.batch_size = batch_size
        self.max_file_age_hours = max_file_age_hours
        self.running = True
        self.initial_scan_done = False
        self.processed_files = set()  # Keep track of processed files
        
    def do_initial_scan(self, watch_pairs):
        """Perform initial scan for today's files"""
        try:
            self.progress.emit("Starting initial scan for today's files...", None, None)
            today_start = time.time() - (24 * 3600)  # 24 hours ago
            
            for watch, target in watch_pairs:
                if not self.running:
                    break
                    
                if not watch or not target:
                    continue
                    
                try:
                    items = os.listdir(watch)
                    # Sort items by modification time (newest first)
                    items_with_time = []
                    for item in items:
                        try:
                            src = os.path.join(watch, item)
                            if not os.path.exists(src):
                                continue
                            mtime = os.path.getmtime(src)
                            # Only include files modified today
                            if mtime >= today_start:
                                items_with_time.append((mtime, item, src))
                        except Exception:
                            continue
                    
                    # Sort by modification time, newest first
                    items_with_time.sort(reverse=True)
                    
                    # Process the sorted items
                    for _, item, src in items_with_time:
                        if ',' in item:  # Basic validation before detailed check
                            self.queue.put((item, src, watch, target, None))
                            
                except Exception as e:
                    self.progress.emit(f"Error scanning directory {watch}: {str(e)}", None, None)
                    continue
            
            self.progress.emit("Initial scan complete", None, None)
            self.initial_scan_done = True
            self.initial_scan_complete.emit()
            
        except Exception as e:
            self.progress.emit(f"Error during initial scan: {str(e)}", None, None)
            self.initial_scan_done = True
            self.initial_scan_complete.emit()
        
    def process_files(self):
        while self.running:
            try:
                # Process files in smaller batches
                batch = []
                temp_batch = []
                
                # Collect items from queue
                for _ in range(self.batch_size * 2):
                    if not self.queue.empty():
                        temp_batch.append(self.queue.get())
                    else:
                        break

                if not temp_batch:
                    # No files to process, sleep briefly
                    time.sleep(0.5)
                    continue

                # Sort and filter files by age
                current_time = time.time()
                sorted_batch = []
                
                for item in temp_batch:
                    try:
                        src = item[1]
                        if not os.path.exists(src):
                            continue
                            
                        # Skip if we've already processed this file recently
                        if src in self.processed_files:
                            continue
                            
                        filename = item[0]
                        if ',' not in filename:
                            continue
                            
                        file_mtime = os.path.getmtime(src)
                        file_age_hours = (current_time - file_mtime) / 3600
                        
                        if file_age_hours <= self.max_file_age_hours:
                            sorted_batch.append((file_mtime, item))
                            
                    except Exception:
                        continue

                # Sort by modification time (newest first)
                sorted_batch.sort(key=lambda x: x[0], reverse=True)
                batch = [item[1] for item in sorted_batch[:self.batch_size]]

                for item in batch:
                    if not self.running:
                        break
                    try:
                        if self._process_single_file(*item):
                            # Add to processed files set if successfully processed
                            self.processed_files.add(item[1])
                            
                            # Limit the size of processed_files set
                            if len(self.processed_files) > 1000:
                                self.processed_files.clear()
                    except Exception as e:
                        self.progress.emit(f"Error processing {item[0]}: {str(e)}", None, None)
                    
                    # Small delay between files
                    time.sleep(0.1)
                    
            except Exception as e:
                self.progress.emit(f"Batch processing error: {str(e)}", None, None)
                time.sleep(1)
                
        self.finished.emit()
        
    def _process_single_file(self, item, src, watch, target, startupinfo=None):
        """Returns True if file was processed successfully"""
        try:
            if not os.path.exists(src):
                return False

            if item.startswith('.') or item.startswith('$'):
                return False

            if ',' not in item:
                return False

            main_folder, remainder = item.split(',', 1)
            main_folder = main_folder.strip()
            remainder = remainder.strip()

            if not main_folder or not remainder:
                return False

            if not is_valid_filename_format(item):
                return False

            extension = os.path.splitext(item)[1]
            base_name = remainder.split('(')[0].split('[')[0].split('-')[0].strip()
            
            if not base_name:
                return False

            final_name = base_name if base_name.lower().endswith(extension.lower()) else base_name + extension

            # Extract all tags in order
            subfolders = []
            
            parentheses = re.findall(r"\(([^)]+)\)", remainder)
            if parentheses:
                subfolders.extend(p.strip() for p in parentheses if p.strip())
            
            brackets = re.findall(r"\[(.*?)\]", remainder)
            if brackets:
                if not parentheses:
                    return False
                subfolders.extend(b.strip() for b in brackets if b.strip())
            
            dashes = re.findall(r"-([^-]+)-", remainder)
            if dashes:
                if not brackets:
                    return False
                subfolders.extend(d.strip() for d in dashes if d.strip())

            dest_path = os.path.join(target, main_folder, *subfolders)
            
            try:
                os.makedirs(dest_path, exist_ok=True)
                dest = os.path.join(dest_path, final_name)

                if os.path.exists(dest):
                    return False

                try:
                    if platform.system() == 'Windows' and os.path.isdir(src):
                        cmd = ["robocopy", src, dest, "/E", "/MOVE", "/NFL", "/NDL", "/NJH", "/NJS"]
                        result = subprocess.run(cmd, startupinfo=startupinfo, 
                                             stdout=subprocess.DEVNULL, 
                                             stderr=subprocess.DEVNULL)
                        if result.returncode > 8:
                            raise Exception(f"Robocopy failed with code {result.returncode}")
                    else:
                        shutil.move(src, dest)
                    self.progress.emit(f"Moved: {item} → {dest_path}", src, dest)
                    return True
                except Exception as e:
                    self.progress.emit(f"Error moving file {item}: {str(e)}", None, None)
                    return False
                    
            except Exception as e:
                self.progress.emit(f"Error setting up destination for {item}: {str(e)}", None, None)
                return False
                
        except Exception as e:
            self.progress.emit(f"Error processing {item}: {str(e)}", None, None)
            return False
            
    def stop(self):
        self.running = False

# Only define FileWatcher if watchdog is available
if USE_WATCHDOG:
    class FileWatcher(FileSystemEventHandler):
        """Watches for file system changes and processes files immediately"""
        
        def __init__(self, watch_dir, target_dir, file_queue, logging_signal):
            self.watch_dir = watch_dir
            self.target_dir = target_dir
            self.file_queue = file_queue
            self.logging_signal = logging_signal
            self.observer = Observer()
            self.observer.schedule(self, watch_dir, recursive=False)
            
        def start(self):
            """Start watching the directory"""
            self.observer.start()
            
        def stop(self):
            """Stop watching the directory"""
            self.observer.stop()
            self.observer.join()
            
        def on_created(self, event):
            """Handle file creation events"""
            if event.is_directory:
                return
            self._process_file(event.src_path)
            
        def on_modified(self, event):
            """Handle file modification events"""
            if event.is_directory:
                return
            self._process_file(event.src_path)
            
        def on_moved(self, event):
            """Handle file move/rename events"""
            if event.is_directory:
                return
            self._process_file(event.dest_path)
            
        def _process_file(self, file_path):
            """Process a single file"""
            try:
                # Get just the filename
                filename = os.path.basename(file_path)
                
                # Skip system files and files without commas
                if filename.startswith('.') or filename.startswith('$'):
                    return
                    
                if ',' not in filename:
                    return
                    
                # Basic validation before queueing
                try:
                    prefix, remainder = filename.split(',', 1)
                    if not prefix.strip() or not remainder.strip():
                        return
                except:
                    return
                    
                # Queue the file for processing
                self.file_queue.put((filename, file_path, self.watch_dir, self.target_dir, None))
                
            except Exception as e:
                self.logging_signal.emit(f"Error processing new file {file_path}: {str(e)}", None, None)

class WatcherManager:
    """Manages file watching using either watchdog or polling"""
    
    def __init__(self, file_queue, logging_signal):
        self.watchers = []
        self.file_queue = file_queue
        self.logging_signal = logging_signal
        self.use_watchdog = USE_WATCHDOG
        self.polling_timer = None if USE_WATCHDOG else QTimer()
        self.watch_pairs = []
        
        if not USE_WATCHDOG and self.polling_timer:
            self.polling_timer.timeout.connect(self._poll_directories)
        
    def update_watchers(self, watch_pairs):
        """Update watchers based on current watch pairs"""
        self.watch_pairs = watch_pairs
        
        if self.use_watchdog:
            # Stop existing watchers
            self.stop_all()
            
            # Create new watchers for each pair
            for watch_dir, target_dir in watch_pairs:
                if watch_dir and target_dir:
                    watcher = FileWatcher(watch_dir, target_dir, self.file_queue, self.logging_signal)
                    watcher.start()
                    self.watchers.append(watcher)
        else:
            # Using polling method
            if self.polling_timer and not self.polling_timer.isActive():
                self.polling_timer.start(1000)  # Poll every second
                
    def _poll_directories(self):
        """Poll directories for changes when watchdog is not available"""
        try:
            for watch_dir, target_dir in self.watch_pairs:
                if not (watch_dir and target_dir):
                    continue
                    
                try:
                    files = os.listdir(watch_dir)
                    for filename in files:
                        file_path = os.path.join(watch_dir, filename)
                        
                        # Skip system files and files without commas
                        if filename.startswith('.') or filename.startswith('$'):
                            continue
                            
                        if ',' not in filename:
                            continue
                            
                        # Basic validation before queueing
                        try:
                            prefix, remainder = filename.split(',', 1)
                            if not prefix.strip() or not remainder.strip():
                                continue
                        except:
                            continue
                            
                        # Queue the file for processing
                        self.file_queue.put((filename, file_path, watch_dir, target_dir, None))
                        
                except Exception as e:
                    self.logging_signal.emit(f"Error polling directory {watch_dir}: {str(e)}", None, None)
                    
        except Exception as e:
            self.logging_signal.emit(f"Error during polling: {str(e)}", None, None)
                
    def stop_all(self):
        """Stop all watchers"""
        if self.use_watchdog:
            for watcher in self.watchers:
                watcher.stop()
            self.watchers.clear()
        else:
            if self.polling_timer and self.polling_timer.isActive():
                self.polling_timer.stop()

class WatcherApp(QMainWindow):
    logging_signal = pyqtSignal(str, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Organizer")
        self.setWindowIcon(safe_icon("icon.ico"))
        self.setGeometry(100, 100, 750, 500)
        
        # Set proper window flags to show all buttons
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        
        # Initialize tray menu actions first
        self.enable_action = QAction("Enable Watching", self)
        self.disable_action = QAction("Disable Watching", self)
        self.open_action = QAction("Open", self)
        self.exit_action = QAction("Exit", self)
        
        # Connect actions
        self.enable_action.triggered.connect(self.enable_watching)
        self.disable_action.triggered.connect(self.disable_watching)
        self.open_action.triggered.connect(self.restore_window)
        self.exit_action.triggered.connect(QApplication.quit)

        # Initialize state variables and load config
        self.watching = False
        self.load_config()

        # Setup system tray BEFORE any other initialization that might use it
        self.setup_tray()
        
        # Initialize file processing queue and worker
        self.file_queue = Queue()
        self.worker_thread = QThread()
        max_age = self.config.get("max_file_age_hours", 24)
        self.file_processor = FileProcessorWorker(self.file_queue, max_file_age_hours=max_age)
        self.file_processor.moveToThread(self.worker_thread)
        self.file_processor.progress.connect(self.safe_log)
        self.worker_thread.started.connect(self.file_processor.process_files)
        self.file_processor.finished.connect(self.worker_thread.quit)
        
        # Initialize watcher manager before any potential usage
        self.watcher_manager = WatcherManager(self.file_queue, self.logging_signal)
        
        # Initialize tabs and UI
        self.init_tabs()
        
        # Connect the logging signal to the logs tab
        self.logging_signal.connect(self.safe_log)
        
        # Setup timers
        self.setup_timers()
        
        # Connect initial scan complete signal
        self.file_processor.initial_scan_complete.connect(self.on_initial_scan_complete)
        
        # Start the worker thread
        self.worker_thread.start()
        
        # Perform initial scan
        pairs = self.main_tab.get_watch_pairs()
        if pairs:
            QTimer.singleShot(1000, lambda: self.file_processor.do_initial_scan(pairs))
            self.logging_signal.emit("Starting initial scan for today's files...", None, None)
        
        # Apply theme (must be done after UI initialization)
        self.apply_theme(self.config.get("theme", "System Default"))
        
        # Auto-hide if configured
        if self.config.get("minimize_on_startup", False):
            self.hide_to_tray()
        
        # Start watching if start on launch is enabled
        if self.config.get("start_on_launch", False):
            QTimer.singleShot(1000, lambda: self.handle_start_on_launch(True))

    def on_initial_scan_complete(self):
        """Handle completion of initial scan"""
        self.logging_signal.emit("Initial scan complete - ready to watch for new files", None, None)
        # Start watching if auto-watch is enabled
        if self.config.get("auto_watch", True):
            self.enable_watching()

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
        self.tray_menu.addAction(self.enable_action)
        self.tray_menu.addAction(self.disable_action)
        
        # Add other actions
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
        self.watcher_manager.update_watchers(pairs)  # Start real-time watchers
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
        self.watcher_manager.stop_all()  # Stop all watchers
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
            self.watcher_manager.update_watchers(pairs)  # Start real-time watchers
            self.main_tab.toggle_btn.setText("Stop")
            self.main_tab.status.setText("Status: Watching...")
        else:
            self.watching = False
            self.watcher_manager.stop_all()  # Stop all watchers
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
        
        # Setup auto-update check timer (hourly = 3600000 ms)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.auto_check_for_updates)
        if self.config.get("auto_update_check", True):
            self.update_timer.start(3600000)  # Check every hour

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
        self.settings_tab.theme_changed.connect(self.apply_theme)
        self.settings_tab.start_on_launch_changed.connect(self.handle_start_on_launch)
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

        if theme == "windows xp":
            app.setStyle("WindowsXP")  # Set Windows XP style
            # Classic Windows XP colors
            palette.setColor(QPalette.Window, QColor(236, 233, 216))  # XP window color
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Base, Qt.white)
            palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
            palette.setColor(QPalette.ToolTipBase, QColor(236, 233, 216))
            palette.setColor(QPalette.ToolTipText, Qt.black)
            palette.setColor(QPalette.Text, Qt.black)
            palette.setColor(QPalette.Button, QColor(236, 233, 216))
            palette.setColor(QPalette.ButtonText, Qt.black)
            palette.setColor(QPalette.BrightText, Qt.white)
            palette.setColor(QPalette.Highlight, QColor(49, 106, 197))  # XP blue
            palette.setColor(QPalette.HighlightedText, Qt.white)
            palette.setColor(QPalette.Link, QColor(0, 0, 255))
        elif theme == "dark":
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

    def handle_start_on_launch(self, enabled):
        """Handle the start on launch setting change"""
        import winreg
        startup_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        try:
            # Get the actual executable path
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                exe_path = sys.executable
            else:
                # Running as script
                exe_path = os.path.abspath(sys.argv[0])
                
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup_key, 0, winreg.KEY_ALL_ACCESS) as key:
                if enabled:
                    # Add to startup with proper quoting and arguments
                    startup_command = f'"{exe_path}" --minimized'
                    winreg.SetValueEx(key, "Auto Organizer", 0, winreg.REG_SZ, startup_command)
                    self.logging_signal.emit("Added Auto Organizer to startup programs", None, None)
                else:
                    # Remove from startup
                    try:
                        winreg.DeleteValue(key, "Auto Organizer")
                        self.logging_signal.emit("Removed Auto Organizer from startup programs", None, None)
                    except FileNotFoundError:
                        # Key doesn't exist, which is fine when disabling
                        pass
        except Exception as e:
            self.logging_signal.emit(f"Failed to modify startup settings: {str(e)}", None, None)
        
        # Only start watching if setting was just enabled
        if enabled and not self.watching:
            pairs = self.main_tab.get_watch_pairs()
            if pairs:
                self.watching = True
                self.watcher_manager.update_watchers(pairs)
                self.main_tab.toggle_btn.setText("Stop")
                self.main_tab.status.setText("Status: Watching...")
                self.update_tray_menu()
                self.show_notification(
                    "Auto Start",
                    "Auto Organizer is now watching folders",
                    QSystemTrayIcon.Information,
                    2000
                )

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
            # Start or restart the update timer with hourly checks
            self.update_timer.start(3600000)  # 1 hour
        else:
            # Stop the timer if auto-update is disabled
            self.update_timer.stop()

        # Update worker with new max age setting if it changed
        new_max_age = self.config.get("max_file_age_hours", 24)
        if hasattr(self, 'file_processor'):
            self.file_processor.max_file_age_hours = new_max_age
            
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
        self.config.setdefault("start_on_launch", False)

    def scan_all_pairs(self):
        """Scan all watch pairs for files to organize"""
        import shutil
        import subprocess
        
        def process_pair(watch, target):
            if not watch or not target:
                self.logging_signal.emit("Invalid watch/target pair", None, None)
                return

            try:
                # Validate directories
                if not os.path.isdir(watch) or not os.path.isdir(target):
                    self.logging_signal.emit(f"Invalid directory pair: {watch} -> {target}", None, None)
                    return

                # Set startupinfo to hide command window on Windows
                startupinfo = None
                if platform.system() == 'Windows':
                    try:
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = 0  # SW_HIDE
                    except Exception as e:
                        self.logging_signal.emit(f"Error setting up subprocess: {str(e)}", None, None)

                try:
                    # Get all items in directory
                    items = os.listdir(watch)
                except Exception as e:
                    self.logging_signal.emit(f"Error scanning directory {watch}: {str(e)}", None, None)
                    return

                # First do a pre-check of all files
                valid_items = []
                for item in items:
                    src = os.path.join(watch, item)
                    
                    # Skip if file doesn't exist or is system/hidden file
                    if not os.path.exists(src) or item.startswith('.') or item.startswith('$'):
                        continue

                    # Do basic comma validation before queueing
                    if ',' not in item:
                        self.logging_signal.emit(f"Not processing - no comma in filename: {item}", None, None)
                        continue
                        
                    # Split and check parts
                    try:
                        prefix, remainder = item.split(',', 1)
                        if not prefix.strip() or not remainder.strip():
                            self.logging_signal.emit(f"Not processing - invalid format: {item}", None, None)
                            continue
                    except:
                        self.logging_signal.emit(f"Not processing - invalid split: {item}", None, None)
                        continue

                    valid_items.append((item, src))

                # Then queue valid items
                for item, src in valid_items:
                    try:
                        # Double check file still exists before queueing
                        if os.path.exists(src):
                            self.file_queue.put((item, src, watch, target, startupinfo))
                    except Exception as e:
                        self.logging_signal.emit(f"Error queueing {item}: {str(e)}", None, None)

            except Exception as e:
                self.logging_signal.emit(f"Error in process_pair: {str(e)}", None, None)

        try:
            pairs = self.main_tab.get_watch_pairs()
            if not pairs:
                self.logging_signal.emit("No watch pairs configured", None, None)
                return

            # Process each pair
            for watch, target in pairs:
                if watch and target:
                    process_pair(watch, target)

        except Exception as e:
            self.logging_signal.emit(f"Error in scan_all_pairs: {str(e)}", None, None)

    def reset_settings(self):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        QMessageBox.information(self, "Reset", "Settings reset. Please restart the app.")
        self.close()

    def closeEvent(self, event):
        # Stop all watchers before closing
        self.watcher_manager.stop_all()
        
        # Stop the file processor
        if hasattr(self, 'file_processor'):
            self.file_processor.stop()
            self.worker_thread.quit()
            self.worker_thread.wait()
            
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
                    # Show popup window instead of notification
                    msg = QMessageBox()
                    msg.setWindowTitle("Update Available")
                    msg.setWindowIcon(self.windowIcon())
                    msg.setIcon(QMessageBox.Information)
                    msg.setText(f"A new version {latest_version} is available!")
                    msg.setInformativeText("Would you like to update now?")
                    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    msg.setDefaultButton(QMessageBox.Yes)
                    
                    if msg.exec_() == QMessageBox.Yes:
                        # Open the About tab which has the update button
                        self.tabs.setCurrentWidget(self.about_tab)
                        self.restore_window()  # Make sure window is visible
                
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

    def safe_log(self, message, src=None, dest=None):
        """Thread-safe logging method"""
        self.logs_tab.log(message, src, dest)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WatcherApp()
    window.show()
    sys.exit(app.exec_())