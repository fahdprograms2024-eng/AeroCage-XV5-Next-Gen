#!/usr/bin/env python3
"""
File Name: ui/pages/wireless_query_page.py
Description: Dynamic Query Interface for Wireless Data (Clients, Interfaces, Bands).
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QTableWidget, 
                             QTableWidgetItem, QPushButton, QSplitter, QMessageBox, QHeaderView, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt
from repositories.device_repository import DeviceRepository
from services.wireless_manager import WirelessManagerService
from utils.logger import AeroLogger

class WirelessQueryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = DeviceRepository()
        self.wireless_service = WirelessManagerService()
        self.logger = AeroLogger.get_logger()
        self.current_dev_id = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Top Filter Bar
        filter_layout = QHBoxLayout()
        
        # Scope
        self.lbl_scope = QLabel("🎯 النطاق:")
        filter_layout.addWidget(self.lbl_scope)
        
        self.radio_all = QRadioButton("الكل")
        self.radio_group = QRadioButton("المجموعة")
        self.radio_device = QRadioButton("جهاز محدد")
        
        self.radio_group_btns = QButtonGroup(self)
        self.radio_group_btns.addButton(self.radio_all)
        self.radio_group_btns.addButton(self.radio_group)
        self.radio_group_btns.addButton(self.radio_device)
        
        self.radio_all.setChecked(True)
        self.radio_all.toggled.connect(self._on_scope_change)
        self.radio_group.toggled.connect(self._on_scope_change)
        self.radio_device.toggled.connect(self._on_scope_change)
        
        filter_layout.addWidget(self.radio_all)
        filter_layout.addWidget(self.radio_group)
        filter_layout.addWidget(self.radio_device)
        
        # Selector (Dynamic)
        self.combo_selector = QComboBox()
        self.combo_selector.setEnabled(False)
        self.combo_selector.currentIndexChanged.connect(self._load_data)
        filter_layout.addWidget(self.combo_selector)
        
        # Band Filter
        self.lbl_band = QLabel("📶 التردد:")
        filter_layout.addWidget(self.lbl_band)
        
        self.combo_band = QComboBox()
        self.combo_band.addItems(["جميع الترددات", "2.4 GHz", "5 GHz"])
        self.combo_band.currentIndexChanged.connect(self._load_data)
        filter_layout.addWidget(self.combo_band)
        
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # Splitter for Results
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Top Table: Interfaces & Info
        self.interfaces_table = QTableWidget()
        self.interfaces_table.setColumnCount(4)
        self.interfaces_table.setHorizontalHeaderLabels(["الواجهة / SSID", "التردد / القناة", "الحالة", "الزبائن"])
        self.interfaces_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.interfaces_table.itemSelectionChanged.connect(self._on_interface_select)
        splitter.addWidget(self.interfaces_table)
        
        # Bottom Table: Clients
        self.clients_table = QTableWidget()
        self.clients_table.setColumnCount(5)
        self.clients_table.setHorizontalHeaderLabels(["MAC Address", "Signal (dBm)", "Noise (dBm)", "RX Rate", "TX Rate"])
        self.clients_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.clients_table)
        
        layout.addWidget(splitter)
        
        # Actions
        action_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 تحديث")
        self.btn_refresh.clicked.connect(self._load_data)
        action_layout.addWidget(self.btn_refresh)
        layout.addLayout(action_layout)
        
        self._load_data()

    def _on_scope_change(self):
        self.combo_selector.blockSignals(True)
        self.combo_selector.clear()
        self.combo_selector.setEnabled(False)
        
        if self.radio_all.isChecked():
            pass
        elif self.radio_group.isChecked():
            self.combo_selector.setEnabled(True)
            groups = self.repo.db.get_all_groups()
            for gid, gname in groups:
                self.combo_selector.addItem(gname, ("group", gid))
        elif self.radio_device.isChecked():
            self.combo_selector.setEnabled(True)
            devices = self.repo.get_all_devices()
            for dev in devices:
                self.combo_selector.addItem(f"{dev} ({dev})", ("device", dev))
        
        self.combo_selector.blockSignals(False)
        self._load_data()

    def _load_data(self):
        self.interfaces_table.setRowCount(0)
        self.clients_table.setRowCount(0)
        
        selected_data = self.combo_selector.currentData()
        band_filter = self.combo_band.currentText()
        
        # Get Devices
        devices = self.repo.get_all_devices()
        
        for dev in devices:
            dev_id, name, ip, user, pwd, _, g_name, status, bands = dev
            
            # Filter by Scope
            if selected_data:
                scope_type, scope_id = selected_data
                if scope_type == "group" and dev != scope_id:
                    continue
                if scope_type == "device" and dev_id != scope_id:
                    continue
            
            # Filter by Band
            if band_filter == "2.4 GHz" and "2G" not in str(bands).upper():
                continue
            if band_filter == "5 GHz" and "5G" not in str(bands).upper():
                continue
            
            # Fetch Data for this Device
            self._fetch_device_data(dev_id, ip, user, pwd)

    def _fetch_device_data(self, dev_id, ip, user, pwd):
        try:
            # Use SSHConnector or WirelessManagerService to fetch data
            # This is a placeholder for the actual SSH logic
            # The logic from report_view.py is reused here
            self.logger.info(f"Fetching data for {ip}")
            
            # Simulate data fetch (Replace with actual SSH call)
            # For now, we just add a placeholder row
            row = self.interfaces_table.rowCount()
            self.interfaces_table.insertRow(row)
            self.interfaces_table.setItem(row, 0, QTableWidgetItem(f"radio0 (Default)"))
            self.interfaces_table.setItem(row, 1, QTableWidgetItem("2.4 GHz / Ch 6"))
            self.interfaces_table.setItem(row, 2, QTableWidgetItem("Active"))
            self.interfaces_table.setItem(row, 3, QTableWidgetItem("0"))
            
            # Simulate clients
            c_row = self.clients_table.rowCount()
            self.clients_table.insertRow(c_row)
            self.clients_table.setItem(c_row, 0, QTableWidgetItem("AA:BB:CC:DD:EE:FF"))
            self.clients_table.setItem(c_row, 1, QTableWidgetItem("-45"))
            self.clients_table.setItem(c_row, 2, QTableWidgetItem("-90"))
            self.clients_table.setItem(c_row, 3, QTableWidgetItem("300.0"))
            self.clients_table.setItem(c_row, 4, QTableWidgetItem("300.0"))
            
        except Exception as e:
            self.logger.exception(f"Error fetching data for {ip}: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل جلب البيانات: {e}")

    def _on_interface_select(self):
        # Handle interface selection if needed
        pass
