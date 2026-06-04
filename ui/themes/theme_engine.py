# ui/themes/theme_engine.py
"""
Theme Engine for AeroCage-XV5
Provides dynamic stylesheet management for dark/light modes.
"""

class ThemeEngine:
    """Handles theme switching and stylesheet generation."""

    THEMES = {
        "Slate Dark": {
            "bg": "#2c3e50",
            "fg": "#ecf0f1",
            "accent": "#3498db",
            "panel": "#34495e",
            "success": "#2ecc71",
            "warning": "#f1c40f",
            "danger": "#e74c3c",
            "text_small": "#bdc3c7"
        },
        "Minimal Light": {
            "bg": "#f5f6fa",
            "fg": "#2c3e50",
            "accent": "#2980b9",
            "panel": "#ffffff",
            "success": "#27ae60",
            "warning": "#f39c12",
            "danger": "#c0392b",
            "text_small": "#7f8c8d"
        },
        "Calm Blue": {
            "bg": "#e8f4f8",
            "fg": "#2c3e50",
            "accent": "#1abc9c",
            "panel": "#ffffff",
            "success": "#16a085",
            "warning": "#f39c12",
            "danger": "#e74c3c",
            "text_small": "#5d6d7e"
        }
    }

    def __init__(self):
        self.current_theme = "Slate Dark"

    def set_theme(self, theme_name: str):
        if theme_name in self.THEMES:
            self.current_theme = theme_name

    def get_stylesheet(self, theme_name: str = None) -> str:
        if theme_name:
            self.current_theme = theme_name
        
        t = self.THEMES.get(self.current_theme, self.THEMES["Slate Dark"])
        
        return f"""
            QMainWindow, QDialog {{
                background-color: {t['bg']};
                color: {t['fg']};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }}
            QPushButton {{
                background-color: {t['accent']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t['accent']};
                opacity: 0.9;
            }}
            QPushButton:disabled {{
                background-color: {t['panel']};
                color: {t['text_small']};
            }}
            QTableWidget {{
                background-color: {t['panel']};
                color: {t['fg']};
                border: 1px solid {t['text_small']};
                gridline-color: {t['text_small']};
                alternate-background-color: {t['bg']};
            }}
            QHeaderView::section {{
                background-color: {t['accent']};
                color: white;
                padding: 4px;
                border: none;
            }}
            QTabWidget::pane {{
                border: 1px solid {t['text_small']};
                background-color: {t['panel']};
            }}
            QTabBar::tab {{
                background-color: {t['bg']};
                color: {t['text_small']};
                padding: 8px 16px;
                border: 1px solid {t['text_small']};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: {t['accent']};
                color: white;
            }}
            QStatusBar {{
                background-color: {t['panel']};
                color: {t['text_small']};
            }}
            QLabel {{
                color: {t['fg']};
            }}
            QMenuBar {{
                background-color: {t['panel']};
                color: {t['fg']};
            }}
            QMenu {{
                background-color: {t['panel']};
                color: {t['fg']};
            }}
            QMenu::item:selected {{
                background-color: {t['accent']};
            }}
            QTextEdit, QPlainTextEdit {{
                background-color: {t['bg']};
                color: {t['fg']};
                border: 1px solid {t['text_small']};
            }}
        """
