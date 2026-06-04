#!/usr/bin/env python3
"""
File Name: ui/pages/device_management_page.py
Description: Advanced Device Management with Groups, Sequential ID, and Connection Testing.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QLineEdit, QComboBox, QMessageBox, QHeaderView, QSplitter)
from PyQt6.QtCore import Qt
from repositories.device_repository import DeviceRepository
from core.ssh_worker import SSHWorker
from utils.logger import AeroLogger
import re

class DeviceManagementPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = DeviceRepository()
        self.logger = AeroLogger.get_logger()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Top Bar
        top_layout = QHBoxLayout()
        self.btn_add = QPushButton("➕ إضافة جهاز/مجموعة")
        self.btn_add.clicked.connect(self._show_add_dialog)
        top_layout.addWidget(self.btn_add)
        top_layout.addStretch()
        
        # Filter
        self.combo_group_filter = QComboBox()
        self.combo_group_filter.addItem("جميع المجموعات", -1)
        self.combo_group_filter.currentIndexChanged.connect(self._load_devices)
        top_layout.addWidget(QLabel("📁 تصفية حسب المجموعة:"))
        top_layout.addWidget(self.combo_group_filter)
        
        layout.addLayout(top_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "الاسم", "IP", "المجموعة", "الحالة", "تحكم"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._handle_selection)
        layout.addWidget(self.table)
        
        # Bottom Action Bar
        action_layout = QHBoxLayout()
        self.btn_test_conn = QPushButton("⚡ فحص الاتصال")
        self.btn_test_conn.clicked.connect(self._test_selected_connection)
        self.btn_test_conn.setEnabled(False)
        self.btn_delete = QPushButton("🗑️ حذف")
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_delete.setEnabled(False)
        
        action_layout.addWidget(self.btn_test_conn)
        action_layout.addWidget(self.btn_delete)
        action_layout.addStretch()
        
        self.lbl_status = QLabel("جاهز")
        action_layout.addWidget(self.lbl_status)
        
        layout.addLayout(action_layout)
        
        self._load_devices()
        self._refresh_group_combo()

    def _load_devices(self):
        group_id = self.combo_group_filter.currentData()
        devices = self.repo.get_all_devices()
        
        self.table.setRowCount(0)
        
        for dev in devices:
            # dev: (id, name, ip, user, pass, group_id, group_name, status, bands)
            if group_id != -1 and dev != group_id:
                continue
                
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(str(dev)))
            self.table.setItem(row, 1, QTableWidgetItem(dev))
            self.table.setItem(row, 2, QTableWidgetItem(dev))
            self.table.setItem(row, 3, QTableWidgetItem(dev or "بدون مجموعة"))
            
            status_item = QTableWidgetItem("Active" if dev == "Active" else "Offline")
            status_item.setForeground(Qt.GlobalColor.green if dev == "Active" else Qt.GlobalColor.red)
            self.table.setItem(row, 4, status_item)
            
            # Control Button
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn = QPushButton("⚙️")
            btn.setFixedSize(30, 30)
            btn.clicked.connect(lambda checked, d_id=dev: self._show_device_actions(d_id))
            btn_layout.addWidget(btn)
            self.table.setCellWidget(row, 5, btn_container)
            
        self._refresh_group_combo()

    def _refresh_group_combo(self):
        self.combo_group_filter.blockSignals(True)
        current = self.combo_group_filter.currentText()
        self.combo_group_filter.clear()
        self.combo_group_filter.addItem("جميع المجموعات", -1)
        groups = self.repo.db.get_all_groups()
        for gid, gname in groups:
            self.combo_group_filter.addItem(gname, gid)
        # Restore selection
        idx = self.combo_group_filter.findText(current)
        self.combo_group_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.combo_group_filter.blockSignals(False)

    def _handle_selection(self):
        selected = self.table.selectedRanges()
        if selected:
            self.btn_test_conn.setEnabled(True)
            self.btn_delete.setEnabled(True)
        else:
            self.btn_test_conn.setEnabled(False)
            self.btn_delete.setEnabled(False)

    def _show_add_dialog(self):
        from ui.device_dialog import DeviceDialog
        dialog = DeviceDialog(self)
        dialog.exec()
        self._load_devices()

    def _test_selected_connection(self):
        selected = self.table.selectedRanges()
        if not selected: return
        
        row = selected.topRow()
        dev_id = int(self.table.item(row, 0).text())
        
        device = self.repo.get_device_by_id(dev_id)
        if not device: return
        
        ip, user, pwd = device, device, device
        
        self.lbl_status.setText("⏳ جاري فحص الاتصال...")
        
        # Async check
        worker = SSHWorker(ip, user, pwd)
        worker.finished.connect(lambda: self._on_check_done(worker.result))
        worker.error.connect(lambda e: self._on_check_done({"status": "error", "msg": str(e)}))
        worker.start()

    def _on_check_done(self, result):
        if result["status"] == "success":
            self.lbl_status.setText(f"✅ اتصال ناجح: {result['msg']}")
            # Update status in DB if needed
        else:
            self.lbl_status.setText(f"❌ فشل الاتصال: {result.get('msg', 'Unknown')}")

    def _delete_selected(self):
        selected = self.table.selectedRanges()
        if not selected: return
        
        row = selected.topRow()
        dev_id = int(self.table.item(row, 0).text())
        
        reply = QMessageBox.question(self, "تأكيد الحذف", "هل أنت متأكد من حذف هذا الجهاز؟ سيتم إعادة ترقيم الباقي.", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.repo.delete_device(dev_id):
                self._load_devices()
                self.lbl_status.setText("✅ تمت العملية بنجاح")
            else:
                self.lbl_status.setText("❌ فشل الحذف")

    def _show_device_actions(self, dev_id):
        # Placeholder for future actions (Update, etc.)
        QMessageBox.information(self, "إجراءات", f"إجراءات الجهاز ID: {dev_id} قادمة قريباً")

    def _load_groups(self):
        # Helper to populate group combo
        pass
