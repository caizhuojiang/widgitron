"""
UI Manager for Widgitron
Handles UI creation and layout management
"""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QGridLayout, QFrame, QStackedWidget)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon


class UIManager:
    """Manages UI creation and layout for Widgitron"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.tab_buttons = {}
        self.sidebar = None
        self.stacked_widget = None

    def setup_ui(self):
        """Setup the main window UI"""
        # Main container with shadow
        container = QWidget()
        container.setObjectName("mainContainer")
        container.setMouseTracking(True)  # Enable mouse tracking
        self.main_window.setCentralWidget(container)

        # Add shadow effect
        shadow = self.main_window.shadow_effect()
        container.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)

        # Content frame with rounded corners
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_frame.setMouseTracking(True)  # Enable mouse tracking
        self.main_window.content_frame = content_frame  # Store reference
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Custom title bar
        title_bar = self.create_title_bar()
        self.main_window.title_bar = title_bar  # Store reference
        content_layout.addWidget(title_bar)

        # Main content area with sidebar and content
        content_area = QWidget()
        content_area.setMouseTracking(True)  # Enable mouse tracking
        content_area_layout = QHBoxLayout(content_area)
        content_area_layout.setContentsMargins(0, 0, 0, 0)
        content_area_layout.setSpacing(0)

        # Left sidebar
        sidebar = self.create_sidebar()
        self.sidebar = sidebar
        self.main_window.sidebar = sidebar  # Store reference
        content_area_layout.addWidget(sidebar)

        # Main content
        main_content = self.create_main_content()
        content_area_layout.addWidget(main_content)

        content_layout.addWidget(content_area)

        main_layout.addWidget(content_frame)

        # Apply stylesheet
        container.setStyleSheet(self.get_stylesheet())

    def create_title_bar(self):
        """Create custom title bar"""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(50)
        title_bar.setMouseTracking(True)  # Enable mouse tracking

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(5)

        # Title
        title_label = QLabel("Widgitron")
        title_label.setObjectName("titleLabel")
        layout.addWidget(title_label)

        layout.addStretch()

        # Minimize button
        min_btn = QPushButton("−")
        min_btn.setObjectName("titleButton")
        min_btn.setToolTip("Minimize")
        min_btn.clicked.connect(self.main_window.showMinimized)
        layout.addWidget(min_btn)

        # Maximize/Restore button
        self.main_window.max_btn = QPushButton("□")
        self.main_window.max_btn.setObjectName("titleButton")
        self.main_window.max_btn.setToolTip("Maximize")
        self.main_window.max_btn.clicked.connect(self.main_window.toggle_maximize)
        layout.addWidget(self.main_window.max_btn)

        # Close button
        close_btn = QPushButton("×")
        close_btn.setObjectName("titleButton")
        close_btn.setToolTip("Hide to tray")
        close_btn.clicked.connect(self.main_window.hide)
        layout.addWidget(close_btn)

        return title_bar

    def create_sidebar(self):
        """Create left sidebar with tab buttons"""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMouseTracking(True)  # Enable mouse tracking

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 20, 0, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # Applications tab button
        app_btn = self.create_tab_button(
            "applications",
            os.path.join(os.path.dirname(__file__), '..', 'icons', 'app_icon.png'),
            "Applications"
        )
        layout.addWidget(app_btn)

        # Settings tab button
        settings_btn = self.create_tab_button(
            "settings",
            os.path.join(os.path.dirname(__file__), '..', 'icons', 'settings_icon.png'),
            "Settings"
        )
        layout.addWidget(settings_btn)

        layout.addStretch()

        return sidebar

    def create_tab_button(self, tab_id, icon_path, tooltip):
        """Create a tab button with proper styling"""
        btn = QPushButton()
        btn.setObjectName("sidebarButton")

        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(32, 32))

        btn.setFixedSize(60, 60)
        btn.setToolTip(tooltip)
        btn.clicked.connect(lambda: self.main_window.switch_tab(tab_id))

        # Store button reference
        self.tab_buttons[tab_id] = btn
        self.main_window.tab_buttons[tab_id] = btn

        # Set initial state
        if tab_id == self.main_window.current_tab:
            btn.setObjectName("sidebarButtonActive")
            btn.setStyle(btn.style())

        return btn

    def create_main_content(self):
        """Create main content area with stacked widget for different tabs"""
        main_content = QWidget()
        main_content.setObjectName("mainContent")
        main_content.setMouseTracking(True)  # Enable mouse tracking

        layout = QVBoxLayout(main_content)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(0)

        # Create stacked widget for tab content
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setMouseTracking(True)  # Enable mouse tracking
        self.main_window.stacked_widget = self.stacked_widget

        # Create applications page
        applications_page = self.create_applications_page()
        self.stacked_widget.addWidget(applications_page)

        # Create settings page
        settings_page = self.create_settings_page()
        self.stacked_widget.addWidget(settings_page)

        layout.addWidget(self.stacked_widget)

        return main_content

    def create_applications_page(self):
        """Create the applications page content"""
        page = QWidget()
        page.setMouseTracking(True)  # Enable mouse tracking

        # Use grid layout for widget cards
        layout = QGridLayout(page)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        # GPU Monitor Card
        gpu_card = self.create_widget_card(
            "GPU Monitor",
            "gpu_monitor",
            os.path.join(os.path.dirname(__file__), '..', 'icons', 'widgitron.png')
        )
        layout.addWidget(gpu_card, 0, 0)

        # Add Widget Card
        add_card = self.create_add_widget_card()
        layout.addWidget(add_card, 0, 1)

        # Add stretch to push cards to top-left
        layout.setRowStretch(1, 1)
        layout.setColumnStretch(2, 1)

        return page

    def create_settings_page(self):
        """Create the settings page content"""
        page = QWidget()
        page.setMouseTracking(True)  # Enable mouse tracking

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignTop)

        # Settings title
        title_label = QLabel("Settings")
        title_label.setObjectName("pageTitle")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #1f2937;")
        layout.addWidget(title_label)

        # Placeholder content
        placeholder_label = QLabel("Settings panel is under development.\n\nFuture features:\n• Theme customization\n• Auto-start configuration\n• Performance settings")
        placeholder_label.setWordWrap(True)
        placeholder_label.setStyleSheet("color: #6b7280; font-size: 14px; line-height: 1.5;")
        layout.addWidget(placeholder_label)

        # Add stretch to push content to top
        layout.addStretch()

        return page

    def create_widget_card(self, name, widget_id, icon_path):
        """Create a widget card"""
        card = QWidget()
        card.setObjectName("widgetCard")
        card.setMouseTracking(True)  # Enable mouse tracking

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        # Widget button
        btn = QPushButton()
        if widget_id in self.main_window.active_widgets:
            btn.setObjectName("widgetButtonActive")
        else:
            btn.setObjectName("widgetButtonInactive")

        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(60, 60))

        btn.setToolTip(f"Toggle {name}")
        btn.clicked.connect(lambda: self.main_window.toggle_widget(widget_id, btn))
        btn.widget_id = widget_id  # Store widget_id for later reference
        layout.addWidget(btn, alignment=Qt.AlignCenter)

        # Store button reference
        if widget_id == 'gpu_monitor':
            self.main_window.gpu_monitor_btn = btn

        # Widget label
        label = QLabel(name)
        label.setObjectName("widgetLabel")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        return card

    def create_add_widget_card(self):
        """Create add widget card"""
        card = QWidget()
        card.setObjectName("widgetCard")
        card.setMouseTracking(True)  # Enable mouse tracking

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        # Add button
        btn = QPushButton("+")
        btn.setObjectName("addWidgetButton")
        btn.setToolTip("Add new widget")
        btn.clicked.connect(self.main_window.add_widget)
        layout.addWidget(btn, alignment=Qt.AlignCenter)

        # Label
        label = QLabel("Add Widget")
        label.setObjectName("widgetLabel")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        return card

    def get_stylesheet(self):
        """Get the complete stylesheet for the application"""
        return """
            QWidget#mainContainer {
                background: transparent;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", "Arial", sans-serif;
            }
            QFrame#contentFrame {
                background: #f5f7fa;
                border-radius: 15px;
            }
            QFrame#contentFrameMaximized {
                background: #f5f7fa;
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
                background: white;
                border-radius: 15px;
                padding: 20px;
                min-width: 140px;
                max-width: 140px;
            }
            QWidget#widgetCard:hover {
                background: #f8f9fa;
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
        """

    def update_tab_button_states(self):
        """Update tab button states based on current tab"""
        for tab_id, btn in self.tab_buttons.items():
            if tab_id == self.main_window.current_tab:
                btn.setObjectName("sidebarButtonActive")
            else:
                btn.setObjectName("sidebarButton")
            btn.setStyle(btn.style())