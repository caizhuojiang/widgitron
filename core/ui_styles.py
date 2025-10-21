"""
UI Styles for Widgitron
Contains all stylesheet definitions
"""


class UIStyles:
    """Manages UI stylesheets"""

    @staticmethod
    def get_stylesheet():
        """Get the complete stylesheet for the application"""
        return """
            QWidget#mainContainer {
                background: transparent;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", "Arial", sans-serif;
            }
            QFrame#contentFrame {
                background: #f6f8fa;
                border-radius: 15px;
                overflow: hidden;
            }
            QFrame#contentFrameMaximized {
                background: #f6f8fa;
                border-radius: 0px;
            }
            QWidget#titleBar {
                background: white;
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
                border-bottom: 1px solid #e8eaed;
                min-height: 50px;
            }
            QWidget#titleBarMaximized {
                background: white;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom: 1px solid #e8eaed;
                min-height: 50px;
            }
            QLabel#titleLabel {
                color: #1f2937;
                font-size: 18px;
                font-weight: 600;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", "Arial", sans-serif;
                padding-left: 15px;
            }
            QPushButton#titleButton {
                background: transparent;
                border: none;
                color: #6b7280;
                font-size: 20px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", "Arial", sans-serif;
                padding: 5px 15px;
                min-width: 40px;
            }
            QPushButton#titleButton:hover {
                background: #f3f4f6;
                color: #1f2937;
            }
            QWidget#sidebar {
                background: white;
                border-right: 1px solid #e8eaed;
                border-bottom-left-radius: 15px;
                min-width: 80px;
                max-width: 80px;
            }
            QWidget#sidebarMaximized {
                background: white;
                border-right: 1px solid #e8eaed;
                border-bottom-left-radius: 0px;
                min-width: 80px;
                max-width: 80px;
            }
            QPushButton#sidebarButton {
                background: transparent;
                border: none;
                border-radius: 12px;
                padding: 10px;
                margin: 10px;
            }
            QPushButton#sidebarButton:hover {
                background: #f3f4f6;
            }
            QPushButton#sidebarButtonActive {
                background: #e5e7eb;
                border-radius: 12px;
            }
            QWidget#mainContent {
                background: transparent;
                padding: 30px;
            }
            QWidget#widgetCard {
                background: #f6f8fa;
                border-radius: 15px;
                padding: 20px;
                min-width: 140px;
                max-width: 140px;
            }
            QWidget#widgetCard:hover {
                background: white;
            }
            QPushButton#widgetButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #9333ea, stop:1 #7e22ce);
                border: none;
                border-radius: 15px;
                min-width: 100px;
                min-height: 100px;
                max-width: 100px;
                max-height: 100px;
            }
            QPushButton#widgetButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #a855f7, stop:1 #9333ea);
            }
            QPushButton#widgetButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7e22ce, stop:1 #6b21a8);
            }
            QPushButton#widgetButtonActive {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #76e371, stop:1 #4ade80);
                border: 2px solid #22c55e;
                border-radius: 15px;
                min-width: 100px;
                min-height: 100px;
                max-width: 100px;
                max-height: 100px;
            }
            QPushButton#widgetButtonInactive {
                background: white;
                border: none;
                border-radius: 15px;
                color: #4a5568;
                min-width: 100px;
                min-height: 100px;
                max-width: 100px;
                max-height: 100px;
            }
            QPushButton#widgetButtonInactive:hover {
                border: 2px solid #667eea;
                background: #f7fafc;
            }
            QLabel#widgetLabel {
                color: #2d3748;
                font-size: 15px;
                font-weight: 500;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", "Arial", sans-serif;
            }
            QPushButton#addWidgetButton {
                background: white;
                border: 2px dashed #cbd5e0;
                border-radius: 15px;
                color: #a0aec0;
                font-size: 48px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", "Arial", sans-serif;
                min-width: 100px;
                min-height: 100px;
                max-width: 100px;
                max-height: 100px;
            }
            QPushButton#addWidgetButton:hover {
                border-color: #667eea;
                color: #667eea;
                background: #f7fafc;
            }
            QScrollArea#settingsScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea#settingsScrollArea QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: #f4f4f4;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #c1c1c1;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a8a8a8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            
            /* Settings Page Styles */
            QFrame#settingsSidebar {
                background: white;
                border-right: 1px solid #e5e7eb;
            }
            QPushButton#settingsMenuButton {
                background: transparent;
                border: 1px solid transparent;
                color: #6b7280;
                text-align: left;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: 500;
                border-radius: 20px;
            }
            QPushButton#settingsMenuButton:hover {
                background: #f0f0f0;
                border: 1px solid #d0d0d0;
                color: #1f2937;
            }
            QPushButton#settingsMenuButtonActive {
                background: #e8e8e8;
                border: 1px solid #c0c0c0;
                color: #6b7280;
                text-align: left;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: 500;
                border-radius: 20px;
            }
            QScrollArea#settingsContentScroll {
                border: none;
                background: #f6f8fa;
                border-radius: 15px;
            }
            QWidget#settingsContentContainer {
                background: #f6f8fa;
            }
            QLabel#settingsContentTitle {
                font-size: 26px;
                font-weight: 700;
                color: #111827;
                margin-bottom: 5px;
            }
            QLabel#settingsContentDescription {
                font-size: 14px;
                color: #6b7280;
                margin-bottom: 10px;
            }
            QFrame#settingsSeparator {
                background: #e5e7eb;
                max-height: 1px;
                margin: 10px 0px;
            }
            QGroupBox#modernSettingsCard {
                font-weight: 600;
                font-size: 15px;
                color: #1f2937;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 15px;
                margin-top: 15px;
                background: white;
            }
            QGroupBox#modernSettingsCard::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #111827;
                font-weight: 600;
                background: white;
            }
            QComboBox#settingsComboBox {
                background: white;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 200px;
                color: #374151;
                font-size: 13px;
            }
            QComboBox#settingsComboBox:hover {
                border-color: #3b82f6;
            }
            QComboBox#settingsComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox#settingsComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #6b7280;
                margin-right: 8px;
            }
            QCheckBox#settingsCheckBox {
                color: #374151;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox#settingsCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #d1d5db;
                border-radius: 4px;
                background: white;
            }
            QCheckBox#settingsCheckBox::indicator:hover {
                border-color: #3b82f6;
            }
            QCheckBox#settingsCheckBox::indicator:checked {
                background: #3b82f6;
                border-color: #3b82f6;
                image: none;
            }
            QLabel#settingsInfoLabel {
                color: #6b7280;
                font-size: 13px;
                padding: 8px 0px;
            }
            QTextEdit#aboutTextEdit {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                background: #f9fafb;
                color: #374151;
                font-size: 13px;
                padding: 12px;
                line-height: 1.5;
            }
            QLabel#aboutAppName {
                font-size: 20px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#aboutVersion {
                font-size: 13px;
                color: #6b7280;
            }
            QPushButton#settingsPrimaryButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                border: none;
                border-radius: 8px;
                color: white;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
                min-height: 36px;
            }
            QPushButton#settingsPrimaryButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }
            QPushButton#settingsPrimaryButton:pressed {
                background: #1e40af;
            }
            QPushButton#settingsSecondaryButton {
                background: white;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                color: #374151;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
                min-height: 36px;
            }
            QPushButton#settingsSecondaryButton:hover {
                background: #f9fafb;
                border-color: #9ca3af;
            }
            QPushButton#settingsSecondaryButton:pressed {
                background: #f3f4f6;
            }
        """