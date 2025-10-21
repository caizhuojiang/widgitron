"""
UI Components for Widgitron
Common UI components and utilities
"""

import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon


class UIComponents:
    """Common UI components"""

    def __init__(self, ui_manager):
        self.ui_manager = ui_manager

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
        min_btn.clicked.connect(self.ui_manager.main_window.showMinimized)
        layout.addWidget(min_btn)

        # Maximize/Restore button
        self.ui_manager.main_window.max_btn = QPushButton("□")
        self.ui_manager.main_window.max_btn.setObjectName("titleButton")
        self.ui_manager.main_window.max_btn.setToolTip("Maximize")
        self.ui_manager.main_window.max_btn.clicked.connect(self.ui_manager.main_window.toggle_maximize)
        layout.addWidget(self.ui_manager.main_window.max_btn)

        # Close button
        close_btn = QPushButton("×")
        close_btn.setObjectName("titleButton")
        close_btn.setToolTip("Hide to tray")
        close_btn.clicked.connect(self.ui_manager.main_window.hide)
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
            os.path.join(os.path.dirname(__file__), '..', 'icons', 'home_icon.png'),
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
        btn.clicked.connect(lambda: self.ui_manager.main_window.switch_tab(tab_id))

        # Store button reference
        self.ui_manager.tab_buttons[tab_id] = btn
        self.ui_manager.main_window.tab_buttons[tab_id] = btn

        # Set initial state
        if tab_id == self.ui_manager.main_window.current_tab:
            btn.setObjectName("sidebarButtonActive")
            btn.setStyle(btn.style())

        return btn

    def update_tab_button_states(self):
        """Update tab button states based on current tab"""
        for tab_id, btn in self.ui_manager.tab_buttons.items():
            if tab_id == self.ui_manager.main_window.current_tab:
                btn.setObjectName("sidebarButtonActive")
            else:
                btn.setObjectName("sidebarButton")
            btn.setStyle(btn.style())