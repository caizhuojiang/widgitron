"""
Applications Page for Widgitron UI
Handles the applications/widgets page creation and management
"""

import os
from PyQt5.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon


class ApplicationsPage:
    """Manages the applications/widgets page"""

    def __init__(self, ui_manager):
        self.ui_manager = ui_manager

    def create_page(self):
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

        # Paper Deadline Card
        paper_card = self.create_widget_card(
            "Paper Deadline",
            "paper_deadline",
            os.path.join(os.path.dirname(__file__), '..', 'icons', 'search_icon.png')
        )
        layout.addWidget(paper_card, 0, 1)

        # Add Widget Card
        add_card = self.create_add_widget_card()
        layout.addWidget(add_card, 0, 2)

        # Add stretch to push cards to top-left
        layout.setRowStretch(1, 1)
        layout.setColumnStretch(2, 1)

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
        if widget_id in self.ui_manager.main_window.active_widgets:
            btn.setObjectName("widgetButtonActive")
        else:
            btn.setObjectName("widgetButtonInactive")

        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(60, 60))

        btn.setToolTip(f"Toggle {name}")
        btn.clicked.connect(lambda: self.ui_manager.main_window.toggle_widget(widget_id, btn))
        btn.widget_id = widget_id  # Store widget_id for later reference
        layout.addWidget(btn, alignment=Qt.AlignCenter)

        # Store button reference
        if widget_id == 'gpu_monitor':
            self.ui_manager.main_window.gpu_monitor_btn = btn
        elif widget_id == 'paper_deadline':
            self.ui_manager.main_window.paper_deadline_btn = btn

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
        btn.clicked.connect(self.ui_manager.main_window.add_widget)
        layout.addWidget(btn, alignment=Qt.AlignCenter)

        # Label
        label = QLabel("Add Widget")
        label.setObjectName("widgetLabel")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        return card