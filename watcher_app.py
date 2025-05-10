import sys, os, re, json, urllib.request, platform, subprocess, shutil, traceback
import socket
import tempfile
import ctypes
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu, QAction, QMessageBox
)
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QThread, QObject
from queue import Queue
import time

# Handle winreg import with better error handling
try:
    import winreg
except ImportError:
    print("Warning: winreg module not available")
    # Create a dummy winreg module with empty functions
    class DummyWinreg:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    winreg = DummyWinreg()

# Add Python's site-packages to path
import site
for site_path in site.getsitepackages():
    if site_path not in sys.path:
        sys.path.append(site_path)

# Try importing watchdog with detailed error reporting and better fallback
USE_WATCHDOG = False  # Set default to False
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    # Test that Observer can actually be instantiated
    test_observer = Observer()
    USE_WATCHDOG = True  # Only set to True if import and instantiation succeed
    print("Successfully imported and tested watchdog")
except ImportError as e:
    print(f"Watchdog import error: {str(e)}")
    print("Python path:", sys.path)
    print("Falling back to polling method")
except Exception as e:
    print(f"Unexpected error importing watchdog: {str(e)}")
    print(f"Error details: {traceback.format_exc()}")
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
        print(f"Using PyInstaller base path: {base_path}")
    except Exception:
        base_path = os.path.abspath(".")
        print(f"Using development base path: {base_path}")

    full_path = os.path.join(base_path, relative_path)
    print(f"Loading resource from: {full_path}")
    return full_path

def safe_icon(icon_path):
    """Create a QIcon object with fallback to empty icon if file doesn't exist"""
    path = get_resource_path(icon_path)
    if os.path.exists(path):
        print(f"Found icon: {path}")
        return QIcon(path)

    # Try looking in the icons subdirectory
    icons_path = get_resource_path(os.path.join("icons", os.path.basename(icon_path)))
    if os.path.exists(icons_path):
        print(f"Found icon in icons directory: {icons_path}")
        return QIcon(icons_path)

    # If icon doesn't exist but icon.ico does, use that instead
    ico_path = get_resource_path("icons/icon.ico")
    if os.path.exists(ico_path):
        print(f"Using fallback icon: {ico_path} for {icon_path}")
        return QIcon(ico_path)

    # Last resort - empty icon
    print(f"WARNING: No icon found for {icon_path}")
    return QIcon()

def set_window_title_bar_theme(hwnd, is_dark):
    """Set the window title bar theme to dark or light mode using Windows DWM API"""
    if platform.system() != 'Windows':
        return False

    try:
        # Define constants for Windows DWM API
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20

        # Get the DWM API
        dwmapi = ctypes.windll.dwmapi

        # Prepare the value to set (0 for light mode, 1 for dark mode)
        value = ctypes.c_int(1 if is_dark else 0)

        # Set the window attribute
        result = dwmapi.DwmSetWindowAttribute(
            hwnd,                          # Window handle
            DWMWA_USE_IMMERSIVE_DARK_MODE, # Attribute to set
            ctypes.byref(value),           # Pointer to the value
            ctypes.sizeof(value)           # Size of the value
        )

        return result == 0  # 0 means success
    except Exception as e:
        print(f"Error setting window title bar theme: {str(e)}")
        return False

def get_windows_system_theme():
    """Get Windows system theme with better error handling for Windows 10/11 compatibility"""
    try:
        # Try Windows 10/11 registry path first
        reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        key = winreg.OpenKey(reg, key_path)
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value == 1 else "dark"
    except FileNotFoundError:
        # Registry key not found - might be older Windows version
        print("Windows theme registry key not found")
        return "light"
    except PermissionError:
        # No permission to access registry
        print("Permission denied accessing Windows theme registry")
        return "light"
    except Exception as e:
        # Any other error
        print(f"Error detecting Windows theme: {str(e)}")
        return "light"

def is_valid_filename_format(filename):
    """
    Validates if a filename follows the required format.
    Format: prefix, rest_of_filename
    The prefix will be used as the main folder name.

    This improved version better handles special characters in filenames.
    """
    try:
        # Skip files that have been undone
        if "(Undo)" in filename:
            print(f"Skipping undo file: {filename}")
            return False

        # Basic comma check - must have at least one comma
        if ',' not in filename:
            print(f"No comma found in filename: {filename}")
            return False

        # Split by first comma
        main_folder, name_part = filename.split(',', 1)

        # Validate main folder (before comma)
        main_folder = main_folder.strip()
        if not main_folder:
            print(f"Empty prefix before comma in filename: {filename}")
            return False

        # Validate name part (after comma)
        name_part = name_part.strip()
        if not name_part:
            print(f"Empty name after comma in filename: {filename}")
            return False

        # Check for balanced parentheses, brackets, and other special characters
        # This is just a basic check to ensure the file can be processed
        paren_count = 0
        bracket_count = 0

        for char in name_part:
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
                # Allow for closing parenthesis without opening (just a warning)
                if paren_count < -1:
                    print(f"Warning: Unbalanced parentheses in filename: {filename}")
            elif char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                # Allow for closing bracket without opening (just a warning)
                if bracket_count < -1:
                    print(f"Warning: Unbalanced brackets in filename: {filename}")

        # Even with unbalanced characters, we'll still try to process the file
        # Just log warnings for potential issues
        if paren_count > 0:
            print(f"Warning: Unclosed parentheses in filename: {filename}")
        if bracket_count > 0:
            print(f"Warning: Unclosed brackets in filename: {filename}")

        # As long as we have a valid prefix and name, consider it valid
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

    def _process_single_file(self, item, src, watch_dir, target, startupinfo=None):
        """Returns True if file was processed successfully"""
        try:
            # Verify file still exists
            if not os.path.exists(src):
                self.progress.emit(f"File no longer exists: {src}", None, None)
                return False

            # Skip system files
            if item.startswith('.') or item.startswith('$'):
                return False

            # Basic validation
            if ',' not in item:
                return False

            # Parse filename
            main_folder, remainder = item.split(',', 1)
            main_folder = main_folder.strip()
            remainder = remainder.strip()

            if not main_folder or not remainder:
                return False

            if not is_valid_filename_format(item):
                return False

            # Get file extension and base name
            extension = os.path.splitext(item)[1]

            # Improved base name extraction that handles special characters better
            # First, find the position of the first special character marker
            first_special_pos = len(remainder)

            # Check for parentheses
            paren_pos = remainder.find('(')
            if paren_pos > 0 and paren_pos < first_special_pos:
                first_special_pos = paren_pos

            # Check for brackets
            bracket_pos = remainder.find('[')
            if bracket_pos > 0 and bracket_pos < first_special_pos:
                first_special_pos = bracket_pos

            # Check for dash with space before it
            dash_pos = remainder.find(' - ')
            if dash_pos > 0 and dash_pos < first_special_pos:
                first_special_pos = dash_pos

            # Check for single dash (only if not part of the filename)
            if dash_pos < 0:  # Only if we didn't find a dash with spaces
                dash_pos = remainder.find('-')
                # Make sure this isn't a dash that's part of the filename
                if dash_pos > 0 and dash_pos < first_special_pos:
                    # Check if there's a word boundary before the dash
                    if dash_pos > 0 and remainder[dash_pos-1].isspace():
                        first_special_pos = dash_pos

            # Extract base name up to the first special character
            base_name = remainder[:first_special_pos].strip()

            # If no special characters were found, use the entire remainder
            if not base_name:
                # Handle case where the entire remainder might be the base name
                # Remove any trailing dashes that might cause issues
                base_name = remainder.strip().rstrip('-').strip()

            if not base_name:
                return False

            # Clean up the base name - remove any trailing dashes
            base_name = base_name.rstrip('-').strip()

            # Log the base name for debugging
            self.progress.emit(f"Base name extracted: {base_name}", None, None)

            # Ensure extension is preserved
            final_name = base_name if base_name.lower().endswith(extension.lower()) else base_name + extension

            # Extract all tags in order
            subfolders = []

            # Process tags in parentheses - improved pattern to handle nested parentheses
            try:
                # Find all content within parentheses
                paren_depth = 0
                start_pos = -1
                paren_tags = []

                for i, char in enumerate(remainder):
                    if char == '(':
                        paren_depth += 1
                        if paren_depth == 1:
                            start_pos = i + 1  # Start after the opening parenthesis
                    elif char == ')':
                        paren_depth -= 1
                        if paren_depth == 0 and start_pos != -1:
                            # Extract content between parentheses
                            tag = remainder[start_pos:i].strip()
                            if tag:
                                paren_tags.append(tag)
                            start_pos = -1

                # Add parentheses tags to subfolders
                subfolders.extend(paren_tags)
            except Exception as e:
                self.progress.emit(f"Error processing parentheses in {item}: {str(e)}", None, None)

            # Process tags in brackets - improved pattern
            try:
                # Find all content within brackets
                bracket_depth = 0
                start_pos = -1
                bracket_tags = []

                for i, char in enumerate(remainder):
                    if char == '[':
                        bracket_depth += 1
                        if bracket_depth == 1:
                            start_pos = i + 1  # Start after the opening bracket
                    elif char == ']':
                        bracket_depth -= 1
                        if bracket_depth == 0 and start_pos != -1:
                            # Extract content between brackets
                            tag = remainder[start_pos:i].strip()
                            if tag:
                                bracket_tags.append(tag)
                            start_pos = -1

                # Add bracket tags to subfolders
                subfolders.extend(bracket_tags)
            except Exception as e:
                self.progress.emit(f"Error processing brackets in {item}: {str(e)}", None, None)

            # Process tags in dashes - improved pattern to handle dash-separated tags
            try:
                # First try to find patterns with spaces around dashes like " - tag - "
                dash_pattern = re.findall(r' - ([^-]+?)(?= - |$)', remainder)

                # If that doesn't work, try a more lenient pattern for single dashes
                if not dash_pattern:
                    # Check if there are any dashes in the remainder
                    if '-' in remainder:
                        # Split by single dash and filter out empty parts
                        parts = [p.strip() for p in remainder.split('-') if p.strip()]
                        # Skip the first part (it's likely part of the filename)
                        if len(parts) > 1:
                            # Don't include the last part if it's empty or just the file extension
                            dash_pattern = []
                            for part in parts[1:]:
                                # Check if this part is just a file extension
                                if part.startswith('.') and len(part) <= 5:
                                    continue
                                # Check if this is an empty part at the end (from trailing dash)
                                if not part:
                                    continue
                                dash_pattern.append(part)

                if dash_pattern:
                    # Additional check to filter out file extensions
                    filtered_tags = []
                    for tag in dash_pattern:
                        # Skip if it's just a file extension (starts with . and is short)
                        if tag.startswith('.') and len(tag) <= 5:
                            continue
                        # Skip if it's empty (could happen with trailing dash)
                        if not tag:
                            continue
                        filtered_tags.append(tag)

                    subfolders.extend(filtered_tags)

                    # Debug log for dash pattern processing
                    self.progress.emit(f"Dash pattern extracted: {filtered_tags}", None, None)
            except Exception as e:
                self.progress.emit(f"Error processing dashes in {item}: {str(e)}", None, None)

            # Debug log for troubleshooting
            self.progress.emit(f"Processing: {item} with subfolders: {subfolders}", None, None)

            # Create destination path
            dest_path = os.path.join(target, main_folder, *subfolders)

            try:
                # Create destination directory with better error handling
                try:
                    os.makedirs(dest_path, exist_ok=True)
                except PermissionError:
                    self.progress.emit(f"Permission denied creating directory: {dest_path}", None, None)
                    return False
                except Exception as dir_error:
                    self.progress.emit(f"Error creating directory {dest_path}: {str(dir_error)}", None, None)
                    return False

                # Full destination path
                dest = os.path.join(dest_path, final_name)

                # Skip if destination already exists
                if os.path.exists(dest):
                    self.progress.emit(f"Destination already exists: {dest}", None, None)
                    return False

                # Move the file
                try:
                    if platform.system() == 'Windows' and os.path.isdir(src):
                        # Use robocopy for directories on Windows with better error handling
                        try:
                            # Create startupinfo if not provided
                            if startupinfo is None:
                                startupinfo = subprocess.STARTUPINFO()
                                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                                startupinfo.wShowWindow = 0  # SW_HIDE

                            # Log the move operation
                            self.progress.emit(f"Moving directory: {src} to {dest}", None, None)

                            cmd = ["robocopy", src, dest, "/E", "/MOVE", "/NFL", "/NDL", "/NJH", "/NJS", "/R:2", "/W:2"]
                            result = subprocess.run(cmd,
                                                 startupinfo=startupinfo,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE,
                                                 timeout=60)  # Add timeout

                            # Robocopy has special return codes, anything <= 8 is success
                            if result.returncode > 8:
                                error_output = result.stderr.decode('utf-8', errors='replace')
                                raise Exception(f"Robocopy failed with code {result.returncode}: {error_output}")
                        except subprocess.TimeoutExpired:
                            self.progress.emit(f"Timeout while moving directory {item}", None, None)
                            return False
                        except FileNotFoundError:
                            # Fallback if robocopy is not available
                            self.progress.emit("Robocopy not found, falling back to shutil", None, None)
                            shutil.move(src, dest)
                    else:
                        # Use shutil for files or non-Windows platforms
                        self.progress.emit(f"Moving file: {src} to {dest}", None, None)
                        shutil.move(src, dest)

                    self.progress.emit(f"Moved: {item} → {dest_path}", src, dest)
                    return True

                except PermissionError:
                    self.progress.emit(f"Permission denied moving {item}", None, None)
                    return False
                except FileNotFoundError:
                    self.progress.emit(f"File disappeared during move: {item}", None, None)
                    return False
                except Exception as move_error:
                    self.progress.emit(f"Error moving file {item}: {str(move_error)}", None, None)
                    print(f"Move error details: {traceback.format_exc()}")
                    return False

            except Exception as e:
                self.progress.emit(f"Error setting up destination for {item}: {str(e)}", None, None)
                return False

        except Exception as e:
            self.progress.emit(f"Error processing {item}: {str(e)}", None, None)
            print(f"Error details for {item}: {traceback.format_exc()}")
            return False

    def stop(self):
        self.running = False

# Only define FileWatcher if watchdog is available
if USE_WATCHDOG:
    class FileWatcher(FileSystemEventHandler):
        """Watches for file system changes and processes files immediately"""

        def __init__(self, watch_dir, target_dir, file_queue, logging_signal):
            super().__init__()  # Add super() call to properly initialize FileSystemEventHandler
            self.watch_dir = watch_dir
            self.target_dir = target_dir
            self.file_queue = file_queue
            self.logging_signal = logging_signal
            self.observer = Observer()
            self.observer.schedule(self, watch_dir, recursive=False)
            self.processed_files = set()  # Track processed files to avoid duplicates

        def start(self):
            """Start watching the directory"""
            if not self.observer.is_alive():
                self.observer.start()
                self.logging_signal.emit(f"Started watching {self.watch_dir}", None, None)

        def stop(self):
            """Stop watching the directory"""
            if self.observer.is_alive():
                self.observer.stop()
                self.observer.join()
                self.logging_signal.emit(f"Stopped watching {self.watch_dir}", None, None)

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
            # Process the destination path since that's where the file ended up
            self._process_file(event.dest_path)

        def _process_file(self, file_path):
            """Process a single file"""
            try:
                # Get just the filename
                filename = os.path.basename(file_path)

                # Create a unique identifier for this file event
                file_id = f"{filename}_{os.path.getmtime(file_path)}"

                # Skip if we've already processed this exact file event
                if file_id in self.processed_files:
                    return

                # Skip system files and files without commas
                if filename.startswith('.') or filename.startswith('$'):
                    self.logging_signal.emit(f"Skipping system file: {filename}", None, None)
                    return

                if ',' not in filename:
                    self.logging_signal.emit(f"Skipping file without comma: {filename}", None, None)
                    return

                # Basic validation before queueing
                try:
                    prefix, remainder = filename.split(',', 1)
                    prefix = prefix.strip()
                    remainder = remainder.strip()
                    if not prefix or not remainder:
                        self.logging_signal.emit(f"Skipping file - invalid format (empty prefix or name): {filename}", None, None)
                        return
                except:
                    self.logging_signal.emit(f"Skipping file - error splitting filename: {filename}", None, None)
                    return

                # Add to processed files set to avoid duplicates
                self.processed_files.add(file_id)

                # Limit the size of processed_files set
                if len(self.processed_files) > 1000:
                    self.processed_files.clear()

                # Queue the file for processing
                if os.path.exists(file_path):  # Double check file still exists
                    self.logging_signal.emit(f"Detected new file: {filename}", None, None)
                    self.file_queue.put((filename, file_path, self.watch_dir, self.target_dir, None))

            except Exception as e:
                self.logging_signal.emit(f"Error processing file {file_path}: {str(e)}", None, None)

        def __del__(self):
            """Ensure observer is stopped when the watcher is destroyed"""
            try:
                if hasattr(self, 'observer'):
                    self.stop()
            except:
                pass

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

    # Create a signal for instance activation
    instance_activation_signal = pyqtSignal()

    def __init__(self, instance_checker=None):
        super().__init__()
        self.setWindowTitle("Auto Organizer")
        self.setWindowIcon(safe_icon("icons/icon.ico"))  # Updated path
        self.setGeometry(100, 100, 800, 550)  # Slightly larger window

        # Create status bar
        self.statusBar().showMessage("Ready", 3000)

        # Store the instance checker reference
        self.instance_checker = instance_checker

        # Connect instance activation signal
        self.instance_activation_signal.connect(self.restore_window)

        # If we have an instance checker, connect its activation method
        if self.instance_checker:
            # Monkey patch the instance checker's _activate_window method
            original_activate = self.instance_checker._activate_window

            def new_activate_window():
                try:
                    # Emit our signal to activate the window from the main thread
                    self.instance_activation_signal.emit()
                    # Still call the original method for any cleanup it might do
                    original_activate()
                except Exception as e:
                    print(f"Error in activate_window: {str(e)}")

            # Replace the method
            self.instance_checker._activate_window = new_activate_window

        # Register application with Windows
        self.register_application()

        # Set proper window flags to show all buttons
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)

        # Initialize instance variables
        self.tray = None
        self.tray_menu = None
        self.enable_action = None
        self.disable_action = None
        self.open_action = None
        self.exit_action = None
        self.watching = False

        # Load config first as other initializations may need it
        self.load_config()

        # Initialize system tray immediately and ensure it's created
        self.setup_tray()
        if not self.tray or not self.tray.isSystemTrayAvailable():
            print("Warning: System tray is not available")

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

        # Make sure theme is applied when window is shown
        def custom_show_event(event):
            self.apply_theme(self.config.get("theme", "System Default"))
            # Call the original event handler
            super(WatcherApp, self).showEvent(event)

        self.showEvent = custom_show_event

        # Auto-hide if configured
        if self.config.get("minimize_on_startup", False):
            QTimer.singleShot(0, self.hide_to_tray)

        # Start watching if start on launch is enabled
        if self.config.get("start_on_launch", False):
            QTimer.singleShot(1000, lambda: self.handle_start_on_launch(True))

    def register_application(self):
        """Register the application with Windows with better error handling for Windows 10/11"""
        try:
            # Get the actual executable path
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(sys.argv[0])

            # Try to register in HKEY_CURRENT_USER first (doesn't require admin privileges)
            self._register_in_hkcu(exe_path)

            # Only try HKEY_LOCAL_MACHINE if we're running with admin privileges
            # This will fail on most systems without admin rights, which is expected
            try:
                self._register_in_hklm(exe_path)
            except PermissionError:
                # This is expected if not running as admin - just log it
                print("Note: Application registration in HKLM requires admin privileges")
            except Exception as e:
                print(f"HKLM registration failed: {str(e)}")

        except Exception as e:
            print(f"Failed to register application: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            # Non-critical error, application will still work

    def _register_in_hkcu(self, exe_path):
        """Register application in HKEY_CURRENT_USER (doesn't require admin privileges)"""
        try:
            # Register in user's classes
            app_path_key = r"Software\Classes\Applications\AutoOrganizer.exe"
            try:
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, app_path_key, 0, winreg.KEY_WRITE) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Auto Organizer")

                    # Add application info
                    with winreg.CreateKeyEx(key, "shell\\open\\command", 0, winreg.KEY_WRITE) as cmd_key:
                        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

                    # Add application icon
                    with winreg.CreateKeyEx(key, "DefaultIcon", 0, winreg.KEY_WRITE) as icon_key:
                        icon_path = os.path.join(os.path.dirname(exe_path), "icons", "icon.ico")
                        if os.path.exists(icon_path):
                            winreg.SetValueEx(icon_key, "", 0, winreg.REG_SZ, icon_path)
                        else:
                            winreg.SetValueEx(icon_key, "", 0, winreg.REG_SZ, exe_path + ",0")

                print("Successfully registered application in HKCU")
            except Exception as e:
                print(f"Failed to register application in HKCU: {str(e)}")

        except Exception as e:
            print(f"Error in HKCU registration: {str(e)}")

    def _register_in_hklm(self, exe_path):
        """Register application in HKEY_LOCAL_MACHINE (requires admin privileges)"""
        # Register Application Capabilities
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\AppRegistration\Applications\AutoOrganizer.Application"
        try:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
                winreg.SetValueEx(key, "ExecutablePath", 0, winreg.REG_SZ, exe_path)
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Auto Organizer")
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Eyad Elshaer")
                winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, "1.0.3.0")
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, os.path.dirname(exe_path))
            print("Successfully registered application capabilities in HKLM")
        except Exception as e:
            print(f"Failed to register application capabilities in HKLM: {str(e)}")
            raise

        # Register ProgID
        progid_path = r"SOFTWARE\Classes\AutoOrganizer.Application.1"
        try:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, progid_path, 0, winreg.KEY_ALL_ACCESS) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Auto Organizer")
                winreg.SetValueEx(key, "FriendlyTypeName", 0, winreg.REG_SZ, "Auto Organizer")

                # Register Application ID
                with winreg.CreateKeyEx(key, "CLSID", 0, winreg.KEY_ALL_ACCESS) as clsid_key:
                    winreg.SetValueEx(clsid_key, "", 0, winreg.REG_SZ, "{F7A76D84-5448-4E79-8F1B-EC8768B9610D}")
            print("Successfully registered ProgID in HKLM")
        except Exception as e:
            print(f"Failed to register ProgID in HKLM: {str(e)}")
            raise

    def on_initial_scan_complete(self):
        """Handle completion of initial scan"""
        self.logging_signal.emit("Initial scan complete - ready to watch for new files", None, None)
        # Start watching if auto-watch is enabled
        if self.config.get("auto_watch", True):
            self.enable_watching()

    def setup_tray(self):
        """Setup the system tray icon and menu with better error handling"""
        try:
            # Check if system tray is supported
            if not QSystemTrayIcon.isSystemTrayAvailable():
                print("System tray is not available on this system")
                self.logging_signal.emit("System tray is not available on this system. Some features may be limited.", None, None)
                return False

            # Create tray icon if it doesn't exist
            if self.tray is None:
                self.tray = QSystemTrayIcon(self)

            # Set the icon with better error handling
            try:
                icon = safe_icon("icons/icon.ico")
                self.tray.setIcon(icon)
                self.tray.setToolTip("Auto Organizer")
            except Exception as icon_error:
                print(f"Error setting tray icon: {str(icon_error)}")
                # Try with a fallback empty icon
                self.tray.setIcon(QIcon())
                self.tray.setToolTip("Auto Organizer (Icon Error)")

            # Create actions if they don't exist
            if self.enable_action is None:
                self.enable_action = QAction("Enable Watching", self)
                self.enable_action.triggered.connect(self.enable_watching)

            if self.disable_action is None:
                self.disable_action = QAction("Disable Watching", self)
                self.disable_action.triggered.connect(self.disable_watching)

            if self.open_action is None:
                self.open_action = QAction("Open", self)
                self.open_action.triggered.connect(self.restore_window)

            if self.exit_action is None:
                self.exit_action = QAction("Exit", self)
                self.exit_action.triggered.connect(QApplication.quit)

            # Create and set up menu
            self.tray_menu = QMenu()
            self.tray_menu.addAction(self.enable_action)
            self.tray_menu.addAction(self.disable_action)
            self.tray_menu.addSeparator()
            self.tray_menu.addAction(self.open_action)
            self.tray_menu.addAction(self.exit_action)

            # Set initial state
            self.update_tray_menu()

            # Set the context menu with error handling
            try:
                self.tray.setContextMenu(self.tray_menu)
            except Exception as menu_error:
                print(f"Error setting tray context menu: {str(menu_error)}")
                self.logging_signal.emit("Error setting up system tray menu. Right-click functionality may be limited.", None, None)

            # Connect activation signal with error handling
            try:
                self.tray.activated.connect(self.tray_activated)
            except Exception as signal_error:
                print(f"Error connecting tray activation signal: {str(signal_error)}")

            # Show the tray icon
            try:
                self.tray.show()
            except Exception as show_error:
                print(f"Error showing tray icon: {str(show_error)}")
                self.logging_signal.emit("Error showing system tray icon. The application will still run normally.", None, None)
                return False

            return True

        except Exception as e:
            print(f"Error setting up system tray: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            self.logging_signal.emit("Failed to set up system tray. The application will still run normally.", None, None)
            return False

    def update_tray_menu(self):
        """Update the tray menu based on watching state"""
        try:
            if self.tray is None or not self.tray.isSystemTrayAvailable():
                return

            if self.watching:
                if self.enable_action:
                    self.enable_action.setVisible(False)
                if self.disable_action:
                    self.disable_action.setVisible(True)
                self.tray.setToolTip("Auto Organizer (Watching)")
            else:
                if self.enable_action:
                    self.enable_action.setVisible(True)
                if self.disable_action:
                    self.disable_action.setVisible(False)
                self.tray.setToolTip("Auto Organizer (Stopped)")
        except Exception as e:
            print(f"Error updating tray menu: {str(e)}")

    def enable_watching(self):
        """Enable watching from tray menu"""
        pairs = self.main_tab.get_watch_pairs()
        if not pairs:
            self.main_tab.status.setText("Add at least one watcher pair ❗")
            self.main_tab.update_status_style()
            self.show_notification(
                "Error",
                "Add at least one watcher pair first.",
                QSystemTrayIcon.Warning,
                3000
            )
            return

        self.watching = True
        self.watcher_manager.update_watchers(pairs)  # Start real-time watchers

        # Start the timer for regular scanning (every 5 seconds)
        self.timer.start(5000)

        # Do an immediate scan
        self.scan_all_pairs()

        self.main_tab.toggle_btn.setText("Stop Watching")
        self.main_tab.toggle_btn.setIcon(safe_icon("icons/stop.png") if os.path.exists(get_resource_path("icons/stop.png")) else QIcon())
        self.main_tab.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 8px 16px;
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
        self.main_tab.status.setText("Status: Watching...")
        self.main_tab.status.setStyleSheet("""
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

        # Stop the timer
        if self.timer.isActive():
            self.timer.stop()

        self.main_tab.toggle_btn.setText("Start Watching")
        self.main_tab.toggle_btn.setIcon(safe_icon("icons/play.png") if os.path.exists(get_resource_path("icons/play.png")) else QIcon())
        self.main_tab.toggle_btn.setStyleSheet("""
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
                self.main_tab.update_status_style()
                return

            self.watching = True
            self.watcher_manager.update_watchers(pairs)  # Start real-time watchers

            # Start the timer for regular scanning (every 5 seconds)
            self.timer.start(5000)

            # Do an immediate scan
            self.scan_all_pairs()

            self.main_tab.toggle_btn.setText("Stop Watching")
            self.main_tab.toggle_btn.setIcon(safe_icon("icons/stop.png") if os.path.exists(get_resource_path("icons/stop.png")) else QIcon())
            self.main_tab.toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    font-weight: bold;
                    font-size: 14px;
                    border-radius: 4px;
                    padding: 8px 16px;
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
            self.main_tab.status.setText("Status: Watching...")
            self.main_tab.update_status_style()

            # Show notification
            self.show_notification(
                "Watching Started",
                "Auto Organizer is now watching folders",
                QSystemTrayIcon.Information,
                2000
            )
        else:
            self.watching = False
            self.watcher_manager.stop_all()  # Stop all watchers

            # Stop the timer
            if self.timer.isActive():
                self.timer.stop()

            self.main_tab.toggle_btn.setText("Start Watching")
            self.main_tab.toggle_btn.setIcon(safe_icon("icons/play.png") if os.path.exists(get_resource_path("icons/play.png")) else QIcon())
            self.main_tab.toggle_btn.setStyleSheet("""
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
            self.main_tab.status.setText("Status: Stopped")
            self.main_tab.update_status_style()

            # Show notification
            self.show_notification(
                "Watching Stopped",
                "Auto Organizer has stopped watching folders",
                QSystemTrayIcon.Information,
                2000
            )

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
        self.main_tab.load_settings(self.config)

        # Setup auto-save for main tab
        try:
            self.main_tab.table.itemChanged.connect(self.auto_save_settings)
        except Exception as e:
            print(f"Error connecting table itemChanged signal: {str(e)}")

        # Use safe_icon for tab icons
        self.tabs.addTab(self.main_tab, safe_icon("icons/watch.png"), "Watchers")

        # Settings tab - explicitly pass self as parent
        self.settings_tab = SettingsTab(self)
        self.settings_tab.reset_btn.clicked.connect(self.reset_settings)
        self.settings_tab.theme_changed.connect(self.apply_theme_and_save)
        self.settings_tab.start_on_launch_changed.connect(self.handle_start_on_launch)

        # Load settings after connecting signals
        try:
            self.settings_tab.load_settings(self.config)
            print("Settings tab loaded successfully")
        except Exception as e:
            print(f"Error loading settings tab: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")

        self.tabs.addTab(self.settings_tab, safe_icon("icons/settings.png"), "Settings")

        # Logs tab - explicitly pass self as parent
        self.logs_tab = LogsTab(self)
        self.tabs.addTab(self.logs_tab, safe_icon("icons/logs.png"), "Logs")

        # About tab - explicitly pass self as parent
        self.about_tab = AboutTab(self, VERSION_FILE)
        self.about_tab.update_auto_update_status(self.config.get("auto_update_check", True))
        self.tabs.addTab(self.about_tab, safe_icon("icons/info.png"), "About")

    def auto_save_settings(self):
        """Auto-save settings when any setting is changed"""
        try:
            # Save settings from all tabs
            self.main_tab.save_settings(self.config)
            self.settings_tab.save_settings(self.config)

            # Handle auto-update timer
            if self.config.get("auto_update_check", True):
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
            self.about_tab.update_auto_update_status(self.config.get("auto_update_check", True))

            # Save to file
            try:
                # Make sure the directory exists
                config_dir = os.path.dirname(CONFIG_FILE)
                if config_dir and not os.path.exists(config_dir):
                    os.makedirs(config_dir, exist_ok=True)

                # Save the config file
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(self.config, f)

                # Print debug info
                print(f"Settings saved to {CONFIG_FILE}")
                print(f"Config contents: {self.config}")
            except Exception as file_error:
                print(f"Error saving config file: {str(file_error)}")
                print(f"Error details: {traceback.format_exc()}")
                self.statusBar().showMessage(f"Error saving settings: {str(file_error)}", 3000)
                return

            # Show a brief notification in the status bar instead of a popup
            # Only show generic message if not already showing a specific message
            if not self.statusBar().currentMessage():
                self.statusBar().showMessage("Settings saved", 2000)

        except Exception as e:
            print(f"Error auto-saving settings: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            self.statusBar().showMessage(f"Error saving settings: {str(e)}", 3000)

    def apply_theme_and_save(self, theme):
        """Apply theme and save settings"""
        self.apply_theme(theme)
        self.auto_save_settings()

    def apply_theme(self, theme):
        theme = theme.lower()
        app = QApplication.instance()
        palette = QPalette()
        is_dark_mode = False

        if theme == "system default":
            if platform.system() == "Windows":
                theme = get_windows_system_theme()
            else:
                theme = "light"

        if theme == "dark":
            is_dark_mode = True
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
            is_dark_mode = False
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

        # Apply some additional styling to improve the GUI
        if is_dark_mode:
            app.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #505050;
                    border-top: 0px;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    padding: 6px 12px;
                    margin: 2px 2px 0px 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    background-color: #383838;
                    color: #e0e0e0;
                }
                QTabBar::tab:selected {
                    font-weight: bold;
                    background-color: #505050;
                }
                QPushButton {
                    padding: 6px 12px;
                    border-radius: 4px;
                    border: 1px solid #505050;
                    background-color: #383838;
                    color: #e0e0e0;
                }
                QTableWidget {
                    gridline-color: #3a3a3a;
                    selection-background-color: #0078d7;
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                }
                QHeaderView::section {
                    padding: 6px;
                    font-weight: bold;
                    background-color: #383838;
                    color: #e0e0e0;
                    border: 1px solid #505050;
                }
                QComboBox {
                    border: 1px solid #505050;
                    border-radius: 4px;
                    padding: 4px 8px;
                    background-color: #383838;
                    color: #e0e0e0;
                }
                QComboBox::drop-down {
                    border-left: 1px solid #505050;
                }
                QComboBox::down-arrow {
                    /* First try to use the white arrow image for dark mode */
                    image: url(icons/dropdown_white.png);
                    width: 12px;
                    height: 12px;
                    /* Fallback styling in case image isn't available */
                    color: #e0e0e0;
                }
                QComboBox QAbstractItemView {
                    border: 1px solid #505050;
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    selection-background-color: #0078d7;
                    selection-color: white;
                }
                QComboBox QAbstractItemView::item {
                    min-height: 24px;
                    padding: 4px;
                    color: #e0e0e0;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: rgba(0, 120, 215, 0.4);
                }
                QLineEdit, QTextEdit {
                    border: 1px solid #505050;
                    border-radius: 4px;
                    padding: 4px;
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                }
                QCheckBox {
                    color: #e0e0e0;
                }
                QLabel {
                    color: #e0e0e0;
                }
                QGroupBox {
                    border: 1px solid #505050;
                    border-radius: 4px;
                    margin-top: 8px;
                    color: #e0e0e0;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """)
        else:
            app.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #999;
                    border-top: 0px;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    padding: 6px 12px;
                    margin: 2px 2px 0px 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    font-weight: bold;
                }
                QPushButton {
                    padding: 6px 12px;
                    border-radius: 4px;
                    border: 1px solid #999;
                }
                QTableWidget {
                    gridline-color: #ccc;
                    selection-background-color: #0078d7;
                }
                QHeaderView::section {
                    padding: 6px;
                    font-weight: bold;
                }
            """)

        # Update the tabs' dark mode setting
        if hasattr(self, 'main_tab'):
            self.main_tab.set_dark_mode(is_dark_mode)

        if hasattr(self, 'settings_tab'):
            self.settings_tab.set_dark_mode(is_dark_mode)

        # Apply theme to window title bar (Windows 10/11 only)
        if platform.system() == 'Windows':
            try:
                # Get the window handle
                hwnd = int(self.winId())

                # Set the title bar theme
                success = set_window_title_bar_theme(hwnd, is_dark_mode)

                if success:
                    print(f"Successfully applied {'dark' if is_dark_mode else 'light'} theme to window title bar")
                else:
                    print("Failed to apply theme to window title bar")
            except Exception as e:
                print(f"Error applying theme to window title bar: {str(e)}")
                print(f"Error details: {traceback.format_exc()}")


    def handle_start_on_launch(self, enabled):
        """Handle the start on launch setting change with better Windows 10/11 compatibility"""
        startup_key = r"Software\Microsoft\Windows\CurrentVersion\Run"

        try:
            # Get the actual executable path
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                exe_path = sys.executable
            else:
                # Running as script
                exe_path = os.path.abspath(sys.argv[0])

            # Try multiple methods to ensure compatibility with different Windows versions
            success = False

            # Method 1: Windows Registry
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup_key, 0, winreg.KEY_ALL_ACCESS) as key:
                    if enabled:
                        # Add to startup with proper quoting and arguments
                        startup_command = f'"{exe_path}" --minimized'
                        winreg.SetValueEx(key, "Auto Organizer", 0, winreg.REG_SZ, startup_command)
                        self.logging_signal.emit("Added Auto Organizer to startup programs via registry", None, None)
                        success = True
                    else:
                        # Remove from startup
                        try:
                            winreg.DeleteValue(key, "Auto Organizer")
                            self.logging_signal.emit("Removed Auto Organizer from startup programs via registry", None, None)
                            success = True
                        except FileNotFoundError:
                            # Key doesn't exist, which is fine when disabling
                            success = True
            except Exception as reg_error:
                print(f"Registry startup method failed: {str(reg_error)}")
                self.logging_signal.emit(f"Registry startup method failed: {str(reg_error)}", None, None)

            # Method 2: Startup folder shortcut (if registry method failed)
            if not success:
                try:
                    # Get the startup folder path
                    startup_folder = os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup")
                    shortcut_path = os.path.join(startup_folder, "Auto Organizer.lnk")

                    if enabled:
                        # Create a shortcut using PowerShell
                        ps_command = f'''
                        $WshShell = New-Object -ComObject WScript.Shell
                        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
                        $Shortcut.TargetPath = "{exe_path}"
                        $Shortcut.Arguments = "--minimized"
                        $Shortcut.WorkingDirectory = "{os.path.dirname(exe_path)}"
                        $Shortcut.Description = "Auto Organizer"
                        $Shortcut.Save()
                        '''

                        # Create a hidden process to run PowerShell
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = 0  # SW_HIDE

                        subprocess.run(["powershell", "-Command", ps_command],
                                     startupinfo=startupinfo,
                                     check=True)

                        self.logging_signal.emit("Added Auto Organizer to startup programs via shortcut", None, None)
                        success = True
                    else:
                        # Remove the shortcut if it exists
                        if os.path.exists(shortcut_path):
                            os.remove(shortcut_path)
                            self.logging_signal.emit("Removed Auto Organizer from startup programs via shortcut", None, None)
                        success = True
                except Exception as shortcut_error:
                    print(f"Shortcut startup method failed: {str(shortcut_error)}")
                    self.logging_signal.emit(f"Shortcut startup method failed: {str(shortcut_error)}", None, None)

            if not success:
                self.logging_signal.emit("Failed to modify startup settings. Please add the application to startup manually.", None, None)

            # Auto-save the settings
            self.auto_save_settings()

        except Exception as e:
            print(f"Start on launch error: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            self.logging_signal.emit(f"Failed to modify startup settings: {str(e)}", None, None)

        # Only start watching if setting was just enabled
        if enabled and not self.watching:
            pairs = self.main_tab.get_watch_pairs()
            if pairs:
                self.watching = True
                self.watcher_manager.update_watchers(pairs)
                self.main_tab.toggle_btn.setText("Stop Watching")
                self.main_tab.toggle_btn.setIcon(safe_icon("icons/stop.png") if os.path.exists(get_resource_path("icons/stop.png")) else QIcon())
                self.main_tab.toggle_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f44336;
                        color: white;
                        font-weight: bold;
                        font-size: 14px;
                        border-radius: 4px;
                        padding: 8px 16px;
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
                self.main_tab.status.setText("Status: Watching...")
                self.main_tab.update_status_style()
                self.update_tray_menu()
                self.show_notification(
                    "Auto Start",
                    "Auto Organizer is now watching folders",
                    QSystemTrayIcon.Information,
                    2000
                )

    def restore_window(self):
        """Restore window from system tray with better Windows 10/11 compatibility"""
        try:
            # Restore normal window flags
            self.setWindowFlags(self.windowFlags() & ~Qt.Tool)
            self.setVisible(True)
            self.showNormal()
            self.activateWindow()
            self.raise_()  # Bring window to front

            # Reapply theme to ensure title bar is themed correctly
            self.apply_theme(self.config.get("theme", "System Default"))

            # On Windows, use Win32 API for more reliable window activation
            if platform.system() == 'Windows':
                try:
                    # Try to use Win32 API to force window to foreground
                    import ctypes
                    user32 = ctypes.windll.user32
                    hwnd = int(self.winId())

                    # SW_RESTORE = 9 if window is minimized
                    user32.ShowWindow(hwnd, 9)

                    # Set our window as the foreground window
                    user32.SetForegroundWindow(hwnd)

                    # Flash window to get user's attention
                    # FLASHW_ALL = 3, FLASHW_TIMERNOFG = 12
                    flash_info = ctypes.Structure()
                    flash_info._fields_ = [
                        ("cbSize", ctypes.c_uint),
                        ("hwnd", ctypes.c_void_p),
                        ("dwFlags", ctypes.c_uint),
                        ("uCount", ctypes.c_uint),
                        ("dwTimeout", ctypes.c_uint)
                    ]
                    flash_info.cbSize = ctypes.sizeof(flash_info)
                    flash_info.hwnd = hwnd
                    flash_info.dwFlags = 3 | 12  # FLASHW_ALL | FLASHW_TIMERNOFG
                    flash_info.uCount = 5
                    flash_info.dwTimeout = 0
                    user32.FlashWindowEx(ctypes.byref(flash_info))

                except Exception as e:
                    print(f"Win32 window activation failed: {str(e)}")
                    # Fall back to Qt methods which were already called
        except Exception as e:
            print(f"Error restoring window: {str(e)}")
            # Try basic show as last resort
            self.show()
            # Still try to apply theme
            self.apply_theme(self.config.get("theme", "System Default"))

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
        """Load configuration with defaults for Windows 10/11 compatibility"""
        try:
            print(f"Loading config from: {CONFIG_FILE}")
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, 'r') as f:
                        config_content = f.read()
                        print(f"Config file content: {config_content}")
                        if not config_content.strip():
                            print("Config file is empty, using defaults")
                            self.config = {}
                        else:
                            self.config = json.loads(config_content)
                            print(f"Loaded config: {self.config}")
                except json.JSONDecodeError as json_error:
                    print(f"Error: Config file {CONFIG_FILE} is corrupted: {str(json_error)}")
                    print(f"Error details: {traceback.format_exc()}")
                    self.config = {}
                    # Backup the corrupted file
                    if os.path.exists(CONFIG_FILE):
                        backup_path = CONFIG_FILE + ".bak"
                        try:
                            shutil.copy2(CONFIG_FILE, backup_path)
                            print(f"Backed up corrupted config to {backup_path}")
                        except Exception as backup_error:
                            print(f"Error backing up config: {str(backup_error)}")
                except Exception as read_error:
                    print(f"Error reading config file: {str(read_error)}")
                    print(f"Error details: {traceback.format_exc()}")
                    self.config = {}
            else:
                print(f"Config file does not exist: {CONFIG_FILE}")
                self.config = {}

            # Set defaults for all configuration options
            self.config.setdefault("version", load_version(VERSION_FILE))
            self.config.setdefault("minimize_on_startup", False)
            self.config.setdefault("exit_on_close", False)
            self.config.setdefault("auto_update_check", True)
            self.config.setdefault("show_notifications", True)
            self.config.setdefault("theme", "System Default")
            self.config.setdefault("start_on_launch", False)
            self.config.setdefault("verbose_logging", False)
            self.config.setdefault("process_directories", True)
            self.config.setdefault("max_file_age_hours", 24)
            self.config.setdefault("auto_watch", True)

            # Save config to ensure all defaults are written
            try:
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(self.config, f)
            except Exception as save_error:
                print(f"Error saving config defaults: {str(save_error)}")

        except Exception as e:
            print(f"Error loading config: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            # Fallback to minimal defaults
            self.config = {
                "version": load_version(VERSION_FILE),
                "theme": "System Default",
                "show_notifications": True
            }

    def scan_all_pairs(self):
        """Scan all watch pairs for files to organize with improved reliability for Windows 10/11"""
        # No need to import shutil here as it's already imported at the top

        def process_pair(watch, target):
            if not watch or not target:
                self.logging_signal.emit("Invalid watch/target pair", None, None)
                return

            try:
                # Validate directories with better error handling
                try:
                    if not os.path.exists(watch):
                        self.logging_signal.emit(f"Watch directory does not exist: {watch}", None, None)
                        return
                    if not os.path.isdir(watch):
                        self.logging_signal.emit(f"Watch path is not a directory: {watch}", None, None)
                        return
                    if not os.path.exists(target):
                        self.logging_signal.emit(f"Target directory does not exist: {target}", None, None)
                        return
                    if not os.path.isdir(target):
                        self.logging_signal.emit(f"Target path is not a directory: {target}", None, None)
                        return
                except Exception as path_error:
                    self.logging_signal.emit(f"Error validating paths: {str(path_error)}", None, None)
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

                # Get all items in directory with better error handling
                try:
                    items = os.listdir(watch)
                except PermissionError:
                    self.logging_signal.emit(f"Permission denied accessing directory: {watch}", None, None)
                    return
                except FileNotFoundError:
                    self.logging_signal.emit(f"Directory disappeared during scan: {watch}", None, None)
                    return
                except Exception as e:
                    self.logging_signal.emit(f"Error scanning directory {watch}: {str(e)}", None, None)
                    return

                # First do a pre-check of all files
                valid_items = []
                for item in items:
                    try:
                        src = os.path.join(watch, item)

                        # Skip if file doesn't exist or is system/hidden file
                        if not os.path.exists(src) or item.startswith('.') or item.startswith('$'):
                            continue

                        # Skip directories if configured to do so
                        if os.path.isdir(src) and not self.config.get("process_directories", True):
                            continue

                        # Do basic comma validation before queueing
                        if ',' not in item:
                            # Only log this at debug level to avoid spamming logs
                            if self.config.get("verbose_logging", False):
                                self.logging_signal.emit(f"Not processing - no comma in filename: {item}", None, None)
                            continue

                        # Split and check parts
                        try:
                            prefix, remainder = item.split(',', 1)
                            if not prefix.strip() or not remainder.strip():
                                if self.config.get("verbose_logging", False):
                                    self.logging_signal.emit(f"Not processing - invalid format: {item}", None, None)
                                continue
                        except:
                            if self.config.get("verbose_logging", False):
                                self.logging_signal.emit(f"Not processing - invalid split: {item}", None, None)
                            continue

                        # Check file age if configured
                        try:
                            if self.config.get("max_file_age_hours", 24) > 0:
                                file_mtime = os.path.getmtime(src)
                                file_age_hours = (time.time() - file_mtime) / 3600
                                if file_age_hours > self.config.get("max_file_age_hours", 24):
                                    continue
                        except Exception as age_error:
                            if self.config.get("verbose_logging", False):
                                self.logging_signal.emit(f"Error checking file age for {item}: {str(age_error)}", None, None)
                            continue

                        valid_items.append((item, src))
                    except Exception as item_error:
                        if self.config.get("verbose_logging", False):
                            self.logging_signal.emit(f"Error processing item {item}: {str(item_error)}", None, None)
                        continue

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
                print(f"Error details for process_pair: {traceback.format_exc()}")

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
            print(f"Error details for scan_all_pairs: {traceback.format_exc()}")

    def reset_settings(self):
        """Reset all settings to defaults and reload the UI"""
        try:
            # Confirm with the user
            reply = QMessageBox.question(
                self,
                "Reset Settings",
                "Are you sure you want to reset all settings to defaults?\n\nThis will clear all watch pairs and settings.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # Stop watching if active
            if self.watching:
                self.watching = False
                self.watcher_manager.stop_all()
                if self.timer.isActive():
                    self.timer.stop()

            # Reset config to defaults
            self.config = {
                "version": load_version(VERSION_FILE),
                "minimize_on_startup": False,
                "exit_on_close": False,
                "auto_update_check": True,
                "show_notifications": True,
                "theme": "System Default",
                "start_on_launch": False,
                "verbose_logging": False,
                "process_directories": True,
                "max_file_age_hours": 24,
                "auto_watch": True,
                "watch_pairs": []
            }

            # Save the reset config
            try:
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(self.config, f)
                print(f"Reset config saved to {CONFIG_FILE}")
            except Exception as save_error:
                print(f"Error saving reset config: {str(save_error)}")
                print(f"Error details: {traceback.format_exc()}")

            # Reload the UI
            # Clear the main tab
            while self.main_tab.table.rowCount() > 0:
                self.main_tab.table.removeRow(0)

            # Reload settings in tabs
            self.main_tab.load_settings(self.config)
            self.settings_tab.load_settings(self.config)

            # Apply default theme
            self.apply_theme("System Default")

            # Update UI state
            self.main_tab.toggle_btn.setText("Start Watching")
            self.main_tab.toggle_btn.setIcon(safe_icon("icons/play.png"))
            self.main_tab.status.setText("Status: Stopped")
            self.main_tab.update_status_style()

            # Show success message
            self.statusBar().showMessage("Settings reset to defaults", 3000)
            QMessageBox.information(self, "Reset Complete", "All settings have been reset to defaults.")

        except Exception as e:
            print(f"Error resetting settings: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            QMessageBox.warning(self, "Reset Failed", f"Error resetting settings: {str(e)}")

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
        """Refresh the version display if version.txt has changed with better interrupt handling"""
        try:
            # Use a flag to track if we need to save config
            need_save = False

            try:
                current_version = load_version(VERSION_FILE)

                # Update about tab version label if it exists
                if hasattr(self, 'about_tab'):
                    try:
                        self.about_tab.update_version_display(current_version)
                    except Exception as ui_error:
                        print(f"Error updating version display: {str(ui_error)}")

                # Update config if version has changed
                if self.config.get("version") != current_version:
                    self.config["version"] = current_version
                    need_save = True

            except KeyboardInterrupt:
                print("Version refresh interrupted by user")
                return
            except Exception as e:
                print(f"Error getting version: {str(e)}")
                return

            # Save config to file to persist the version change if needed
            if need_save:
                try:
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump(self.config, f)
                except KeyboardInterrupt:
                    print("Config save interrupted by user")
                except Exception as save_error:
                    print(f"Error saving config during version refresh: {str(save_error)}")

        except KeyboardInterrupt:
            # Handle keyboard interrupt gracefully
            print("Version refresh interrupted by user")
        except Exception as e:
            print(f"Error refreshing version: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")

    def show_notification(self, title, message, icon=QSystemTrayIcon.Information, duration=2000):
        """Show a system tray notification if enabled"""
        try:
            if self.config.get("show_notifications", True) and self.tray and self.tray.isSystemTrayAvailable():
                self.tray.showMessage(title, message, icon, duration)
        except Exception as e:
            print(f"Error showing notification: {str(e)}")

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

class SingleInstanceChecker:
    """
    Ensures only one instance of the application is running.
    Uses a socket-based approach which works reliably on Windows 10 and Windows 11.
    Also provides functionality to activate the existing instance.
    """
    def __init__(self, app_name="AutoOrganizer"):
        self.app_name = app_name
        self.socket = None
        self.lock_file = os.path.join(tempfile.gettempdir(), f"{app_name}.lock")
        self.port = self._get_port_from_app_name()
        self.server_thread = None
        self.running = True

    def _get_port_from_app_name(self):
        """Generate a port number from the app name (between 49152 and 65535)"""
        # Use a hash of the app name to generate a consistent port number
        port_hash = sum(ord(c) for c in self.app_name) % 16383
        return port_hash + 49152  # Use the private port range (49152-65535)

    def is_already_running(self):
        """Check if another instance is already running"""
        try:
            # Try to create and bind a socket to the port
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Set socket timeout to avoid hanging
            self.socket.settimeout(1.0)

            try:
                self.socket.bind(('127.0.0.1', self.port))
                self.socket.listen(1)

                # Start a thread to accept connections from other instances
                self._start_server_thread()

                # If we get here, no other instance is using this port
                # Create a lock file with our PID
                try:
                    with open(self.lock_file, 'w') as f:
                        f.write(str(os.getpid()))
                except Exception as e:
                    print(f"Warning: Could not create lock file: {str(e)}")

                return False
            except socket.error as e:
                print(f"Socket binding error: {str(e)}")
                # Socket is already in use, another instance is running
                return True

        except Exception as e:
            print(f"Error in single instance check: {str(e)}")
            # On any error, assume no other instance is running to avoid blocking the app
            return False

    def _start_server_thread(self):
        """Start a thread to listen for activation requests from other instances"""
        import threading

        def server_thread():
            try:
                while self.running and self.socket:
                    try:
                        # Accept connections with timeout
                        self.socket.settimeout(1.0)
                        try:
                            client, _ = self.socket.accept()
                            # Received connection from another instance
                            # This means we should activate our window
                            client.close()
                            self._activate_window()
                        except socket.timeout:
                            # This is expected, just continue the loop
                            pass
                    except Exception as e:
                        if self.running:  # Only log if we're still supposed to be running
                            print(f"Error in server thread: {str(e)}")
                            time.sleep(0.5)  # Avoid tight loop on error
            except Exception as e:
                print(f"Server thread exiting due to error: {str(e)}")

        self.server_thread = threading.Thread(target=server_thread, daemon=True)
        self.server_thread.start()

    def _activate_window(self):
        """Activate the main window of the application"""
        try:
            # This will be called from the server thread
            # We need to use Qt's signal/slot mechanism to safely interact with the UI
            # The actual implementation will be connected from the main thread
            pass
        except Exception as e:
            print(f"Error activating window: {str(e)}")

    def activate_existing_instance(self):
        """Try to activate an existing instance of the application"""
        try:
            # Try to connect to the existing instance's socket
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(1.0)
            try:
                # Connect to the existing instance
                client.connect(('127.0.0.1', self.port))
                # Just connecting is enough to signal the other instance
                client.close()
                return True
            except (socket.error, socket.timeout) as e:
                print(f"Could not connect to existing instance: {str(e)}")
                return False
        except Exception as e:
            print(f"Error activating existing instance: {str(e)}")
            return False

    def cleanup(self):
        """Clean up resources when the application exits"""
        try:
            self.running = False
            if self.socket:
                self.socket.close()
                self.socket = None
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except Exception as e:
            print(f"Error during instance checker cleanup: {str(e)}")
            pass

if __name__ == "__main__":
    # Enable high DPI scaling before creating QApplication
    # This must be done before QApplication is created
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Set up exception handling to catch and log all errors
    def exception_hook(exc_type, exc_value, exc_traceback):
        """Global exception handler to log unhandled exceptions"""
        # Special handling for KeyboardInterrupt
        if exc_type is KeyboardInterrupt:
            print("Application interrupted by user (Ctrl+C)")
            # Clean up and exit gracefully
            try:
                if QApplication.instance():
                    QApplication.instance().quit()
            except:
                pass
            return

        # For other exceptions, show detailed error
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(f"Unhandled exception: {error_msg}")

        # Try to show error dialog if QApplication exists
        try:
            if QApplication.instance():
                error_box = QMessageBox()
                error_box.setIcon(QMessageBox.Critical)
                error_box.setWindowTitle("Unhandled Error")
                error_box.setText("An unexpected error occurred:")
                error_box.setInformativeText(str(exc_value))
                error_box.setDetailedText(error_msg)
                error_box.exec_()
        except:
            pass

        # Call the original exception hook
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    # Install the exception hook
    sys.excepthook = exception_hook

    # Check if another instance is already running
    instance_checker = SingleInstanceChecker("AutoOrganizer")
    if instance_checker.is_already_running():
        # Create a minimal QApplication just to show the message box
        app = QApplication(sys.argv)
        app.setApplicationName("Auto Organizer")

        # Try to activate the existing instance
        activation_successful = instance_checker.activate_existing_instance()

        # Show message box informing the user
        if activation_successful:
            message = "Auto Organizer is already running.\n\nThe existing instance has been activated. Please check your taskbar or system tray."
        else:
            message = "Auto Organizer is already running.\n\nPlease check your system tray for the running instance."

        QMessageBox.information(
            None,
            "Auto Organizer Already Running",
            message,
            QMessageBox.Ok
        )

        # Exit the application
        sys.exit(0)

    try:
        # Create application
        app = QApplication(sys.argv)

        # Set application metadata
        app.setApplicationName("Auto Organizer")
        app.setApplicationVersion(load_version(os.path.join(os.path.dirname(__file__), "version.txt")))
        app.setOrganizationName("Eyad Elshaer")

        # Create the instance checker for the main instance
        instance_checker = SingleInstanceChecker("AutoOrganizer")

        # Create main window and pass the instance checker
        window = WatcherApp(instance_checker)

        # Only show the window if minimize_on_startup is False
        if not window.config.get("minimize_on_startup", False):
            window.show()
            window.activateWindow()
            window.raise_()
        else:
            window.hide_to_tray()
            window.show_notification(
                "Auto Organizer",
                "Running in system tray",
                QSystemTrayIcon.Information,
                2000
            )

        # Set up signal handler for Ctrl+C in console
        def signal_handler(sig, _):  # Use underscore for unused frame parameter
            print(f"Received interrupt signal {sig}, shutting down gracefully...")
            app.quit()

        # Try to install signal handler if on a platform that supports it
        try:
            import signal
            signal.signal(signal.SIGINT, signal_handler)

            # Allow Python interpreter to catch Ctrl-C every 500ms
            # This is needed because Qt blocks Python's signal handling
            timer = QTimer()
            timer.start(500)
            timer.timeout.connect(lambda: None)  # Let the interpreter run
        except (ImportError, AttributeError):
            # Signal handling might not be available on all platforms
            print("Signal handling not available on this platform")
            pass

        try:
            # Start the application event loop
            exit_code = app.exec_()
        except KeyboardInterrupt:
            print("Application interrupted by keyboard, shutting down...")
            exit_code = 0
            app.quit()

        # Clean up resources before exit
        try:
            print("Cleaning up resources...")
            if hasattr(window, 'watcher_manager'):
                window.watcher_manager.stop_all()
            if hasattr(window, 'file_processor'):
                window.file_processor.stop()
                window.worker_thread.quit()
                window.worker_thread.wait(1000)  # Wait up to 1 second for thread to finish

            # Clean up the single instance checker
            if 'instance_checker' in locals() or 'instance_checker' in globals():
                instance_checker.cleanup()
                print("Single instance checker cleaned up")

            # Also clean up the instance checker in the window if it exists
            if hasattr(window, 'instance_checker') and window.instance_checker:
                window.instance_checker.cleanup()
                print("Window's instance checker cleaned up")
        except Exception as cleanup_error:
            print(f"Error during cleanup: {str(cleanup_error)}")

        print("Application shutdown complete")
        sys.exit(exit_code)

    except Exception as e:
        # If there's an error during startup, show it in a message box
        error_msg = traceback.format_exc()
        print(f"Startup error: {error_msg}")

        try:
            # Try to show error in GUI
            if QApplication.instance() is None:
                app = QApplication(sys.argv)

            error_box = QMessageBox()
            error_box.setIcon(QMessageBox.Critical)
            error_box.setWindowTitle("Startup Error")
            error_box.setText("An error occurred while starting the application:")
            error_box.setInformativeText(str(e))
            error_box.setDetailedText(error_msg)
            error_box.exec_()
        except:
            # If GUI fails, print to console
            print(f"Critical error: {str(e)}")
            print(error_msg)

        sys.exit(1)