#!/usr/bin/env python3
"""
File Name: main.py
Version: 1.0.0 (Master Controller)
Description: The central entry point that orchestrates all modules, initializes the app, and launches the GUI.
"""

import sys
import os

# إضافة المسار الجذر للـ imports (لضمان عمل الاستيرادات من المجلدات الفرعية)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ==========================================
# 1. استيراد المكونات (Imports)
# ==========================================
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMenuBar, QMenu
from PyQt6.QtCore import Qt

# استيراد الثيمات
from ui.theme_engine import ThemeEngine

# استيراد الخدمات والمستودعات
from repositories.device_repository import DeviceRepository
from services.device_service import DeviceService

# استيراد الصفحات (UI)
from ui.pages.device_management_page import DeviceManagementPage

# ==========================================
# 2. النافذة الرئيسية (Main Window Layout)
# ==========================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # تهيئة الثيم
        self.theme_engine = ThemeEngine()
        self.theme_engine.set_theme("Slate Dark") # الثيم الافتراضي
        
        self.setWindowTitle("AeroCage-XV5 | نظام إدارة الأجهزة")
        self.setMinimumSize(1000, 700)
        
        # تهيئة الخدمات (Dependency Injection)
        # نمرر الـ Repository للـ Service، والـ Service للصفحات عند الحاجة
        self.repo = DeviceRepository()
        self.service = DeviceService(self.repo)
        
        # إعداد الواجهة
        self._init_ui()
        self._apply_theme()
        
        # إعداد القائمة العلوية
        self._setup_menubar()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # شريط علوي بسيط (اختياري)
        header = QLabel("أهلاً بك في AeroCage-XV5")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("background-color: #2c3e50; color: white; padding: 10px; font-size: 18px; font-weight: bold;")
        main_layout.addWidget(header)

        # منطقة المحتوى (تعرض الصفحات المختلفة)
        self.content_area = QVBoxLayout()
        self.content_area.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(self.content_area)

        # إضافة صفحة إدارة الأجهزة كصفحة افتراضية
        self.device_page = DeviceManagementPage(service=self.service)
        self.content_area.addWidget(self.device_page)

        # شريط الحالة
        self.statusBar().showMessage("جاهز للعمل")

    def _apply_theme(self):
        """تطبيق الثيم المختار على كامل التطبيق"""
        stylesheet = self.theme_engine.get_stylesheet()
        self.setStyleSheet(stylesheet)

    def _setup_menubar(self):
        menubar = self.menuBar()
        
        # قائمة الملف
        file_menu = menubar.addMenu("الملف")
        exit_action = file_menu.addAction("خروج")
        exit_action.triggered.connect(qApp.quit)
        
        # قائمة الإعدادات (لتغيير الثيم مثلاً)
        settings_menu = menubar.addMenu("إعدادات")
        
        dark_action = settings_menu.addAction("الوضع المظلم (Slate Dark)")
        dark_action.triggered.connect(lambda: self._change_theme("Slate Dark"))
        
        light_action = settings_menu.addAction("الوضع الفاتح (Minimal Light)")
        light_action.triggered.connect(lambda: self._change_theme("Minimal Light"))

    def _change_theme(self, theme_name):
        self.theme_engine.set_theme(theme_name)
        self._apply_theme()
        self.statusBar().showMessage(f"تم تغيير الثيم إلى: {theme_name}")

# ==========================================
# 3. نقطة البداية (Entry Point)
# ==========================================

def main():
    # إنشاء تطبيق البايثون
    app = QApplication(sys.argv)
    
    # ضبط خط النظام (اختياري لتحسين المظهر)
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # إنشاء النافذة الرئيسية
    window = MainWindow()
    window.show()

    # تشغيل حلقة الأحداث
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
