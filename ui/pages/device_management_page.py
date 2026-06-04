#!/usr/bin/env python3
"""
File Name: ui/pages/device_management_page.py
Version: 1.1.0 (Corrected & Smart Integrated)
Description: Advanced Device Management with Groups, Connection Testing, and Smart Actions.
"""
import sys
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QLineEdit, QComboBox, QMessageBox, QHeaderView, QInputDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

# Add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repositories.device_repository import DeviceRepository
from core.ssh_connector import SSHConnector, SSHError
from core.security import decrypt_data
from utils.logger import get_logger

logger = get_logger(__name__)

class ConnectionWorker(QThread):
    """Thread for testing connection without blocking UI."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, ip, user, password):
        super().__init__()
        self.ip = ip
        self.user = user
        self.password = password

    def run(self):
        try:
            if not self.password:
                self.error.emit("No password provided")
                return
            
            with SSHConnector(hostname=self.ip, username=self.user, password=self.password, timeout=5) as ssh:
                exit_code, stdout, stderr = ssh.execute_command("echo 'alive'", timeout=5)
                if exit_code == 0:
                    self.finished.emit({"status": "success", "msg": "Connected", "output": stdout.strip()})
                else:
                    self.finished.emit({"status": "warning", "msg": f"Command failed: {stderr.strip()}"})
        except SSHError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {str(e)}")

class DeviceManagementPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = DeviceRepository()
        self.logger = get_logger(__name__)
        self._init_ui()
        self._load_devices()
        self._refresh_group_combo()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Top Bar
        top_layout = QHBoxLayout()
        self.btn_add = QPushButton("➕ إضافة جهاز")
        self.btn_add.clicked.connect(self._show_add_dialog)
        top_layout.addWidget(self.btn_add)
        
        self.btn_add_group = QPushButton("➕ إضافة مجموعة")
        self.btn_add_group.clicked.connect(self._show_add_group_dialog)
        top_layout.addWidget(self.btn_add_group)
        
        top_layout.addStretch()
        
        # Filter
        self.combo_group_filter = QComboBox()
        self.combo_group_filter.addItem("جميع المجموعات", -1)
        self.combo_group_filter.currentIndexChanged.connect(self._load_devices)
        top_layout.addWidget(QLabel("📁 المجموعة:"))
        top_layout.addWidget(self.combo_group_filter)
        
        layout.addLayout(top_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "الاسم", "IP", "المجموعة", "الحالة", "البصمة", "تحكم"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._handle_selection)
        layout.addWidget(self.table)
        
        # Bottom Action Bar
        action_layout = QHBoxLayout()
        self.btn_test_conn = QPushButton("⚡ اختبار الاتصال")
        self.btn_test_conn.clicked.connect(self._test_selected_connection)
        self.btn_test_conn.setEnabled(False)
        
        self.btn_smart_scan = QPushButton("🔍 فحص ذكي")
        self.btn_smart_scan.clicked.connect(self._smart_scan_selected)
        self.btn_smart_scan.setEnabled(False)
        
        self.btn_analyze = QPushButton("🧬 تحليل بصمة")
        self.btn_analyze.clicked.connect(self._analyze_selected)
        self.btn_analyze.setEnabled(False)
        
        self.btn_delete = QPushButton("🗑️ حذف")
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_delete.setEnabled(False)
        
        action_layout.addWidget(self.btn_test_conn)
        action_layout.addWidget(self.btn_smart_scan)
        action_layout.addWidget(self.btn_analyze)
        action_layout.addWidget(self.btn_delete)
        action_layout.addStretch()
        
        self.lbl_status = QLabel("جاهز")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #2ecc71;")
        action_layout.addWidget(self.lbl_status)
        
        layout.addLayout(action_layout)

    def _load_devices(self):
        group_id = self.combo_group_filter.currentData()
        devices = self.repo.get_all_devices()
        
        self.table.setRowCount(0)
        
        for dev in devices:
            # dev structure: (id, name, ip, user, pass_enc, group_id, group_name, status, bands)
            dev_id, name, ip, user, pass_enc, g_id, g_name, status, bands = dev
            
            # Filter
            if group_id != -1 and g_id != group_id:
                continue
                
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Populate items
            self.table.setItem(row, 0, QTableWidgetItem(str(dev_id)))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(ip))
            self.table.setItem(row, 3, QTableWidgetItem(g_name or "-"))
            
            # Status Color
            status_item = QTableWidgetItem(status)
            if status == "Online":
                status_item.setBackground(QColor("#2ecc71"))
                status_item.setForeground(QColor("white"))
            elif status == "Offline":
                status_item.setBackground(QColor("#e74c3c"))
                status_item.setForeground(QColor("white"))
            else:
                status_item.setBackground(QColor("#f1c40f"))
                status_item.setForeground(QColor("black"))
            self.table.setItem(row, 4, status_item)
            
            # Fingerprint (Placeholder)
            self.table.setItem(row, 5, QTableWidgetItem("-")) 
            
            # Control Button
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn = QPushButton("⚙️")
            btn.setFixedSize(30, 30)
            btn.clicked.connect(lambda checked, d_id=dev_id: self._show_device_actions(d_id))
            btn_layout.addWidget(btn)
            self.table.setCellWidget(row, 6, btn_container)
            
        self._refresh_group_combo()

    def _refresh_group_combo(self):
        self.combo_group_filter.blockSignals(True)
        current = self.combo_group_filter.currentText()
        self.combo_group_filter.clear()
        self.combo_group_filter.addItem("جميع المجموعات", -1)
        groups = self.repo.get_all_groups()
        for gid, gname in groups:
            self.combo_group_filter.addItem(gname, gid)
        idx = self.combo_group_filter.findText(current)
        self.combo_group_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.combo_group_filter.blockSignals(False)

    def _handle_selection(self):
        selected = self.table.selectedRanges()
        has_selection = len(selected) > 0
        self.btn_test_conn.setEnabled(has_selection)
        self.btn_smart_scan.setEnabled(has_selection)
        self.btn_analyze.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)

    def _show_add_dialog(self):
        # Simple inline dialog for adding device
        name, ok1 = QInputDialog.getText(self, "إضافة جهاز", "اسم الجهاز:")
        if not ok1 or not name: return
        
        ip, ok2 = QInputDialog.getText(self, "إضافة جهاز", "عنوان IP:")
        if not ok2 or not ip: return
        
        user, ok3 = QInputDialog.getText(self, "إضافة جهاز", "اسم المستخدم (root):", text="root")
        if not ok3: return
        
        password, ok4 = QInputDialog.getText(self, "إضافة جهاز", "كلمة المرور:", echo=QLineEdit.EchoMode.Password)
        if not ok4: return
        
        group_name, ok5 = QInputDialog.getText(self, "إضافة جهاز", "المجموعة (اختياري):")
        
        if self.repo.create_device(name, ip, user, password, None): # Group logic simplified
            self._load_devices()
            self.lbl_status.setText("✅ تم إضافة الجهاز بنجاح")
        else:
            self.lbl_status.setText("❌ فشل الإضافة (IP مكرر؟)")

    def _show_add_group_dialog(self):
        name, ok = QInputDialog.getText(self, "إضافة مجموعة", "اسم المجموعة:")
        if ok and name:
            if self.repo.create_group(name):
                self._refresh_group_combo()
                self.lbl_status.setText(f"✅ تم إنشاء المجموعة: {name}")
            else:
                self.lbl_status.setText("❌ فشل إنشاء المجموعة")

    def _test_selected_connection(self):
        selected = self.table.selectedRanges()
        if not selected: return
        row = selected.topRow()
        dev_id = int(self.table.item(row, 0).text())
        
        device = self.repo.get_device_by_id(dev_id)
        if not device: return
        
        _, _, ip, user, pass_enc, _, _, _, _ = device
        password = decrypt_data(pass_enc) if pass_enc else None
        
        if not password:
            QMessageBox.warning(self, "تحذير", "لا توجد كلمة مرور محفوظة لهذا الجهاز.")
            return

        self.lbl_status.setText("⏳ جاري اختبار الاتصال...")
        self.btn_test_conn.setEnabled(False)
        
        worker = ConnectionWorker(ip, user, password)
        worker.finished.connect(lambda res: self._on_check_done(res, worker))
        worker.error.connect(lambda err: self._on_check_done({"status": "error", "msg": err}, worker))
        worker.start()

    def _smart_scan_selected(self):
        # Placeholder for smart scan logic (reuse test connection with retries)
        self._test_selected_connection() # For now, same as test

    def _analyze_selected(self):
        # Placeholder for fingerprinting
        QMessageBox.information(self, "تحليل", "ميزة تحليل البصمة قيد التطوير.")

    def _on_check_done(self, result, worker):
        self.btn_test_conn.setEnabled(True)
        if result["status"] == "success":
            self.lbl_status.setText(f"✅ اتصال ناجح: {result['msg']}")
            # Update status in DB
            selected = self.table.selectedRanges()
            if selected:
                row = selected.topRow()
                dev_id = int(self.table.item(row, 0).text())
                self.repo.update_device_status(dev_id, "Online")
                self._load_devices() # Refresh to show new status
        else:
            self.lbl_status.setText(f"❌ فشل الاتصال: {result.get('msg', 'Unknown')}")
            # Update status in DB
            selected = self.table.selectedRanges()
            if selected:
                row = selected.topRow()
                dev_id = int(self.table.item(row, 0).text())
                self.repo.update_device_status(dev_id, "Offline")
                self._load_devices()

    def _delete_selected(self):
        selected = self.table.selectedRanges()
        if not selected: return
        row = selected.topRow()
        dev_id = int(self.table.item(row, 0).text())
        
        reply = QMessageBox.question(self, "تأكيد الحذف", "هل أنت متأكد من حذف هذا الجهاز؟", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.repo.delete_device(dev_id):
                self._load_devices()
                self.lbl_status.setText("✅ تم الحذف بنجاح")
            else:
                self.lbl_status.setText("❌ فشل الحذف")

    def _show_device_actions(self, dev_id):
        QMessageBox.information(self, "الإجراءات", f"قائمة إجراءات الجهاز ID: {dev_id}\n(قريباً)")
