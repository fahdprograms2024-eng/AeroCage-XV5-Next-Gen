#!/usr/bin/env python3
"""
File Name: main_window.py
Version: 1.0.0 | Status: Active
Purpose: Main GUI for AeroCage-XV5.
         Provides a smart, user-controlled interface for device management.
"""
import sys
import logging
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, 
                             QLabel, QMessageBox, QHeaderView, QStatusBar, QSplitter,
                             QFrame, QDialog, QDialogButtonBox, QLineEdit, QTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

# Import Service Layer
from services.device_service import DeviceService
from utils.logger import get_logger

logger = get_logger(__name__)

class ScanWorker(QThread):
    """Thread for running scans in background to keep UI responsive."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, service, device_id, action_type):
        super().__init__()
        self.service = service
        self.device_id = device_id
        self.action_type = action_type # 'scan', 'fingerprint', 'heal'

    def run(self):
        try:
            if self.action_type == 'scan':
                result = self.service.execute_smart_scan(self.device_id)
            elif self.action_type == 'fingerprint':
                result = self.service.execute_device_fingerprint(self.device_id)
            elif self.action_type == 'heal':
                # Placeholder for healing logic (e.g., restart sshd)
                result = {"success": True, "message": "Healing action simulated."}
            else:
                result = {"success": False, "error": "Unknown action"}
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.service = DeviceService()
        self.setWindowTitle("AeroCage-XV5 - Smart Control Center")
        self.setGeometry(100, 100, 1200, 800)
        
        self.init_ui()
        self.refresh_device_list()

    def init_ui(self):
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Header
        header = QLabel("🛡️ AeroCage-XV5: Smart Device Management")
        header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Stats Bar
        self.stats_label = QLabel("Loading stats...")
        self.stats_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.stats_label)

        # Splitter for Table and Logs
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Device Table
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "IP", "User", "Group", "Status", "Actions", "Details"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table_layout.addWidget(self.table)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Refresh All")
        self.btn_refresh.clicked.connect(self.refresh_device_list)
        btn_layout.addWidget(self.btn_refresh)
        
        self.btn_smart_scan_all = QPushButton("🚀 Smart Scan All")
        self.btn_smart_scan_all.clicked.connect(self.smart_scan_all_devices)
        btn_layout.addWidget(self.btn_smart_scan_all)
        
        table_layout.addLayout(btn_layout)
        splitter.addWidget(table_widget)

        # Log/Status Area
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setPlaceholderText("System logs and smart suggestions will appear here...")
        log_layout.addWidget(self.log_display)
        splitter.addWidget(log_widget)

        splitter.setSizes([600, 200])
        layout.addWidget(splitter)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def log_message(self, message, level="INFO"):
        """Adds a message to the log display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        self.log_display.append(log_entry)
        logger.info(message)

    def refresh_device_list(self):
        """Refreshes the device table from the service."""
        self.table.setRowCount(0)
        devices = self.service.get_all_devices()
        health = self.service.get_network_health()
        
        # Update Stats
        status_text = f"Total: {health['total']} | Online: {health['online']} | Offline: {health['offline']} | Health: {health['health']}"
        self.stats_label.setText(status_text)
        self.status_bar.showMessage(f"Network Health: {health['status']}")

        for row, dev in enumerate(devices):
            self.table.insertRow(row)
            
            # Data
            items = [
                QTableWidgetItem(dev["id"] [:8] + "..."), # Truncate ID
                QTableWidgetItem(dev["name"]),
                QTableWidgetItem(dev["ip"]),
                QTableWidgetItem(dev["user"]),
                QTableWidgetItem(dev["group_name"] or "-"),
                QTableWidgetItem(dev["status"])
            ]
            
            # Color code status
            status = dev["status"]
            if status == "Online":
                items.setBackground(QColor("#d4edda")) # Green
            elif status == "Offline":
                items.setBackground(QColor("#f8d7da")) # Red
            else:
                items.setBackground(QColor("#fff3cd")) # Yellow

            for i, item in enumerate(items):
                self.table.setItem(row, i, item)

            # Action Buttons Column (7)
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0)

            # Smart Scan Button
            btn_scan = QPushButton("🔍 Scan")
            btn_scan.setToolTip("Perform smart scan with retries")
            btn_scan.clicked.connect(lambda checked, r=row: self.on_scan_clicked(r))
            btn_layout.addWidget(btn_scan)

            # Fingerprint Button
            btn_fp = QPushButton("🧬 Analyze")
            btn_fp.setToolTip("Identify device type/OS")
            btn_fp.clicked.connect(lambda checked, r=row: self.on_analyze_clicked(r))
            btn_layout.addWidget(btn_fp)

            # Heal Button (Only if Offline)
            btn_heal = QPushButton("🛠️ Heal")
            if status == "Offline":
                btn_heal.setToolTip("Attempt to restart SSH service")
                btn_heal.clicked.connect(lambda checked, r=row: self.on_heal_clicked(r))
            else:
                btn_heal.setEnabled(False)
                btn_heal.setToolTip("Device is Online")
            btn_layout.addWidget(btn_heal)

            self.table.setCellWidget(row, 6, btn_container)
            
            # Details (Empty for now)
            self.table.setItem(row, 7, QTableWidgetItem(""))

    def on_scan_clicked(self, row):
        device_id = self.table.item(row, 0).text()
        # Show confirmation dialog
        reply = QMessageBox.question(self, 'Confirm Smart Scan', 
            f"Are you sure you want to perform a Smart Scan on device {device_id}?\n"
            "This will attempt to connect up to 3 times with delays.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log_message(f"Initiating Smart Scan for {device_id}...")
            self.run_background_task(device_id, 'scan')

    def on_analyze_clicked(self, row):
        device_id = self.table.item(row, 0).text()
        reply = QMessageBox.question(self, 'Confirm Analysis', 
            f"Identify device type and OS for {device_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log_message(f"Analyzing device {device_id}...")
            self.run_background_task(device_id, 'fingerprint')

    def on_heal_clicked(self, row):
        device_id = self.table.item(row, 0).text()
        reply = QMessageBox.question(self, 'Confirm Healing', 
            f"Attempt to restart SSH service on {device_id}?\n"
            "This requires root privileges and may interrupt current connections.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log_message(f"Initiating Healing for {device_id}...")
            self.run_background_task(device_id, 'heal')

    def run_background_task(self, device_id, action):
        self.worker = ScanWorker(self.service, device_id, action)
        self.worker.finished.connect(self.on_task_finished)
        self.worker.error.connect(self.on_task_error)
        self.worker.start()
        self.status_bar.showMessage(f"Running {action} for {device_id}...")

    def on_task_finished(self, result):
        if result.get("success"):
            self.log_message(f"Task completed successfully: {result.get('message', 'OK')}")
            if "fingerprint" in result:
                self.log_message(f"Fingerprint: {result['fingerprint']}")
            self.refresh_device_list()
        else:
            self.log_message(f"Task failed: {result.get('error', 'Unknown error')}", "WARNING")
        self.status_bar.showMessage("Ready")

    def on_task_error(self, error_msg):
        self.log_message(f"Error during task: {error_msg}", "ERROR")
        QMessageBox.critical(self, "Error", f"Task failed: {error_msg}")
        self.status_bar.showMessage("Ready")

    def smart_scan_all_devices(self):
        reply = QMessageBox.question(self, 'Confirm Full Scan', 
            "Are you sure you want to Smart Scan ALL devices?\n"
            "This may take some time.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log_message("Starting Smart Scan for all devices...")
            # For simplicity, we scan sequentially in a thread
            # In a real app, use a thread pool
            devices = self.service.get_all_devices()
            for dev in devices:
                self.run_background_task(dev["id"], 'scan')
                QThread.msleep(100) # Small delay to avoid UI freeze

if __name__ == "__main__":
    from datetime import datetime
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
