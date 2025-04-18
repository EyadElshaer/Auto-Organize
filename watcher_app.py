from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QPushButton, QLabel, QFileDialog,
    QSystemTrayIcon, QMenu, QAction, QCheckBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QGroupBox,
    QLineEdit, QTabWidget, QHBoxLayout, QMessageBox, QScrollArea, QFrame
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, QDateTime, Qt
import sys, os, shutil, re, json, urllib.request, webbrowser

CONFIG_FILE = os.path.expanduser("~/.watcher_pairs_config.json")
AUTOSTART_PATH = os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\watcher_app.lnk")
VERSION_FILE = os.path.join(os.path.dirname(__file__), "version.txt")

def load_version():
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except:
        return "v0.0.0"

class WatcherApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Organizer")
        self.setWindowIcon(QIcon("icon.ico"))
        self.setGeometry(100, 100, 750, 500)
        self.load_config()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.init_main_tab()
        self.init_settings_tab()
        self.init_logs_tab()

        self.tray = QSystemTrayIcon(QIcon("icon.ico"), self)
        self.tray.setToolTip("Auto Organizer")
        tray_menu = QMenu()
        tray_menu.addAction(QAction("Open", self, triggered=self.restore_window))
        tray_menu.addAction(QAction("Exit", self, triggered=QApplication.quit))
        self.tray.setContextMenu(tray_menu)
        self.tray.show()

        self.timer = QTimer()
        self.timer.timeout.connect(self.scan_all_pairs)
        self.watching = False

        if self.config.get("minimize_on_startup", False):
            self.hide()

    def restore_window(self):
        self.showNormal()
        self.activateWindow()

    def init_main_tab(self):
        main_tab = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Watcher Pairs (Source → Target):"))
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Watch Folder", "Target Folder"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        for pair in self.config.get("watch_pairs", []):
            self.add_table_row(pair[0], pair[1])

        buttons = QHBoxLayout()
        btnAdd = QPushButton("+")
        btnAdd.clicked.connect(self.add_pair)
        btnRemove = QPushButton("-")
        btnRemove.clicked.connect(self.remove_pair)
        buttons.addWidget(btnAdd)
        buttons.addWidget(btnRemove)
        layout.addLayout(buttons)

        actions = QHBoxLayout()
        self.startBtn = QPushButton("Start")
        self.startBtn.clicked.connect(self.start_watching)
        self.stopBtn = QPushButton("Stop")
        self.stopBtn.setEnabled(False)
        self.stopBtn.clicked.connect(self.stop_watching)
        self.saveBtn = QPushButton("Save")
        self.saveBtn.clicked.connect(self.save_config)
        actions.addWidget(self.startBtn)
        actions.addWidget(self.stopBtn)
        actions.addWidget(self.saveBtn)
        layout.addLayout(actions)

        self.status = QLabel("Status: Stopped")
        layout.addWidget(self.status)

        main_tab.setLayout(layout)
        self.tabs.addTab(main_tab, "Watchers")

    def init_settings_tab(self):
        settings_tab = QWidget()
        layout = QVBoxLayout()
        group = QGroupBox("Preferences")
        g_layout = QVBoxLayout()

        self.run_startup_chk = QCheckBox("Run on Startup")
        self.run_startup_chk.setChecked(os.path.exists(AUTOSTART_PATH))
        g_layout.addWidget(self.run_startup_chk)

        self.minimize_chk = QCheckBox("Minimize to tray on launch")
        self.minimize_chk.setChecked(self.config.get("minimize_on_startup", False))
        g_layout.addWidget(self.minimize_chk)

        self.exit_on_close_chk = QCheckBox("Exit completely on close")
        self.exit_on_close_chk.setChecked(self.config.get("exit_on_close", False))
        g_layout.addWidget(self.exit_on_close_chk)

        self.separator_input = QLineEdit()
        self.separator_input.setText(self.config.get("separator_pattern", ",()[]-"))
        g_layout.addWidget(QLabel("Separator Pattern (e.g., ,()[]-):"))
        g_layout.addWidget(self.separator_input)

        group.setLayout(g_layout)
        layout.addWidget(group)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        update_btn = QPushButton("Check for Update")
        reset_btn = QPushButton("Reset Settings")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(update_btn)
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)

        save_btn.clicked.connect(self.save_settings)
        update_btn.clicked.connect(self.check_for_updates)
        reset_btn.clicked.connect(self.reset_settings)
        self.run_startup_chk.stateChanged.connect(self.toggle_autostart)

        settings_tab.setLayout(layout)
        self.tabs.addTab(settings_tab, "Settings")

    def init_logs_tab(self):
        logs_tab = QWidget()
        layout = QVBoxLayout()

        clear_btn = QPushButton("Clear All Logs")
        clear_btn.clicked.connect(self.clear_logs)
        layout.addWidget(clear_btn)

        self.logs_area = QScrollArea()
        self.logs_area.setWidgetResizable(True)
        self.logs_container = QWidget()
        self.logs_container_layout = QVBoxLayout()
        self.logs_container_layout.setAlignment(Qt.AlignTop)
        self.logs_container.setLayout(self.logs_container_layout)
        self.logs_area.setWidget(self.logs_container)

        layout.addWidget(self.logs_area)
        logs_tab.setLayout(layout)
        self.tabs.addTab(logs_tab, "Logs")

    def clear_logs(self):
        for i in reversed(range(self.logs_container_layout.count())):
            widget = self.logs_container_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def log(self, message, undo_data=None):
        log_entry = QFrame()
        layout = QHBoxLayout()
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        layout.addWidget(QLabel(f"[{timestamp}] {message}"))

        if undo_data:
            undo_btn = QPushButton("Undo")
            redo_btn = QPushButton("Redo")
            undo_btn.setFixedWidth(60)
            redo_btn.setFixedWidth(60)
            redo_btn.setEnabled(False)

            def undo_action():
                try:
                    os.makedirs(undo_data['src'], exist_ok=True)
                    shutil.move(os.path.join(undo_data['dest'], undo_data['filename']), os.path.join(undo_data['src'], undo_data['filename']))
                    redo_btn.setEnabled(True)
                    undo_btn.setEnabled(False)
                    self.log(f"Undone: {undo_data['filename']} → {undo_data['src']}")
                except Exception as e:
                    QMessageBox.warning(self, "Undo Failed", f"Error undoing move:\n{e}")

            def redo_action():
                try:
                    os.makedirs(undo_data['dest'], exist_ok=True)
                    shutil.move(os.path.join(undo_data['src'], undo_data['filename']), os.path.join(undo_data['dest'], undo_data['filename']))
                    redo_btn.setEnabled(False)
                    undo_btn.setEnabled(True)
                    self.log(f"Redone: {undo_data['filename']} → {undo_data['dest']}")
                except Exception as e:
                    QMessageBox.warning(self, "Redo Failed", f"Error redoing move:\n{e}")

            undo_btn.clicked.connect(undo_action)
            redo_btn.clicked.connect(redo_action)
            layout.addWidget(undo_btn)
            layout.addWidget(redo_btn)

        log_entry.setLayout(layout)
        log_entry.setFrameShape(QFrame.StyledPanel)
        self.logs_container_layout.addWidget(log_entry)

    def add_table_row(self, watch="", target=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(watch))
        self.table.setItem(row, 1, QTableWidgetItem(target))

    def add_pair(self):
        watch = QFileDialog.getExistingDirectory(self, "Select Watch Folder")
        if not watch: return
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder")
        if not target: return
        self.add_table_row(watch, target)

    def remove_pair(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def start_watching(self):
        if self.table.rowCount() == 0:
            self.status.setText("Add at least one watcher pair ❗")
            return
        self.watching = True
        self.timer.start(2000)
        self.status.setText("Status: Watching...")
        self.startBtn.setEnabled(False)
        self.stopBtn.setEnabled(True)

    def stop_watching(self):
        self.watching = False
        self.timer.stop()
        self.status.setText("Status: Stopped")
        self.startBtn.setEnabled(True)
        self.stopBtn.setEnabled(False)

    def save_config(self):
        pairs = [(self.table.item(row, 0).text(), self.table.item(row, 1).text()) for row in range(self.table.rowCount())]
        self.config["watch_pairs"] = pairs
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f)
        self.status.setText("Saved ✔")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {}
        self.config.setdefault("version", load_version())
        self.config.setdefault("separator_pattern", ",()[]-")
        self.config.setdefault("minimize_on_startup", False)
        self.config.setdefault("exit_on_close", False)

    def scan_all_pairs(self):
        for row in range(self.table.rowCount()):
            watch = self.table.item(row, 0).text()
            target = self.table.item(row, 1).text()
            if not os.path.isdir(watch) or not os.path.isdir(target):
                continue

            for item in os.listdir(watch):
                src = os.path.join(watch, item)
                if not os.path.exists(src): continue

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
                os.makedirs(dest_path, exist_ok=True)
                try:
                    shutil.move(src, os.path.join(dest_path, final_name))
                    self.log(
                        f"Moved: {item} → {dest_path}",
                        undo_data={"src": watch, "dest": dest_path, "filename": final_name}
                    )
                except Exception as e:
                    self.log(f"Error moving {item}: {e}")

    def save_settings(self):
        sep = self.separator_input.text().strip()
        if not sep or any(c in sep for c in r'\\/:*?"<>|'):
            QMessageBox.warning(self, "Invalid", "Separator contains illegal characters.")
            return
        self.config["separator_pattern"] = sep
        self.config["minimize_on_startup"] = self.minimize_chk.isChecked()
        self.config["exit_on_close"] = self.exit_on_close_chk.isChecked()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f)
        QMessageBox.information(self, "Saved", "Settings saved successfully.")

    def reset_settings(self):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        QMessageBox.information(self, "Reset", "Settings reset. Please restart the app.")
        self.close()

    def check_for_updates(self):
        try:
            with urllib.request.urlopen("https://api.github.com/repos/EyadElshaer/Auto-Organizer/releases/latest") as res:
                data = json.load(res)
                latest_version = data["tag_name"]
                current_version = self.config.get("version", "v0.0.0")
                if latest_version != current_version:
                    msg = QMessageBox(self)
                    msg.setWindowTitle("Update Available")
                    msg.setText(f"New version available: {latest_version}")
                    msg.setStandardButtons(QMessageBox.Ok)
                    update_btn = msg.addButton("Update Now", QMessageBox.ActionRole)
                    msg.exec_()
                    if msg.clickedButton() == update_btn:
                        webbrowser.open(data["html_url"])
                else:
                    QMessageBox.information(self, "Up to Date", "You're using the latest version.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to check for update:\n{str(e)}")

    def toggle_autostart(self):
        import winshell
        from win32com.client import Dispatch
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

    def closeEvent(self, event):
        if self.config.get("exit_on_close", False):
            event.accept()
        else:
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Auto Organizer",
                "Still running in the background. Right-click tray icon to exit.",
                QSystemTrayIcon.Information,
                3000
            )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WatcherApp()
    window.show()
    sys.exit(app.exec_())