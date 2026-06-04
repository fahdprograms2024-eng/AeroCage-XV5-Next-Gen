#!/usr/bin/env python3
"""
File Name: theme_engine.py
Purpose: Manages QSS Stylesheets for Dark/Light/Custom themes.
"""
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor

class ThemeEngine:
    """Manages the application's visual style."""
    
    THEMES = {
        "Slate Dark": """
            QMainWindow { background-color: #2c3e50; }
            QWidget { color: #ecf0f1; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QPushButton {
                background-color: #34495e; color: white; border-radius: 5px; padding: 6px 12px;
                border: 1px solid #34495e;
            }
            QPushButton:hover { background-color: #2980b9; }
            QLineEdit, QComboBox {
                background-color: #34495e; color: white; border: 1px solid #7f8c8d; border-radius: 4px;
            }
            QTableWidget { background-color: #34495e; alternate-background-color: #2c3e50; border: 1px solid #7f8c8d; }
            QHeaderView::section { background-color: #2c3e50; color: white; }
        """,
        
        "Minimal Light": """
            QMainWindow { background-color: #f5f5f5; }
            QWidget { color: #333; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QPushButton { background-color: #3498db; color: white; border-radius: 4px; padding: 6px 12px; }
            QLineEdit, QComboBox { background-color: white; border: 1px solid #ccc; color: #333; }
            QTableWidget { background-color: white; border: 1px solid #ccc; }
            QHeaderView::section { background-color: #f5f5f5; }
        """,
        
        "Calm Blue": """
            QMainWindow { background-color: #eef2f3; }
            QWidget { color: #4a5568; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QPushButton { background-color: #5a67d8; color: white; border-radius: 8px; padding: 8px 16px; }
            QLineEdit, QComboBox { background-color: white; border: 1px solid #cbd5e0; border-radius: 8px; }
            QTableWidget { background-color: white; border: 1px solid #cbd5e0; }
            QHeaderView::section { background-color: #eef2f3; color: #4a5568; }
        """,
        
        "Modern Purple": """
            QMainWindow { background-color: #1a1c20; }
            QWidget { color: #f3f4f6; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QPushButton { background-color: #7c3aed; color: white; border-radius: 5px; padding: 6px 12px; }
            QLineEdit, QComboBox { background-color: #374151; color: #f3f4f6; border: 1px solid #4b5563; }
            QTableWidgets { background-color: #1a1c20; border: 1px solid #374151; }
            QHeaderView::section { background-color: #1a1c20; color: #d1d5db; }
        """
    }

    @staticmethod
    def get_stylesheet(theme_name):
        return ThemeEngine.THEMES.get(theme_name, ThemeEngine.THEMES["Slate Dark"])
