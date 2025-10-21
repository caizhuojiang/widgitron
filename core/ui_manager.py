"""
UI Manager for Widgitron
Handles UI creation and layout management
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QStackedWidget
from PyQt5.QtCore import Qt

from .ui_components import UIComponents
from .applications_page import ApplicationsPage
from .settings_page import SettingsPage
from .ui_styles import UIStyles


class UIManager:
    """Manages UI creation and layout for Widgitron"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.tab_buttons = {}
        self.sidebar = None
        self.stacked_widget = None

        # Initialize sub-managers
        self.components = UIComponents(self)
        self.applications_page = ApplicationsPage(self)
        self.settings_page = SettingsPage(self)

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
        title_bar = self.components.create_title_bar()
        self.main_window.title_bar = title_bar  # Store reference
        content_layout.addWidget(title_bar)

        # Main content area with sidebar and content
        content_area = QWidget()
        content_area.setMouseTracking(True)  # Enable mouse tracking
        content_area_layout = QHBoxLayout(content_area)
        content_area_layout.setContentsMargins(0, 0, 0, 0)
        content_area_layout.setSpacing(0)

        # Left sidebar
        sidebar = self.components.create_sidebar()
        self.sidebar = sidebar
        self.main_window.sidebar = sidebar  # Store reference
        content_area_layout.addWidget(sidebar)

        # Main content
        main_content = self.create_main_content()
        content_area_layout.addWidget(main_content)

        content_layout.addWidget(content_area)

        main_layout.addWidget(content_frame)

        # Apply stylesheet
        container.setStyleSheet(UIStyles.get_stylesheet())

    def create_main_content(self):
        """Create main content area with stacked widget for different tabs"""
        main_content = QWidget()
        main_content.setObjectName("mainContent")
        main_content.setMouseTracking(True)  # Enable mouse tracking

        layout = QVBoxLayout(main_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create stacked widget for tab content
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setMouseTracking(True)  # Enable mouse tracking
        self.main_window.stacked_widget = self.stacked_widget

        # Create applications page
        applications_page = self.applications_page.create_page()
        self.stacked_widget.addWidget(applications_page)

        # Create settings page
        settings_page = self.settings_page.create_page()
        self.stacked_widget.addWidget(settings_page)

        layout.addWidget(self.stacked_widget)

        return main_content

    def update_tab_button_states(self):
        """Update tab button states based on current tab"""
        self.components.update_tab_button_states()
