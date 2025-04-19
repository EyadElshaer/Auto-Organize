import os, json, shutil, datetime
from PyQt5.QtWidgets import (
    QLabel, QPushButton, QScrollArea, QVBoxLayout,
    QHBoxLayout, QFrame, QWidget, QMessageBox,
    QDialog, QDateTimeEdit, QFormLayout, QDialogButtonBox, QFileDialog
)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal, QTimer
# When running directly
try:
    from tabs.base_tab import BaseTab
except ModuleNotFoundError:
    from base_tab import BaseTab  # For direct execution

# Path for log storage
LOGS_FILE = os.path.expanduser("~/.watcher_logs.json")

class LogEntry(QFrame):
    """A log entry widget with undo/redo functionality"""
    undo_requested = pyqtSignal(str, str)
    redo_requested = pyqtSignal(str, str)

    def __init__(self, message, source=None, destination=None, timestamp=None, is_undone=False, parent=None):
        super().__init__(parent)
        # Store original paths
        self.original_source = source  # Where the file was originally from
        self.original_destination = destination  # Where the file was moved to
        self.current_location = destination  # Current location of the file
        self.message = message
        self.is_undone = is_undone
        self.timestamp = timestamp or QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")

        layout = QHBoxLayout()
        self.message_label = QLabel(f"[{self.timestamp}] {message}")
        layout.addWidget(self.message_label)
        
        # Status label to show if files exist
        self.status_label = QLabel()
        self.update_file_status()
        layout.addWidget(self.status_label)

        # Only show buttons if source and destination are provided
        if source and destination:
            self.undo_btn = QPushButton("Undo")
            self.redo_btn = QPushButton("Redo")
            layout.addWidget(self.undo_btn)
            layout.addWidget(self.redo_btn)

            # Initially, only show appropriate button
            if self.is_undone:
                self.undo_btn.hide()
                self.redo_btn.show()
            else:
                self.redo_btn.hide()
                self.undo_btn.show()

            self.undo_btn.clicked.connect(self.handle_undo)
            self.redo_btn.clicked.connect(self.handle_redo)

        self.setLayout(layout)
        self.setFrameShape(QFrame.StyledPanel)
        
    def update_file_status(self):
        """Check and update the status of files in this log entry"""
        if not hasattr(self, 'status_label') or not self.status_label:
            return
            
        if not self.original_source and not self.original_destination:
            self.status_label.clear()
            return
            
        if self.is_undone:
            # Check if the undone file exists
            if os.path.exists(self.current_location):
                self.status_label.setText("✓")
                self.status_label.setStyleSheet("color: green")
            else:
                self.status_label.setText("✗")
                self.status_label.setStyleSheet("color: red")
        else:
            # Check if the destination file exists
            if os.path.exists(self.current_location):
                self.status_label.setText("✓")
                self.status_label.setStyleSheet("color: green")
            else:
                self.status_label.setText("✗")
                self.status_label.setStyleSheet("color: red")

    def handle_undo(self):
        # Get the directory where the file originally came from
        original_dir = os.path.dirname(self.original_source)
        current_filename = os.path.basename(self.current_location)
        name, ext = os.path.splitext(current_filename)
        
        # Create the undo destination path in the original directory
        undo_destination = os.path.join(original_dir, f"{name} (Undo){ext}")
        
        # Emit signal to move from current location back to original directory
        self.undo_requested.emit(self.current_location, undo_destination)
        self.current_location = undo_destination
        self.is_undone = True
        self.undo_btn.hide()
        self.redo_btn.show()

    def handle_redo(self):
        if self.is_undone and os.path.exists(self.current_location):
            # Move from current (undo) location back to original destination
            self.redo_requested.emit(self.current_location, self.original_destination)
            self.current_location = self.original_destination
            self.is_undone = False
            self.undo_btn.show()
            self.redo_btn.hide()
            
    def to_dict(self):
        """Convert log entry to a dictionary for serialization"""
        return {
            "message": self.message,
            "timestamp": self.timestamp,
            "original_source": self.original_source,
            "original_destination": self.original_destination,
            "current_location": self.current_location,
            "is_undone": self.is_undone
        }

class DateRangeDialog(QDialog):
    """Dialog to select a date range for log export"""
    
    def __init__(self, parent=None):
        # Always ensure we get a parent window 
        super().__init__(parent)
        self.setWindowTitle("Select Date Range")
        self.resize(400, 150)
        # Set modal to true to prevent interacting with the main window
        self.setModal(True)
        
        # Create form layout
        layout = QFormLayout(self)
        
        # Start date/time
        self.start_date = QDateTimeEdit(self)
        self.start_date.setDateTime(QDateTime.currentDateTime().addDays(-7))  # Default to a week ago
        self.start_date.setCalendarPopup(True)
        layout.addRow("Start Date/Time:", self.start_date)
        
        # End date/time
        self.end_date = QDateTimeEdit(self)
        self.end_date.setDateTime(QDateTime.currentDateTime())  # Default to now
        self.end_date.setCalendarPopup(True)
        layout.addRow("End Date/Time:", self.end_date)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
    def get_range(self):
        """Return the selected date range as strings"""
        return (
            self.start_date.dateTime().toString("yyyy-MM-dd hh:mm:ss"),
            self.end_date.dateTime().toString("yyyy-MM-dd hh:mm:ss")
        )

class LogsTab(BaseTab):
    """Logs tab for showing application activity"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.log_entries = []  # Store log entries for saving
        self.init_ui()
        self.load_logs()
        
        # Timer to periodically check file status
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_all_file_status)
        self.status_timer.start(10000)  # Check every 10 seconds
        
    def init_ui(self):
        """Initialize the UI components"""
        # Button row
        buttons_layout = QHBoxLayout()
        
        # Clear logs button
        self.clear_btn = QPushButton("Clear All Logs")
        self.clear_btn.clicked.connect(self.clear_logs)
        buttons_layout.addWidget(self.clear_btn)
        
        # Verify button
        self.verify_btn = QPushButton("Verify Files")
        self.verify_btn.clicked.connect(self.check_all_file_status)
        buttons_layout.addWidget(self.verify_btn)
        
        # Export logs button
        self.export_btn = QPushButton("Export Logs")
        self.export_btn.clicked.connect(self.export_logs)
        buttons_layout.addWidget(self.export_btn)
        
        self.main_layout.addLayout(buttons_layout)

        # Logs scroll area
        self.logs_area = QScrollArea()
        self.logs_area.setWidgetResizable(True)
        self.logs_container = QWidget()
        self.logs_container_layout = QVBoxLayout()
        self.logs_container_layout.setAlignment(Qt.AlignTop)
        self.logs_container.setLayout(self.logs_container_layout)
        self.logs_area.setWidget(self.logs_container)

        self.main_layout.addWidget(self.logs_area)
        
    def check_all_file_status(self):
        """Check status of all files in log entries"""
        for i in range(self.logs_container_layout.count()):
            widget = self.logs_container_layout.itemAt(i).widget()
            if isinstance(widget, LogEntry):
                widget.update_file_status()
        
    def clear_logs(self):
        """Clear all log entries"""
        confirm = QMessageBox.question(
            self, "Clear Logs", 
            "Are you sure you want to clear all logs? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            for i in reversed(range(self.logs_container_layout.count())):
                widget = self.logs_container_layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)
            self.log_entries = []
            self.save_logs()
                
    def log(self, message, source=None, destination=None):
        """Add a new log entry"""
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        
        if source is not None and destination is not None:
            # Check if this is an original move message or a moved back message
            is_original_move = not ("Moved back" in message or "(Undo)" in message or "(Redo)" in message)
            
            if is_original_move:
                # Create log entry with buttons for original moves
                log_entry = LogEntry(message, source, destination, timestamp)
                log_entry.undo_requested.connect(self.handle_undo)
                log_entry.redo_requested.connect(self.handle_redo)
                self.log_entries.append(log_entry.to_dict())
            else:
                # Create simple log entry without buttons for undo/redo operations
                log_entry = LogEntry(message, source, destination, timestamp)
                self.log_entries.append(log_entry.to_dict())
        else:
            # Create simple log entry for messages without source/destination
            log_entry = LogEntry(message, None, None, timestamp)
            self.log_entries.append(log_entry.to_dict())
            
        self.logs_container_layout.addWidget(log_entry)
        self.save_logs()
            
    def handle_undo(self, source, destination):
        """Handle undo request from log entry"""
        try:
            if os.path.exists(source):
                # Move the file back to original directory with (Undo) suffix
                shutil.move(source, destination)
                self.log(f"Moved back to original location: {os.path.basename(destination)} (Undo)", 
                        destination, source)  # Swap source and destination for next operation
            else:
                self.log(f"Undo failed: File not found at {source} (Undo)")
        except Exception as e:
            self.log(f"Undo error: {str(e)} (Undo)")

    def handle_redo(self, source, destination):
        """Handle redo request from log entry"""
        try:
            if os.path.exists(source):
                # Move from undo location back to original destination
                shutil.move(source, destination)
                self.log(f"Moved back to: {os.path.dirname(destination)} (Redo)", 
                        source, destination)
            else:
                self.log(f"Redo failed: File not found at {source} (Redo)")
        except Exception as e:
            self.log(f"Redo error: {str(e)} (Redo)")
            
    def save_logs(self):
        """Save logs to file"""
        try:
            with open(LOGS_FILE, 'w') as f:
                json.dump(self.log_entries, f)
        except Exception as e:
            print(f"Error saving logs: {str(e)}")
            
    def load_logs(self):
        """Load logs from file"""
        if not os.path.exists(LOGS_FILE):
            return
            
        try:
            with open(LOGS_FILE, 'r') as f:
                logs_data = json.load(f)
                
            for log_data in logs_data:
                log_entry = LogEntry(
                    message=log_data.get("message", ""),
                    source=log_data.get("original_source"),
                    destination=log_data.get("original_destination"),
                    timestamp=log_data.get("timestamp"),
                    is_undone=log_data.get("is_undone", False)
                )
                
                if log_data.get("original_source") and log_data.get("original_destination"):
                    log_entry.current_location = log_data.get("current_location")
                    log_entry.undo_requested.connect(self.handle_undo)
                    log_entry.redo_requested.connect(self.handle_redo)
                    
                self.logs_container_layout.addWidget(log_entry)
                
            self.log_entries = logs_data
            self.check_all_file_status()
                
        except Exception as e:
            print(f"Error loading logs: {str(e)}")
            self.log(f"Error loading previous logs: {str(e)}")

    def export_logs(self):
        """Export logs to a file within a date range"""
        # Use the main application window as parent
        dialog = DateRangeDialog(self.parent_window if self.parent_window else self)
        if dialog.exec_() != QDialog.Accepted:
            return
            
        start_date, end_date = dialog.get_range()
        start_date_str = start_date.toString("yyyy-MM-dd hh:mm:ss")
        end_date_str = end_date.toString("yyyy-MM-dd hh:mm:ss")
        
        # Filter logs based on date range
        filtered_logs = []
        try:
            for log_entry in self.log_entries:
                log_dict = log_entry.to_dict()
                log_time = QDateTime.fromString(log_dict["timestamp"], "yyyy-MM-dd hh:mm:ss")
                if start_date <= log_time <= end_date:
                    filtered_logs.append(log_dict)
                else:
                    continue
        except ValueError as e:
            QMessageBox.warning(self, "Date Format Error", f"Error parsing date range: {str(e)}")
            return
        
        if not filtered_logs:
            QMessageBox.information(
                self, 
                "No Logs in Range", 
                f"No logs found between {start_date_str} and {end_date_str}."
            )
            return
            
        # Ask user for save location - use parent window to prevent flashing
        parent = self.parent_window if self.parent_window else self
        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            "Save Logs",
            os.path.expanduser("~/logs_export.json"),
            "JSON Files (*.json);;Text Files (*.txt);;All Files (*.*)"
        )
        
        if not file_path:
            return  # User cancelled
            
        try:
            # Determine format based on extension
            if file_path.lower().endswith('.json'):
                # Save as JSON
                with open(file_path, 'w') as f:
                    json.dump(filtered_logs, f, indent=2)
            else:
                # Save as plain text
                with open(file_path, 'w') as f:
                    for log in filtered_logs:
                        f.write(f"[{log.get('timestamp', '')}] {log.get('message', '')}\n")
                        
            QMessageBox.information(
                self, 
                "Export Successful", 
                f"Exported {len(filtered_logs)} logs to {file_path}"
            )
                
        except Exception as e:
            QMessageBox.warning(
                self, 
                "Export Error", 
                f"Failed to export logs: {str(e)}"
            ) 