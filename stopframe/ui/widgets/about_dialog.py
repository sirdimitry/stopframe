"""Branded About panel with the runtime version and project credit."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QTextBrowser

from stopframe import __version__
from stopframe.about import TECH_STACK, CREDIT
from stopframe.resources import resource_path


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About StopFrame")
        self.setFixedWidth(680)
        self.setStyleSheet("QDialog { background: #101113; } QLabel { color: #f5f1e9; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)
        banner = QLabel()
        banner.setPixmap(QPixmap(str(resource_path('assets', 'branding', 'banner.png'))).scaledToWidth(
            632, Qt.TransformationMode.SmoothTransformation))
        banner.setAccessibleName("StopFrame — Find the frame worth keeping")
        layout.addWidget(banner)

        row = QHBoxLayout()
        self.version_label = QLabel(f"Version {__version__}")
        self.version_label.setStyleSheet("color: #ff8057; font-size: 18px; font-weight: 600;")
        row.addWidget(self.version_label)
        row.addStretch()
        credit = QLabel(CREDIT)
        credit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        credit.setStyleSheet("font-size: 15px;")
        row.addWidget(credit)
        layout.addLayout(row)
        description = QLabel("Sharp, distinct stills from your videos.\nRuns locally on your Mac — no uploads, no accounts.")
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 14px; color: #b8b8bd; padding: 4px 0;")
        layout.addWidget(description)
        details = QTextBrowser()
        details.setOpenExternalLinks(False)
        details.setPlainText("Built with\n\n" + "\n\n".join(TECH_STACK))
        details.setFixedHeight(180)
        details.setStyleSheet("background: #191a1d; border: 1px solid #303136; border-radius: 10px; padding: 10px; color: #b8b8bd;")
        layout.addWidget(details)
        close = QPushButton("Close")
        close.setObjectName("primaryButton")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
