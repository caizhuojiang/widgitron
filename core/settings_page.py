"""
Settings Page for Widgitron UI
Handles the settings page creation and management
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout,
                             QScrollArea, QGroupBox, QCheckBox, QComboBox,
                             QPushButton, QTextEdit, QFormLayout, QFrame,
                             QStackedWidget, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon
import json
import os


class SettingsPage:
    """Manages the settings page"""

    def __init__(self, ui_manager):
        self.ui_manager = ui_manager
        self.current_settings_tab = "general"  # Default selected general settings
        self.settings_menu_buttons = {}  # Store settings menu buttons

    def create_page(self):
        """Create the settings page content with sidebar navigation"""
        # Main container
        main_container = QWidget()
        main_container.setObjectName("settingsMainContainer")
        main_layout = QHBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left sidebar for settings categories
        sidebar = self.create_settings_sidebar()
        main_layout.addWidget(sidebar)

        # Right content area
        content_area = self.create_settings_content()
        main_layout.addWidget(content_area, 1)  # Stretch factor 1

        return main_container

    def create_settings_sidebar(self):
        """Create the left sidebar with settings categories"""
        sidebar = QFrame()
        sidebar.setObjectName("settingsSidebar")
        sidebar.setMinimumWidth(300)
        sidebar.setMaximumWidth(300)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 20, 20, 20)
        sidebar_layout.setSpacing(5)
        sidebar_layout.setAlignment(Qt.AlignTop)

        # Settings menu items
        menu_items = [
            {"id": "general", "label": "General Settings", "icon": "🔧"},
            {"id": "widgets", "label": "Widgets", "icon": "📦"},
            {"id": "about", "label": "About", "icon": "ℹ️"},
        ]

        for item in menu_items:
            btn = self.create_settings_menu_button(item["id"], item["label"], item["icon"])
            sidebar_layout.addWidget(btn)
            self.settings_menu_buttons[item["id"]] = btn

        # Set first button as active
        if "general" in self.settings_menu_buttons:
            self.settings_menu_buttons["general"].setObjectName("settingsMenuButtonActive")
            self.settings_menu_buttons["general"].setStyle(self.settings_menu_buttons["general"].style())

        sidebar_layout.addStretch()

        return sidebar

    def create_settings_menu_button(self, item_id, label, icon):
        """Create a settings menu button"""
        btn = QPushButton(f"  {icon}  {label}")
        btn.setObjectName("settingsMenuButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(44)
        btn.clicked.connect(lambda: self.switch_settings_tab(item_id))
        
        font = QFont()
        font.setPointSize(10)
        btn.setFont(font)
        
        return btn

    def create_settings_content(self):
        """Create the right content area with stacked widget"""
        # Stacked widget for different settings pages
        self.settings_stacked_widget = QStackedWidget()
        self.settings_stacked_widget.setObjectName("settingsStackedWidget")

        # Add different settings pages
        self.settings_stacked_widget.addWidget(self.create_general_settings())
        self.settings_stacked_widget.addWidget(self.create_widgets_settings())
        self.settings_stacked_widget.addWidget(self.create_about_settings())

        return self.settings_stacked_widget

    def switch_settings_tab(self, tab_id):
        """Switch to the specified settings tab"""
        if tab_id == self.current_settings_tab:
            return

        # Update button states
        if self.current_settings_tab in self.settings_menu_buttons:
            self.settings_menu_buttons[self.current_settings_tab].setObjectName("settingsMenuButton")
            self.settings_menu_buttons[self.current_settings_tab].setStyle(
                self.settings_menu_buttons[self.current_settings_tab].style())

        if tab_id in self.settings_menu_buttons:
            self.settings_menu_buttons[tab_id].setObjectName("settingsMenuButtonActive")
            self.settings_menu_buttons[tab_id].setStyle(self.settings_menu_buttons[tab_id].style())

        # Update current tab
        self.current_settings_tab = tab_id

        # Switch stacked widget page
        tab_indices = {
            "general": 0,
            "widgets": 1,
            "about": 2
        }
        
        if tab_id in tab_indices:
            self.settings_stacked_widget.setCurrentIndex(tab_indices[tab_id])

    def create_general_settings(self):
        """Create general settings page"""
        return self.create_settings_scroll_page(
            "General Settings",
            "Configure basic application settings and behavior",
            self.create_general_content()
        )

    def create_widgets_settings(self):
        """Create widgets settings page"""
        return self.create_settings_scroll_page(
            "Widget Settings",
            "Configure individual widget settings",
            self.create_widgets_content()
        )

    def create_about_settings(self):
        """Create about page"""
        return self.create_settings_scroll_page(
            "About Widgitron",
            "Application information and version details",
            self.create_about_content()
        )

    def create_settings_scroll_page(self, title, description, content_widget):
        """Create a scrollable settings page with title and description"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setObjectName("settingsContentScroll")

        container = QWidget()
        container.setObjectName("settingsContentContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(25)
        layout.setAlignment(Qt.AlignTop)

        # Title
        title_label = QLabel(title)
        title_label.setObjectName("settingsContentTitle")
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setObjectName("settingsContentDescription")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("settingsSeparator")
        layout.addWidget(separator)

        # Content
        layout.addWidget(content_widget)
        layout.addStretch()

        scroll_area.setWidget(container)
        return scroll_area

    def create_general_content(self):
        """Create general settings content"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Language settings card
        lang_card = self.create_modern_settings_card("Language Settings")
        lang_layout = QFormLayout(lang_card)
        lang_layout.setContentsMargins(25, 25, 25, 25)
        lang_layout.setSpacing(15)

        lang_combo = QComboBox()
        lang_combo.addItems(["English"])
        lang_combo.setCurrentText("English")
        lang_combo.setObjectName("settingsComboBox")
        lang_layout.addRow("Interface Language:", lang_combo)

        layout.addWidget(lang_card)

        # Theme Settings Card
        theme_card = self.create_modern_settings_card("Theme Settings")
        theme_layout = QFormLayout(theme_card)
        theme_layout.setContentsMargins(25, 25, 25, 25)
        theme_layout.setSpacing(15)

        # Theme selector
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light Theme"])
        self.theme_combo.setCurrentText("Light Theme")
        self.theme_combo.setObjectName("settingsComboBox")

        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        theme_layout.addRow("Appearance Theme:", self.theme_combo)

        layout.addWidget(theme_card)

        return widget

    def create_widgets_content(self):
        """Create widgets settings content"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Dynamically load settings for each widget
        self.load_widget_settings(layout)

        return widget

    def create_about_content(self):
        """Create about page content"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # About Card
        about_card = self.create_modern_settings_card("Application Information")
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(25, 25, 25, 25)
        about_layout.setSpacing(15)

        # App icon and name
        header_layout = QHBoxLayout()
        
        # Icon
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icons', 'widgitron.png')
        if os.path.exists(icon_path):
            icon_pixmap = QIcon(icon_path).pixmap(64, 64)
            icon_label.setPixmap(icon_pixmap)
        header_layout.addWidget(icon_label)
        
        # App name and version
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        app_name_label = QLabel("Widgitron")
        app_name_label.setObjectName("aboutAppName")
        info_layout.addWidget(app_name_label)
        
        version_label = QLabel(f"Version {self.ui_manager.main_window.config.get('version', '0.1.0')}")
        version_label.setObjectName("aboutVersion")
        info_layout.addWidget(version_label)
        
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        about_layout.addLayout(header_layout)

        # Description
        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setObjectName("aboutTextEdit")
        about_text.setPlainText(f"""
{self.ui_manager.main_window.config.get('description', 'A modular desktop widget framework for researchers and developers')}

Key Features:
• Modular widget system
• System tray integration
• Customizable themes
• GPU monitoring capabilities
• Extensible architecture

Built with PyQt5
""")
        about_text.setMaximumHeight(200)
        about_layout.addWidget(about_text)

        layout.addWidget(about_card)

        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        # Reset button
        reset_btn = QPushButton("Reset Settings")
        reset_btn.setObjectName("settingsSecondaryButton")
        reset_btn.setMinimumWidth(120)
        reset_btn.clicked.connect(self.reset_settings)
        buttons_layout.addWidget(reset_btn)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        return widget

    def load_widget_settings(self, layout):
        """Dynamically load settings for all available widgets"""
        # Get available widgets from widget manager
        available_widgets = self.ui_manager.main_window.widget_manager.widget_classes
        
        for widget_id, (module_name, class_name) in available_widgets.items():
            try:
                # Import the widget module
                module = __import__(module_name, fromlist=[class_name])
                widget_class = getattr(module, class_name)
                
                # Check if the widget class has a get_settings_ui method
                if hasattr(widget_class, 'get_settings_ui'):
                    # Create settings card for this widget
                    widget_card = self.create_modern_settings_card(f"{widget_id.replace('_', ' ').title()} Settings")
                    widget_layout = QVBoxLayout(widget_card)
                    widget_layout.setContentsMargins(25, 25, 25, 25)
                    widget_layout.setSpacing(15)
                    
                    # Get the settings UI from the widget class
                    settings_ui = widget_class.get_settings_ui(self)
                    if settings_ui:
                        widget_layout.addWidget(settings_ui)
                    
                    layout.addWidget(widget_card)
                    
            except Exception as e:
                print(f"Failed to load settings for {widget_id}: {e}")

    def create_modern_settings_card(self, title):
        """Create a modern settings card with title"""
        card = QGroupBox(title)
        card.setObjectName("modernSettingsCard")
        return card

    def on_theme_changed(self, theme_text):
        """Handle theme selection change"""
        # Update config based on theme selection
        if theme_text == "Light Theme":
            self.ui_manager.main_window.config['theme']['dark_mode'] = False
            self.ui_manager.main_window.config['theme']['style'] = 'light'

        # Save to file
        config_path = 'configs/widgitron.json'
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.ui_manager.main_window.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            # Silently handle save errors for auto-save
            print(f"Failed to save settings: {str(e)}")

    def on_setting_changed(self):
        """Handle setting changes - auto save"""
        # Update config with current UI values
        # No settings to update currently

        # Save to file
        config_path = 'configs/widgitron.json'
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.ui_manager.main_window.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            # Silently handle save errors for auto-save
            print(f"Failed to save settings: {str(e)}")

    def reset_settings(self):
        """Reset settings to default values"""
        from PyQt5.QtWidgets import QMessageBox

        reply = QMessageBox.question(self.ui_manager.main_window, "Reset Settings",
                                   "Are you sure you want to reset all settings to default values?",
                                   QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            # Reset to defaults
            self.theme_combo.setCurrentText("Light Theme")

            # Auto-save after reset
            self.on_theme_changed("Light Theme")
