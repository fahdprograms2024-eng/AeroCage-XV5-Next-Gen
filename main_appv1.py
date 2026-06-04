#!/usr/bin/env python3
"""
File Name: main_app.py
Version: 8.0.0 [AeroCage GUI Master]
Description: The central orchestrator for the AeroCage Desktop Application.
             Combines Sidebar, Multi-theme, Multi-lang, Device Management, and Reporting.
"""

import sys
import os
import logging
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QStatusBar, QMenu, QMenuBar, QMenuBar, QToolBar)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QAction, QIcon

# استيراد المكونات الداخلية (تأكد من وجود المسارات)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui.pages.device_management_page import DeviceManagementPage
from ui.pages.wireless_query_page import WirelessQueryPage
from ui.pages.operations_monitor_page import OperationsMonitorPage
from ui.themes.theme_engine import ThemeEngine
from utils.logger import AeroLogger

# تهيئة السجلات
logger = AeroLogger.get_logger()

class AeroCageMainWindow(QMainWindow):
    """
    المنسق الرسومي الأعلى (Master Window).
    يدير القائمة الجانبية (Sidebar)، التبويبات (Tabs)، والثيم واللغة.
    """

    def __init__(self):
        super().__init__()
        self.logger = logger
        self.current_lang = "AR"
        self.current_theme = "Slate Dark"
        
        # تهيئة المحرك الثيمي
        self.theme_engine = ThemeEngine()
        
        self._init_ui()
        self._apply_theme()
        self._apply_language()
        
        self.logger.info("🚀 AeroCage GUI v8.0.0 Initialized Successfully.")

    def _init_ui(self):
        self.setWindowTitle("AeroCage-XV8.0 | Security Suite")
        self.resize(1200, 800)
        
        # --- 1. القائمة العلوية (Menu Bar) ---
        self._create_menu_bar()
        
        # --- 2. شريط الأدوات (Toolbar) ---
        self._create_toolbar()

        # --- 3. الهيكل الرئيسي (Sidebar + Content) ---
        central_widget = QWidget()
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Sidebar
        self.sidebar = self._create_sidebar()
        layout.addWidget(self.sidebar)
        
        # Content Area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Control Bar (Top of Content)
        control_bar = QHBoxLayout()
        self.lbl_status = QLabel("حالة النظام: جاهز")
        self.lbl_status.setStyleSheet("color: #2ecc71; font-weight: bold;")
        control_bar.addWidget(self.lbl_status)
        control_bar.addStretch()
        self.lbl_lang_status = QLabel("AR | Dark")
        control_bar.addWidget(self.lbl_lang_status)
        
        content_layout.addLayout(control_bar)
        
        # Tabs Widget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        content_layout.addWidget(self.tabs)
        
        layout.addWidget(content_widget)
        self.setCentralWidget(central_widget)
        
        # Status Bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("جاهز للعمليات...")

        # --- 4. إضافة الصفحات الافتراضية ---
        self._add_default_pages()

    def _create_menu_bar(self):
        menubar = self.menuBar()
        
        # Menu: File
        file_menu = menubar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menu: View (Themes)
        view_menu = menubar.addMenu("View")
        theme_menu = view_menu.addMenu("Theme")
        themes = ["Slate Dark", "Minimal Light", "Calm Blue", "Modern Purple"]
        for theme in themes:
            action = QAction(theme, self)
            action.triggered.connect(lambda checked, t=theme: self._change_theme(t))
            theme_menu.addAction(action)
            
        # Menu: Help (Logs)
        help_menu = menubar.addMenu("Help")
        logs_action = QAction("Show System Logs", self)
        logs_action.triggered.connect(self._show_logs)
        help_menu.addAction(logs_action)

    def _create_toolbar(self):
        toolbar = self.addToolBar("Main Tools")
        toolbar.setMovable(False)
        
        btn_new_device = QAction("🛠️ Device Mgmt", self)
        btn_new_device.triggered.connect(self._open_device_page)
        toolbar.addAction(btn_new_device)
        
        toolbar.addSeparator()
        
        btn_query = QAction("📡 Wireless Query", self)
        btn_query.triggered.connect(self._open_query_page)
        toolbar.addAction(btn_query)

    def _create_sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background-color: #2c3e50; color: #ecf0f1;")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Logo Area
        logo_lbl = QLabel("AeroCage")
        logo_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #3498db;")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_lbl)
        
        layout.addSpacing(20)
        
        # Navigation Buttons
        self.nav_buttons = {}
        pages_config = [
            ("📊 Dashboard", "dashboard", self._open_dashboard),
            ("🛠️ Devices", "devices", self._open_device_page),
            ("📡 Wireless Query", "query", self._open_query_page),
            ("🔍 Operations", "ops", self._open_ops_page),
        ]
        
        for text, page_id, callback in pages_config:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, cb=callback: cb())
            btn.setStyleSheet("""
                QPushButton { 
                    background: none; border: none; text-align: left; padding: 10px; color: #bdc3c7; 
                }
                QPushButton:hover { background-color: #34495e; color: white; }
                QPushButton:checked { background-color: #3498db; color: white; font-weight: bold; }
            """)
            layout.addWidget(btn)
            self.nav_buttons[page_id] = btn
            
        layout.addStretch()
        
        # Settings Button
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setStyleSheet("background: none; border: none; text-align: left; padding: 10px; color: #bdc3c7;")
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn)
        
        return sidebar

    def _add_default_pages(self):
        # Dashboard
        dashboard = QWidget()
        dashboard_layout = QVBoxLayout(dashboard)
        dashboard_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dashboard_layout.addWidget(QLabel("👋 Welcome to AeroCage v8.0"))
        self.tabs.addTab(dashboard, "Dashboard")
        
        # Devices (Initially hidden, shown on click)
        self.device_page = DeviceManagementPage()
        self.tabs.addTab(self.device_page, "Device Management")
        
        # Query
        self.query_page = WirelessQueryPage()
        self.tabs.addTab(self.query_page, "Wireless Query")
        
        # Ops
        self.ops_page = OperationsMonitorPage()
        self.tabs.addTab(self.ops_page, "Operations Monitor")

    def _close_tab(self, index):
        if index > 0: # Keep dashboard
            self.tabs.removeTab(index)

    # --- Navigation Handlers ---
    def _open_dashboard(self):
        self.tabs.setCurrentIndex(0)
        self._update_nav_state("dashboard")

    def _open_device_page(self):
        # Reset index to 0, then add device page if not exists
        self._update_nav_state("devices")
        # Ensure the tab exists
        if not self.tabs.findChild(QWidget, "device_page_tab"):
            # Logic to ensure tab is visible
            pass
        # In a real app, we might swap tabs dynamically. 
        # For now, we assume tabs are pre-loaded or we add them dynamically.
        # Let's ensure the tab is active.
        for i in range(self.tabs.count()):
            if "Device Management" in self.tabs.tabText(i):
                self.tabs.setCurrentIndex(i)
                break

    def _open_query_page(self):
        for i in range(self.tabs.count()):
            if "Wireless Query" in self.tabs.tabText(i):
                self.tabs.setCurrentIndex(i)
                break

    def _open_ops_page(self):
        for i in range(self.tabs.count()):
            if "Operations Monitor" in self.tabs.tabText(i):
                self.tabs.setCurrentIndex(i)
                break

    def _update_nav_state(self, page_id):
        for pid, btn in self.nav_buttons.items():
            btn.setChecked(pid == page_id)

    # --- Theme & Language ---
    def _change_theme(self, theme_name):
        self.current_theme = theme_name
        self.theme_engine.set_theme(theme_name)
        self.setStyleSheet(self.theme_engine.get_stylesheet(theme_name))
        self.lbl_lang_status.setText(f"{self.current_lang} | {theme_name}")
        self.logger.info(f"Theme changed to: {theme_name}")

    def _apply_theme(self):
        self.setStyleSheet(self.theme_engine.get_stylesheet("Slate Dark"))

    def _show_logs(self):
        # Show a simple text dialog with logs or a dedicated log window
        log_window = QWidget()
        log_layout = QVBoxLayout(log_window)
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        log_text.setPlainText(self.logger.get_log_content()) # Assuming logger has this method
        log_layout.addWidget(log_text)
        log_window.setWindowTitle("System Logs")
        log_window.resize(600, 400)
        log_window.show()

    def _open_settings(self):
        QMessageBox.information(self, "Settings", "Settings module coming soon.")

    def closeEvent(self, event):
        self.logger.info("Application closing. Shutting down services...")
        event.accept()

# --- Entry Point ---
if __name__ == "__main__":
    # تهيئة الكونتينر (إذا كان هناك)
    # app = QApplication(sys.argv)
    # window = AeroCageMainWindow()
    # window.show()
    # sys.exit(app.exec())
    pass # Placeholder for testing
